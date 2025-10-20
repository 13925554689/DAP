"""
数据版本控制器 - Layer 2
数据版本控制和回滚能力管理

核心功能：
1. 数据版本管理和标记
2. 增量和全量快照
3. 智能回滚机制
4. 版本比较和差异分析
5. 分支合并和冲突解决
"""

import asyncio
import logging
import json
import sqlite3
import hashlib
import shutil
import gzip
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from enum import Enum

# 压缩支持
try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

try:
    import lz4.frame
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False

# Git风格版本控制（可选）
try:
    import dulwich
    DULWICH_AVAILABLE = True
except ImportError:
    DULWICH_AVAILABLE = False

class VersionType(Enum):
    """版本类型"""
    FULL = "full"           # 全量快照
    INCREMENTAL = "incremental"  # 增量快照
    DELTA = "delta"         # 差异快照
    BRANCH = "branch"       # 分支版本
    TAG = "tag"            # 标记版本

class ConflictResolution(Enum):
    """冲突解决策略"""
    MANUAL = "manual"       # 手动解决
    AUTO_LATEST = "auto_latest"    # 自动选择最新
    AUTO_MERGE = "auto_merge"      # 自动合并
    ROLLBACK = "rollback"   # 回滚操作

@dataclass
class DataVersion:
    """数据版本信息"""
    version_id: str
    version_number: str
    version_type: VersionType
    parent_version: Optional[str]
    data_hash: str
    metadata: Dict[str, Any]
    created_at: datetime
    created_by: str
    description: str
    is_active: bool
    file_path: str
    compressed_size: int
    original_size: int

@dataclass
class VersionDiff:
    """版本差异"""
    from_version: str
    to_version: str
    added_records: List[Dict[str, Any]]
    modified_records: List[Dict[str, Any]]
    deleted_records: List[Dict[str, Any]]
    schema_changes: Dict[str, Any]
    statistics: Dict[str, Any]

@dataclass
class BranchInfo:
    """分支信息"""
    branch_name: str
    base_version: str
    head_version: str
    created_at: datetime
    created_by: str
    description: str
    is_merged: bool

