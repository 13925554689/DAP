"""
DAP v2.0 - Model Version Manager
模型版本管理器 - 完整的版本控制和回滚
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import shutil
import hashlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

logger = logging.getLogger(__name__)


class ModelVersionManager:
    """模型版本管理器"""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path(settings.AI_MODEL_PATH)
        self.versions_file = self.model_path / 'versions.json'
        self.versions_dir = self.model_path / 'versions'
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        # 加载版本信息
        self.versions = self._load_versions()

    def _load_versions(self) -> Dict[str, Any]:
        """加载版本信息"""
        if self.versions_file.exists():
            try:
                with open(self.versions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load versions: {e}")
        return {}

    def _save_versions(self):
        """保存版本信息"""
        try:
            self.versions_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.versions_file, 'w', encoding='utf-8') as f:
                json.dump(self.versions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save versions: {e}")

    def register_new_version(
        self,
        model_type: str,
        model_file: Path,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        注册新模型版本

        Args:
            model_type: 模型类型
            model_file: 模型文件路径
            metadata: 模型元数据

        Returns:
            版本信息
        """
        try:
            # 获取下一个版本号
            version_number = self._get_next_version(model_type)

            # 计算文件哈希
            file_hash = self._calculate_file_hash(model_file)

            # 创建版本目录
            version_dir = self.versions_dir / model_type / f"v{version_number}"
            version_dir.mkdir(parents=True, exist_ok=True)

            # 复制模型文件
            target_file = version_dir / model_file.name
            shutil.copy2(model_file, target_file)

            # 创建版本记录
            version_info = {
                'version': version_number,
                'model_type': model_type,
                'file_path': str(target_file),
                'file_hash': file_hash,
                'file_size': model_file.stat().st_size,
                'created_at': datetime.now().isoformat(),
                'metadata': metadata,
                'status': 'active'
            }

            # 保存版本元数据
            metadata_file = version_dir / 'metadata.json'
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(version_info, f, indent=2, ensure_ascii=False)

            # 更新版本列表
            if model_type not in self.versions:
                self.versions[model_type] = {
                    'current_version': version_number,
                    'versions': []
                }

            self.versions[model_type]['versions'].append(version_info)
            self.versions[model_type]['current_version'] = version_number
            self._save_versions()

            logger.info(f"Registered new version {version_number} for {model_type}")

            return {
                'success': True,
                'version': version_number,
                'version_info': version_info
            }

        except Exception as e:
            logger.error(f"Failed to register version: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def rollback_to_version(
        self,
        model_type: str,
        target_version: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        回滚到指定版本

        Args:
            model_type: 模型类型
            target_version: 目标版本号
            reason: 回滚原因

        Returns:
            回滚结果
        """
        try:
            if model_type not in self.versions:
                return {
                    'success': False,
                    'error': f'No versions found for {model_type}'
                }

            model_versions = self.versions[model_type]
            current_version = model_versions['current_version']

            # 查找目标版本
            target_version_info = None
            for v in model_versions['versions']:
                if v['version'] == target_version:
                    target_version_info = v
                    break

            if not target_version_info:
                return {
                    'success': False,
                    'error': f'Version {target_version} not found'
                }

            # 验证文件存在
            version_file = Path(target_version_info['file_path'])
            if not version_file.exists():
                return {
                    'success': False,
                    'error': f'Version file not found: {version_file}'
                }

            # 创建回滚记录
            rollback_record = {
                'from_version': current_version,
                'to_version': target_version,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }

            # 更新当前版本
            model_versions['current_version'] = target_version

            # 添加回滚历史
            if 'rollback_history' not in model_versions:
                model_versions['rollback_history'] = []
            model_versions['rollback_history'].append(rollback_record)

            self._save_versions()

            logger.info(f"Rolled back {model_type} from v{current_version} to v{target_version}")

            return {
                'success': True,
                'from_version': current_version,
                'to_version': target_version,
                'rollback_record': rollback_record
            }

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_version_info(
        self,
        model_type: str,
        version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取版本信息

        Args:
            model_type: 模型类型
            version: 版本号(None表示当前版本)

        Returns:
            版本信息
        """
        try:
            if model_type not in self.versions:
                return {
                    'error': f'No versions found for {model_type}'
                }

            model_versions = self.versions[model_type]

            if version is None:
                version = model_versions['current_version']

            # 查找版本
            for v in model_versions['versions']:
                if v['version'] == version:
                    return v

            return {
                'error': f'Version {version} not found'
            }

        except Exception as e:
            logger.error(f"Failed to get version info: {e}")
            return {
                'error': str(e)
            }

    def list_versions(
        self,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        列出所有版本

        Args:
            model_type: 模型类型(None表示所有类型)

        Returns:
            版本列表
        """
        try:
            if model_type:
                if model_type not in self.versions:
                    return {
                        'model_type': model_type,
                        'versions': [],
                        'total': 0
                    }

                model_versions = self.versions[model_type]
                return {
                    'model_type': model_type,
                    'current_version': model_versions['current_version'],
                    'versions': model_versions['versions'],
                    'total': len(model_versions['versions']),
                    'rollback_history': model_versions.get('rollback_history', [])
                }
            else:
                # 所有模型类型
                all_versions = {}
                for mt in self.versions.keys():
                    all_versions[mt] = self.list_versions(mt)

                return {
                    'total_models': len(self.versions),
                    'models': all_versions
                }

        except Exception as e:
            logger.error(f"Failed to list versions: {e}")
            return {
                'error': str(e)
            }

    def compare_versions(
        self,
        model_type: str,
        version_a: int,
        version_b: int
    ) -> Dict[str, Any]:
        """
        比较两个版本

        Args:
            model_type: 模型类型
            version_a: 版本A
            version_b: 版本B

        Returns:
            比较结果
        """
        try:
            if model_type not in self.versions:
                return {
                    'error': f'No versions found for {model_type}'
                }

            # 获取两个版本的信息
            version_a_info = self.get_version_info(model_type, version_a)
            version_b_info = self.get_version_info(model_type, version_b)

            if 'error' in version_a_info or 'error' in version_b_info:
                return {
                    'error': 'One or both versions not found'
                }

            # 比较元数据
            metadata_a = version_a_info.get('metadata', {})
            metadata_b = version_b_info.get('metadata', {})

            comparison = {
                'model_type': model_type,
                'version_a': {
                    'version': version_a,
                    'created_at': version_a_info['created_at'],
                    'file_size': version_a_info['file_size'],
                    'accuracy': metadata_a.get('accuracy'),
                    'sample_count': metadata_a.get('sample_count')
                },
                'version_b': {
                    'version': version_b,
                    'created_at': version_b_info['created_at'],
                    'file_size': version_b_info['file_size'],
                    'accuracy': metadata_b.get('accuracy'),
                    'sample_count': metadata_b.get('sample_count')
                },
                'differences': {}
            }

            # 计算差异
            if metadata_a.get('accuracy') and metadata_b.get('accuracy'):
                comparison['differences']['accuracy_delta'] = \
                    metadata_b.get('accuracy') - metadata_a.get('accuracy')

            if metadata_a.get('sample_count') and metadata_b.get('sample_count'):
                comparison['differences']['sample_delta'] = \
                    metadata_b.get('sample_count') - metadata_a.get('sample_count')

            # 推荐
            if comparison['differences'].get('accuracy_delta', 0) > 0:
                comparison['recommendation'] = f'version_{version_b}'
                comparison['reason'] = 'Higher accuracy'
            elif comparison['differences'].get('accuracy_delta', 0) < 0:
                comparison['recommendation'] = f'version_{version_a}'
                comparison['reason'] = 'Higher accuracy'
            else:
                comparison['recommendation'] = f'version_{version_b}'
                comparison['reason'] = 'Newer version'

            return comparison

        except Exception as e:
            logger.error(f"Version comparison failed: {e}")
            return {
                'error': str(e)
            }

    def delete_version(
        self,
        model_type: str,
        version: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        删除指定版本

        Args:
            model_type: 模型类型
            version: 版本号
            force: 是否强制删除(即使是当前版本)

        Returns:
            删除结果
        """
        try:
            if model_type not in self.versions:
                return {
                    'success': False,
                    'error': f'No versions found for {model_type}'
                }

            model_versions = self.versions[model_type]
            current_version = model_versions['current_version']

            # 不能删除当前版本(除非force=True)
            if version == current_version and not force:
                return {
                    'success': False,
                    'error': 'Cannot delete current version (use force=True)'
                }

            # 查找并删除版本
            version_info = None
            for i, v in enumerate(model_versions['versions']):
                if v['version'] == version:
                    version_info = model_versions['versions'].pop(i)
                    break

            if not version_info:
                return {
                    'success': False,
                    'error': f'Version {version} not found'
                }

            # 删除文件
            version_dir = Path(version_info['file_path']).parent
            if version_dir.exists():
                shutil.rmtree(version_dir)

            self._save_versions()

            logger.info(f"Deleted version {version} of {model_type}")

            return {
                'success': True,
                'deleted_version': version
            }

        except Exception as e:
            logger.error(f"Failed to delete version: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def cleanup_old_versions(
        self,
        model_type: str,
        keep_last_n: int = 5
    ) -> Dict[str, Any]:
        """
        清理旧版本,只保留最近N个

        Args:
            model_type: 模型类型
            keep_last_n: 保留最近N个版本

        Returns:
            清理结果
        """
        try:
            if model_type not in self.versions:
                return {
                    'success': False,
                    'error': f'No versions found for {model_type}'
                }

            model_versions = self.versions[model_type]
            versions_list = model_versions['versions']
            current_version = model_versions['current_version']

            # 按版本号排序
            sorted_versions = sorted(versions_list, key=lambda x: x['version'], reverse=True)

            # 确定要删除的版本
            to_delete = []
            for v in sorted_versions[keep_last_n:]:
                # 不删除当前版本
                if v['version'] != current_version:
                    to_delete.append(v['version'])

            # 执行删除
            deleted_count = 0
            for version in to_delete:
                result = self.delete_version(model_type, version, force=False)
                if result.get('success'):
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} old versions of {model_type}")

            return {
                'success': True,
                'deleted_count': deleted_count,
                'deleted_versions': to_delete,
                'remaining_count': len(model_versions['versions']) - deleted_count
            }

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_next_version(self, model_type: str) -> int:
        """获取下一个版本号"""
        if model_type not in self.versions:
            return 1

        versions = self.versions[model_type]['versions']
        if not versions:
            return 1

        max_version = max(v['version'] for v in versions)
        return max_version + 1

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件SHA256哈希"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_rollback_history(
        self,
        model_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取回滚历史"""
        if model_type not in self.versions:
            return []

        history = self.versions[model_type].get('rollback_history', [])
        return history[-limit:]


# 全局实例
_version_manager = None


def get_version_manager() -> ModelVersionManager:
    """获取版本管理器单例"""
    global _version_manager
    if _version_manager is None:
        _version_manager = ModelVersionManager()
    return _version_manager