class VersionController:
    """数据版本控制器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 版本存储配置
        self.version_db_path = self.config.get('version_db_path', 'data/versions.db')
        self.version_storage_path = self.config.get('version_storage_path', 'data/versions/')
        self.max_versions = self.config.get('max_versions', 100)
        self.auto_cleanup = self.config.get('auto_cleanup', True)

        # 压缩配置
        self.compression_algorithm = self.config.get('compression_algorithm', 'auto')
        self.compression_level = self.config.get('compression_level', 6)

        # 并发控制
        self.max_workers = self.config.get('max_workers', 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # 缓存
        self._version_cache = {}
        self._diff_cache = {}
        self._lock = threading.RLock()

        # 确保存储目录存在
        Path(self.version_storage_path).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 当前分支
        self.current_branch = 'main'

    def _init_database(self):
        """初始化版本数据库"""
        try:
            Path(self.version_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()

                # 版本表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS data_versions (
                        version_id TEXT PRIMARY KEY,
                        version_number TEXT NOT NULL,
                        version_type TEXT NOT NULL,
                        parent_version TEXT,
                        data_hash TEXT NOT NULL,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        description TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        file_path TEXT NOT NULL,
                        compressed_size INTEGER,
                        original_size INTEGER,
                        branch_name TEXT DEFAULT 'main',
                        FOREIGN KEY (parent_version) REFERENCES data_versions (version_id)
                    )
                ''')

                # 分支表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS version_branches (
                        branch_name TEXT PRIMARY KEY,
                        base_version TEXT NOT NULL,
                        head_version TEXT,
                        created_at TEXT NOT NULL,
                        created_by TEXT NOT NULL,
                        description TEXT,
                        is_merged BOOLEAN DEFAULT 0,
                        FOREIGN KEY (base_version) REFERENCES data_versions (version_id),
                        FOREIGN KEY (head_version) REFERENCES data_versions (version_id)
                    )
                ''')

                # 版本差异表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS version_diffs (
                        diff_id TEXT PRIMARY KEY,
                        from_version TEXT NOT NULL,
                        to_version TEXT NOT NULL,
                        diff_data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (from_version) REFERENCES data_versions (version_id),
                        FOREIGN KEY (to_version) REFERENCES data_versions (version_id)
                    )
                ''')

                # 索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_versions_number ON data_versions (version_number)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_versions_branch ON data_versions (branch_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_versions_created ON data_versions (created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_diffs_versions ON version_diffs (from_version, to_version)')

                # 插入默认分支
                cursor.execute('''
                    INSERT OR IGNORE INTO version_branches
                    (branch_name, base_version, created_at, created_by, description)
                    VALUES ('main', 'root', ?, 'system', '主分支')
                ''', (datetime.now().isoformat(),))

                conn.commit()

            self.logger.info("版本控制数据库初始化完成")

        except Exception as e:
            self.logger.error(f"版本控制数据库初始化失败: {e}")
            raise

    async def create_version(self, data: Any, version_info: Dict[str, Any]) -> Dict[str, Any]:
        """创建新版本"""
        try:
            # 生成版本信息
            version_id = self._generate_version_id()
            version_number = version_info.get('version_number') or self._generate_version_number()

            # 计算数据哈希
            data_hash = self._calculate_data_hash(data)

            # 检查是否为重复版本
            if await self._is_duplicate_version(data_hash):
                existing_version = await self._get_version_by_hash(data_hash)
                return {
                    'status': 'duplicate',
                    'version_id': existing_version['version_id'],
                    'message': '数据未发生变化，跳过版本创建'
                }

            # 确定版本类型
            version_type = VersionType(version_info.get('version_type', 'full'))
            parent_version = version_info.get('parent_version') or await self._get_latest_version_id()

            # 压缩和存储数据
            file_path = await self._store_version_data(version_id, data, version_type, parent_version)

            # 创建版本记录
            version = DataVersion(
                version_id=version_id,
                version_number=version_number,
                version_type=version_type,
                parent_version=parent_version,
                data_hash=data_hash,
                metadata=version_info.get('metadata', {}),
                created_at=datetime.now(),
                created_by=version_info.get('created_by', 'system'),
                description=version_info.get('description', ''),
                is_active=True,
                file_path=file_path,
                compressed_size=Path(file_path).stat().st_size if Path(file_path).exists() else 0,
                original_size=len(pickle.dumps(data))
            )

            # 保存到数据库
            await self._save_version_to_db(version)

            # 更新缓存
            with self._lock:
                self._version_cache[version_id] = version

            # 自动清理旧版本
            if self.auto_cleanup:
                await self._cleanup_old_versions()

            result = {
                'status': 'success',
                'version_id': version_id,
                'version_number': version_number,
                'data_hash': data_hash,
                'file_path': file_path,
                'compressed_size': version.compressed_size,
                'original_size': version.original_size,
                'compression_ratio': version.compressed_size / version.original_size if version.original_size > 0 else 0
            }

            self.logger.info(f"版本创建成功: {result}")
            return result

        except Exception as e:
            self.logger.error(f"版本创建失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'created_at': datetime.now().isoformat()
            }

    def _generate_version_id(self) -> str:
        """生成版本ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_suffix = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        return f"v_{timestamp}_{random_suffix}"

    def _generate_version_number(self) -> str:
        """生成版本号"""
        try:
            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT version_number FROM data_versions
                    WHERE branch_name = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (self.current_branch,))

                result = cursor.fetchone()
                if result:
                    last_version = result[0]
                    # 简单的版本号递增 (v1.0.0 -> v1.0.1)
                    parts = last_version.split('.')
                    if len(parts) == 3 and parts[0].startswith('v'):
                        major, minor, patch = int(parts[0][1:]), int(parts[1]), int(parts[2])
                        return f"v{major}.{minor}.{patch + 1}"

                return "v1.0.0"

        except Exception as e:
            self.logger.error(f"生成版本号失败: {e}")
            return f"v1.0.{int(datetime.now().timestamp())}"

    def _calculate_data_hash(self, data: Any) -> str:
        """计算数据哈希"""
        try:
            if isinstance(data, dict):
                # 对字典进行排序后序列化
                serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
            else:
                serialized = str(data)

            return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

        except Exception as e:
            self.logger.error(f"计算数据哈希失败: {e}")
            return hashlib.sha256(str(datetime.now()).encode()).hexdigest()

    async def _is_duplicate_version(self, data_hash: str) -> bool:
        """检查是否为重复版本"""
        try:
            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM data_versions
                    WHERE data_hash = ? AND is_active = 1
                ''', (data_hash,))

                return cursor.fetchone()[0] > 0

        except Exception as e:
            self.logger.error(f"检查重复版本失败: {e}")
            return False

    async def _get_version_by_hash(self, data_hash: str) -> Optional[Dict[str, Any]]:
        """根据哈希获取版本"""
        try:
            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT version_id, version_number, created_at
                    FROM data_versions
                    WHERE data_hash = ? AND is_active = 1
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (data_hash,))

                result = cursor.fetchone()
                if result:
                    return {
                        'version_id': result[0],
                        'version_number': result[1],
                        'created_at': result[2]
                    }

                return None

        except Exception as e:
            self.logger.error(f"根据哈希获取版本失败: {e}")
            return None

    async def _get_latest_version_id(self) -> Optional[str]:
        """获取最新版本ID"""
        try:
            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT version_id FROM data_versions
                    WHERE branch_name = ? AND is_active = 1
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (self.current_branch,))

                result = cursor.fetchone()
                return result[0] if result else None

        except Exception as e:
            self.logger.error(f"获取最新版本ID失败: {e}")
            return None

    async def _store_version_data(self, version_id: str, data: Any, version_type: VersionType, parent_version: Optional[str]) -> str:
        """存储版本数据"""
        try:
            # 选择存储格式和压缩算法
            if version_type == VersionType.INCREMENTAL and parent_version:
                # 增量存储：只存储差异
                parent_data = await self.get_version_data(parent_version)
                if parent_data:
                    diff_data = self._calculate_diff(parent_data, data)
                    data_to_store = diff_data
                else:
                    data_to_store = data
            else:
                # 全量存储
                data_to_store = data

            # 序列化数据
            serialized_data = pickle.dumps(data_to_store)

            # 压缩数据
            compressed_data = await self._compress_data(serialized_data)

            # 存储文件
            file_path = Path(self.version_storage_path) / f"{version_id}.dat"

            with open(file_path, 'wb') as f:
                f.write(compressed_data)

            return str(file_path)

        except Exception as e:
            self.logger.error(f"存储版本数据失败: {e}")
            raise

    async def _compress_data(self, data: bytes) -> bytes:
        """压缩数据"""
        try:
            algorithm = self.compression_algorithm

            if algorithm == 'auto':
                # 自动选择最佳压缩算法
                algorithm = self._select_best_compression(data)

            if algorithm == 'zstd' and ZSTD_AVAILABLE:
                compressor = zstd.ZstdCompressor(level=self.compression_level)
                return compressor.compress(data)
            elif algorithm == 'lz4' and LZ4_AVAILABLE:
                return lz4.frame.compress(data, compression_level=self.compression_level)
            else:
                # 默认使用gzip
                return gzip.compress(data, compresslevel=self.compression_level)

        except Exception as e:
            self.logger.error(f"数据压缩失败: {e}")
            return data

    def _select_best_compression(self, data: bytes) -> str:
        """选择最佳压缩算法"""
        data_size = len(data)

        if data_size < 1024:  # 小于1KB，不压缩
            return 'none'
        elif data_size < 1024 * 1024:  # 小于1MB，使用LZ4
            return 'lz4' if LZ4_AVAILABLE else 'gzip'
        else:  # 大于1MB，使用ZSTD
            return 'zstd' if ZSTD_AVAILABLE else 'gzip'

    def _calculate_diff(self, old_data: Any, new_data: Any) -> Dict[str, Any]:
        """计算数据差异"""
        try:
            if isinstance(old_data, dict) and isinstance(new_data, dict):
                return self._calculate_dict_diff(old_data, new_data)
            elif isinstance(old_data, list) and isinstance(new_data, list):
                return self._calculate_list_diff(old_data, new_data)
            else:
                return {
                    'type': 'replacement',
                    'old_value': old_data,
                    'new_value': new_data
                }

        except Exception as e:
            self.logger.error(f"计算差异失败: {e}")
            return {'type': 'error', 'error': str(e)}

    def _calculate_dict_diff(self, old_dict: Dict[str, Any], new_dict: Dict[str, Any]) -> Dict[str, Any]:
        """计算字典差异"""
        diff = {
            'type': 'dict_diff',
            'added': {},
            'modified': {},
            'deleted': {}
        }

        # 新增和修改的键
        for key, value in new_dict.items():
            if key not in old_dict:
                diff['added'][key] = value
            elif old_dict[key] != value:
                diff['modified'][key] = {
                    'old': old_dict[key],
                    'new': value
                }

        # 删除的键
        for key in old_dict:
            if key not in new_dict:
                diff['deleted'][key] = old_dict[key]

        return diff

    def _calculate_list_diff(self, old_list: List[Any], new_list: List[Any]) -> Dict[str, Any]:
        """计算列表差异"""
        # 简单的列表差异计算
        diff = {
            'type': 'list_diff',
            'added': [],
            'removed': [],
            'length_change': len(new_list) - len(old_list)
        }

        old_set = set(old_list) if all(isinstance(x, (str, int, float, bool)) for x in old_list) else old_list
        new_set = set(new_list) if all(isinstance(x, (str, int, float, bool)) for x in new_list) else new_list

        if isinstance(old_set, set) and isinstance(new_set, set):
            diff['added'] = list(new_set - old_set)
            diff['removed'] = list(old_set - new_set)
        else:
            # 复杂对象的简单比较
            diff['old_list'] = old_list
            diff['new_list'] = new_list

        return diff

    async def _save_version_to_db(self, version: DataVersion):
        """保存版本到数据库"""
        try:
            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO data_versions
                    (version_id, version_number, version_type, parent_version, data_hash,
                     metadata, created_at, created_by, description, is_active,
                     file_path, compressed_size, original_size, branch_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    version.version_id,
                    version.version_number,
                    version.version_type.value,
                    version.parent_version,
                    version.data_hash,
                    json.dumps(version.metadata),
                    version.created_at.isoformat(),
                    version.created_by,
                    version.description,
                    version.is_active,
                    version.file_path,
                    version.compressed_size,
                    version.original_size,
                    self.current_branch
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"保存版本到数据库失败: {e}")
            raise

    async def get_version_data(self, version_id: str) -> Optional[Any]:
        """获取版本数据"""
        try:
            # 检查缓存
            with self._lock:
                if version_id in self._version_cache:
                    cached_version = self._version_cache[version_id]
                    if Path(cached_version.file_path).exists():
                        return await self._load_version_data(cached_version)

            # 从数据库获取版本信息
            version_info = await self._get_version_info(version_id)
            if not version_info:
                return None

            # 加载数据
            version = DataVersion(**version_info)
            data = await self._load_version_data(version)

            # 更新缓存
            with self._lock:
                self._version_cache[version_id] = version

            return data

        except Exception as e:
            self.logger.error(f"获取版本数据失败: {e}")
            return None

    async def _get_version_info(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取版本信息"""
        try:
            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT version_id, version_number, version_type, parent_version,
                           data_hash, metadata, created_at, created_by, description,
                           is_active, file_path, compressed_size, original_size
                    FROM data_versions
                    WHERE version_id = ?
                ''', (version_id,))

                result = cursor.fetchone()
                if result:
                    return {
                        'version_id': result[0],
                        'version_number': result[1],
                        'version_type': VersionType(result[2]),
                        'parent_version': result[3],
                        'data_hash': result[4],
                        'metadata': json.loads(result[5]) if result[5] else {},
                        'created_at': datetime.fromisoformat(result[6]),
                        'created_by': result[7],
                        'description': result[8],
                        'is_active': bool(result[9]),
                        'file_path': result[10],
                        'compressed_size': result[11],
                        'original_size': result[12]
                    }

                return None

        except Exception as e:
            self.logger.error(f"获取版本信息失败: {e}")
            return None

    async def _load_version_data(self, version: DataVersion) -> Any:
        """加载版本数据"""
        try:
            if not Path(version.file_path).exists():
                raise FileNotFoundError(f"版本文件不存在: {version.file_path}")

            # 读取压缩数据
            with open(version.file_path, 'rb') as f:
                compressed_data = f.read()

            # 解压数据
            decompressed_data = await self._decompress_data(compressed_data)

            # 反序列化
            data = pickle.loads(decompressed_data)

            # 如果是增量版本，需要重建完整数据
            if version.version_type == VersionType.INCREMENTAL and version.parent_version:
                parent_data = await self.get_version_data(version.parent_version)
                if parent_data:
                    data = self._apply_diff(parent_data, data)

            return data

        except Exception as e:
            self.logger.error(f"加载版本数据失败: {e}")
            raise

    async def _decompress_data(self, compressed_data: bytes) -> bytes:
        """解压数据"""
        try:
            # 尝试不同的解压算法
            algorithms = ['zstd', 'lz4', 'gzip']

            for algorithm in algorithms:
                try:
                    if algorithm == 'zstd' and ZSTD_AVAILABLE:
                        decompressor = zstd.ZstdDecompressor()
                        return decompressor.decompress(compressed_data)
                    elif algorithm == 'lz4' and LZ4_AVAILABLE:
                        return lz4.frame.decompress(compressed_data)
                    elif algorithm == 'gzip':
                        return gzip.decompress(compressed_data)
                except:
                    continue

            # 如果所有解压尝试都失败，返回原始数据
            return compressed_data

        except Exception as e:
            self.logger.error(f"数据解压失败: {e}")
            return compressed_data

    def _apply_diff(self, base_data: Any, diff_data: Dict[str, Any]) -> Any:
        """应用差异到基础数据"""
        try:
            diff_type = diff_data.get('type')

            if diff_type == 'dict_diff':
                result = base_data.copy() if isinstance(base_data, dict) else {}

                # 应用新增
                result.update(diff_data.get('added', {}))

                # 应用修改
                for key, change in diff_data.get('modified', {}).items():
                    result[key] = change['new']

                # 应用删除
                for key in diff_data.get('deleted', {}):
                    result.pop(key, None)

                return result

            elif diff_type == 'list_diff':
                # 简单的列表差异应用
                if 'new_list' in diff_data:
                    return diff_data['new_list']
                else:
                    result = base_data.copy() if isinstance(base_data, list) else []
                    # 更复杂的列表差异应用逻辑
                    return result

            elif diff_type == 'replacement':
                return diff_data['new_value']

            else:
                return base_data

        except Exception as e:
            self.logger.error(f"应用差异失败: {e}")
            return base_data

    async def rollback_to_version(self, version_id: str, rollback_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """回滚到指定版本"""
        try:
            options = rollback_options or {}

            # 获取目标版本数据
            target_data = await self.get_version_data(version_id)
            if target_data is None:
                return {
                    'status': 'error',
                    'error': f"版本 {version_id} 不存在或无法访问"
                }

            # 创建回滚版本
            current_time = datetime.now()
            rollback_version_info = {
                'version_number': f"rollback_{version_id}_{current_time.strftime('%Y%m%d_%H%M%S')}",
                'version_type': 'full',
                'description': f"回滚到版本 {version_id}",
                'created_by': options.get('created_by', 'system'),
                'metadata': {
                    'rollback_target': version_id,
                    'rollback_reason': options.get('reason', ''),
                    'original_branch': self.current_branch
                }
            }

            rollback_result = await self.create_version(target_data, rollback_version_info)

            if rollback_result['status'] == 'success':
                # 如果需要，可以将当前分支头指向回滚版本
                if options.get('update_branch_head', True):
                    await self._update_branch_head(self.current_branch, rollback_result['version_id'])

                return {
                    'status': 'success',
                    'rollback_version_id': rollback_result['version_id'],
                    'target_version_id': version_id,
                    'rollback_time': current_time.isoformat(),
                    'message': f"成功回滚到版本 {version_id}"
                }
            else:
                return rollback_result

        except Exception as e:
            self.logger.error(f"版本回滚失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'rollback_time': datetime.now().isoformat()
            }

    async def compare_versions(self, version1_id: str, version2_id: str) -> Dict[str, Any]:
        """比较两个版本"""
        try:
            # 检查差异缓存
            diff_key = f"{version1_id}:{version2_id}"
            with self._lock:
                if diff_key in self._diff_cache:
                    return self._diff_cache[diff_key]

            # 获取版本数据
            data1 = await self.get_version_data(version1_id)
            data2 = await self.get_version_data(version2_id)

            if data1 is None or data2 is None:
                return {
                    'status': 'error',
                    'error': '无法获取版本数据进行比较'
                }

            # 计算差异
            diff_result = self._calculate_detailed_diff(data1, data2)

            result = {
                'status': 'success',
                'from_version': version1_id,
                'to_version': version2_id,
                'comparison_time': datetime.now().isoformat(),
                'diff': diff_result,
                'summary': {
                    'has_changes': len(diff_result.get('added', [])) > 0 or
                                  len(diff_result.get('modified', [])) > 0 or
                                  len(diff_result.get('deleted', [])) > 0,
                    'added_count': len(diff_result.get('added', [])),
                    'modified_count': len(diff_result.get('modified', [])),
                    'deleted_count': len(diff_result.get('deleted', []))
                }
            }

            # 缓存结果
            with self._lock:
                self._diff_cache[diff_key] = result

            return result

        except Exception as e:
            self.logger.error(f"版本比较失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'comparison_time': datetime.now().isoformat()
            }

    def _calculate_detailed_diff(self, data1: Any, data2: Any) -> Dict[str, Any]:
        """计算详细差异"""
        if isinstance(data1, dict) and isinstance(data2, dict):
            return self._calculate_dict_diff(data1, data2)
        elif isinstance(data1, list) and isinstance(data2, list):
            return self._calculate_list_diff(data1, data2)
        else:
            return {
                'type': 'value_change',
                'old_value': data1,
                'new_value': data2,
                'changed': data1 != data2
            }

    async def list_versions(self, list_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """列出版本"""
        try:
            options = list_options or {}
            branch = options.get('branch', self.current_branch)
            limit = options.get('limit', 50)
            offset = options.get('offset', 0)

            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()

                # 构建查询条件
                where_clause = "WHERE is_active = 1"
                params = []

                if branch:
                    where_clause += " AND branch_name = ?"
                    params.append(branch)

                # 获取版本列表
                cursor.execute(f'''
                    SELECT version_id, version_number, version_type, created_at,
                           created_by, description, compressed_size, original_size
                    FROM data_versions
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', params + [limit, offset])

                versions = []
                for row in cursor.fetchall():
                    versions.append({
                        'version_id': row[0],
                        'version_number': row[1],
                        'version_type': row[2],
                        'created_at': row[3],
                        'created_by': row[4],
                        'description': row[5],
                        'compressed_size': row[6],
                        'original_size': row[7]
                    })

                # 获取总数
                cursor.execute(f'''
                    SELECT COUNT(*) FROM data_versions {where_clause}
                ''', params)
                total_count = cursor.fetchone()[0]

                return {
                    'status': 'success',
                    'versions': versions,
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'branch': branch
                }

        except Exception as e:
            self.logger.error(f"列出版本失败: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def _cleanup_old_versions(self):
        """清理旧版本"""
        try:
            if not self.auto_cleanup:
                return

            with sqlite3.connect(self.version_db_path) as conn:
                cursor = conn.cursor()

                # 获取每个分支的版本数
                cursor.execute('''
                    SELECT branch_name, COUNT(*)
                    FROM data_versions
                    WHERE is_active = 1
                    GROUP BY branch_name
                ''')

                for branch_name, count in cursor.fetchall():
                    if count > self.max_versions:
                        # 获取需要删除的版本
                        versions_to_delete = count - self.max_versions
                        cursor.execute('''
                            SELECT version_id, file_path
                            FROM data_versions
                            WHERE branch_name = ? AND is_active = 1
                            ORDER BY created_at ASC
                            LIMIT ?
                        ''', (branch_name, versions_to_delete))

                        # 删除版本文件和记录
                        for version_id, file_path in cursor.fetchall():
                            # 删除文件
                            try:
                                if Path(file_path).exists():
                                    Path(file_path).unlink()
                            except:
                                pass

                            # 标记为非活跃
                            cursor.execute('''
                                UPDATE data_versions
                                SET is_active = 0
                                WHERE version_id = ?
                            ''', (version_id,))

                conn.commit()

            self.logger.info("旧版本清理完成")

        except Exception as e:
            self.logger.error(f"清理旧版本失败: {e}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)

            self.logger.info("版本控制器资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")


async def main():
    """测试主函数"""
    config = {
        'version_db_path': 'data/test_versions.db',
        'version_storage_path': 'data/test_versions/',
        'max_versions': 10,
        'auto_cleanup': True,
        'compression_algorithm': 'auto'
    }

    async with VersionController(config) as controller:
        # 测试数据
        test_data_v1 = {
            'company': '测试公司',
            'accounts': [
                {'code': '1001', 'name': '库存现金', 'balance': 10000},
                {'code': '1002', 'name': '银行存款', 'balance': 50000}
            ]
        }

        test_data_v2 = {
            'company': '测试公司',
            'accounts': [
                {'code': '1001', 'name': '库存现金', 'balance': 15000},  # 修改
                {'code': '1002', 'name': '银行存款', 'balance': 50000},
                {'code': '1003', 'name': '应收账款', 'balance': 20000}  # 新增
            ]
        }

        # 创建版本1
        result1 = await controller.create_version(test_data_v1, {
            'description': '初始版本',
            'created_by': 'test_user'
        })
        print(f"版本1创建结果: {json.dumps(result1, indent=2, ensure_ascii=False)}")

        # 创建版本2
        result2 = await controller.create_version(test_data_v2, {
            'description': '更新版本',
            'created_by': 'test_user',
            'version_type': 'incremental'
        })
        print(f"版本2创建结果: {json.dumps(result2, indent=2, ensure_ascii=False)}")

        # 比较版本
        if result1['status'] == 'success' and result2['status'] == 'success':
            diff_result = await controller.compare_versions(result1['version_id'], result2['version_id'])
            print(f"版本比较结果: {json.dumps(diff_result, indent=2, ensure_ascii=False)}")

            # 回滚测试
            rollback_result = await controller.rollback_to_version(result1['version_id'])
            print(f"回滚结果: {json.dumps(rollback_result, indent=2, ensure_ascii=False)}")

        # 列出版本
        versions_list = await controller.list_versions()
        print(f"版本列表: {json.dumps(versions_list, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())