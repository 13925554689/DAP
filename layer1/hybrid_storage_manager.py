#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hybrid Storage Manager - 混合存储管理器
实现数据湖 + 数据仓库 + 缓存的三层存储架构

存储层次：
1. 数据湖 (Data Lake) - 原始数据长期存储 (MinIO/S3)
2. 数据仓库 (Data Warehouse) - 结构化数据高性能存储 (TiDB/SQLite)
3. 缓存层 (Cache) - 热点数据快速访问 (Redis/内存)
"""

import asyncio
import logging
import os
import time
import json
import pickle
import zstandard as zstd  # 高效压缩
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor

# 导入基础存储管理器
try:
    from .storage_manager import StorageManager
except ImportError:
    from storage_manager import StorageManager

# 缓存相关导入
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# 对象存储相关导入
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False

logger = logging.getLogger(__name__)

class DataLakeManager:
    """数据湖管理器 - 处理原始数据的长期存储"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.storage_path = Path(self.config.get('data_lake_path', 'data/lake'))
        self.compression_level = self.config.get('compression_level', 3)
        self.retention_days = self.config.get('retention_days', 2555)  # 7年

        # 确保存储目录存在
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 压缩器
        self.compressor = zstd.ZstdCompressor(level=self.compression_level)
        self.decompressor = zstd.ZstdDecompressor()

        # MinIO客户端（如果可用）
        self.minio_client = None
        if MINIO_AVAILABLE and self.config.get('minio_enabled', False):
            self._init_minio_client()

        logger.info(f"Data Lake Manager initialized: {self.storage_path}")

    def _init_minio_client(self):
        """初始化MinIO客户端"""
        try:
            self.minio_client = Minio(
                self.config.get('minio_endpoint', 'localhost:9000'),
                access_key=self.config.get('minio_access_key', 'minioadmin'),
                secret_key=self.config.get('minio_secret_key', 'minioadmin'),
                secure=self.config.get('minio_secure', False)
            )

            # 确保bucket存在
            bucket_name = self.config.get('minio_bucket', 'dap-data-lake')
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)

            logger.info("MinIO client initialized successfully")

        except Exception as e:
            logger.warning(f"Failed to initialize MinIO client: {e}")
            self.minio_client = None

    async def store_raw_data(self, data_id: str, data: Dict[str, Any], metadata: Dict[str, Any] = None) -> str:
        """
        存储原始数据到数据湖

        Args:
            data_id: 数据唯一标识
            data: 原始数据
            metadata: 元数据

        Returns:
            存储路径
        """
        try:
            # 生成存储路径
            timestamp = datetime.now().strftime('%Y/%m/%d')
            storage_key = f"{timestamp}/{data_id}"

            # 准备数据包
            data_package = {
                'data': data,
                'metadata': metadata or {},
                'stored_at': datetime.now().isoformat(),
                'version': '1.0'
            }

            # 序列化和压缩
            serialized_data = pickle.dumps(data_package)
            compressed_data = self.compressor.compress(serialized_data)

            if self.minio_client:
                # 存储到MinIO
                storage_path = await self._store_to_minio(storage_key, compressed_data)
            else:
                # 存储到本地文件系统
                storage_path = await self._store_to_local(storage_key, compressed_data)

            logger.info(f"Raw data stored successfully: {storage_path}")
            return storage_path

        except Exception as e:
            logger.error(f"Failed to store raw data {data_id}: {e}")
            raise

    async def _store_to_minio(self, storage_key: str, compressed_data: bytes) -> str:
        """存储到MinIO"""
        bucket_name = self.config.get('minio_bucket', 'dap-data-lake')
        object_name = f"{storage_key}.zst"

        try:
            from io import BytesIO
            data_stream = BytesIO(compressed_data)

            self.minio_client.put_object(
                bucket_name,
                object_name,
                data_stream,
                len(compressed_data),
                content_type='application/octet-stream'
            )

            return f"minio://{bucket_name}/{object_name}"

        except Exception as e:
            logger.error(f"MinIO storage failed: {e}")
            raise

    async def _store_to_local(self, storage_key: str, compressed_data: bytes) -> str:
        """存储到本地文件系统"""
        file_path = self.storage_path / f"{storage_key}.zst"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, 'wb') as f:
                f.write(compressed_data)

            return str(file_path)

        except Exception as e:
            logger.error(f"Local storage failed: {e}")
            raise

    async def retrieve_raw_data(self, storage_path: str) -> Dict[str, Any]:
        """从数据湖检索原始数据"""
        try:
            if storage_path.startswith('minio://'):
                compressed_data = await self._retrieve_from_minio(storage_path)
            else:
                compressed_data = await self._retrieve_from_local(storage_path)

            # 解压缩和反序列化
            decompressed_data = self.decompressor.decompress(compressed_data)
            data_package = pickle.loads(decompressed_data)

            return data_package

        except Exception as e:
            logger.error(f"Failed to retrieve raw data from {storage_path}: {e}")
            raise

    async def _retrieve_from_minio(self, storage_path: str) -> bytes:
        """从MinIO检索数据"""
        # 解析MinIO路径
        path_parts = storage_path.replace('minio://', '').split('/', 1)
        bucket_name = path_parts[0]
        object_name = path_parts[1]

        try:
            response = self.minio_client.get_object(bucket_name, object_name)
            return response.read()

        except Exception as e:
            logger.error(f"MinIO retrieval failed: {e}")
            raise

    async def _retrieve_from_local(self, storage_path: str) -> bytes:
        """从本地文件系统检索数据"""
        try:
            with open(storage_path, 'rb') as f:
                return f.read()

        except Exception as e:
            logger.error(f"Local retrieval failed: {e}")
            raise

    async def cleanup_expired_data(self):
        """清理过期数据"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        if self.minio_client:
            await self._cleanup_minio_expired_data(cutoff_date)
        else:
            await self._cleanup_local_expired_data(cutoff_date)

    async def _cleanup_local_expired_data(self, cutoff_date: datetime):
        """清理本地过期数据"""
        try:
            expired_files = []

            for file_path in self.storage_path.glob('**/*.zst'):
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    expired_files.append(file_path)

            for file_path in expired_files:
                file_path.unlink()
                logger.info(f"Deleted expired file: {file_path}")

            logger.info(f"Cleaned up {len(expired_files)} expired files")

        except Exception as e:
            logger.error(f"Local cleanup failed: {e}")

class DataWarehouseManager:
    """数据仓库管理器 - 处理结构化数据的高性能存储"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.db_path = self.config.get('warehouse_db_path', 'data/warehouse/dap_warehouse.db')
        self.connection_pool_size = self.config.get('connection_pool_size', 5)

        # 确保数据库目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # 连接池
        self.connection_pool = []
        self.pool_lock = threading.Lock()
        self._init_connection_pool()

        # 初始化数据仓库结构
        self._init_warehouse_schema()

        logger.info(f"Data Warehouse Manager initialized: {self.db_path}")

    def _init_connection_pool(self):
        """初始化连接池"""
        with self.pool_lock:
            for _ in range(self.connection_pool_size):
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute('PRAGMA journal_mode=WAL')  # 启用WAL模式提高并发性能
                conn.execute('PRAGMA synchronous=NORMAL')  # 平衡性能和安全性
                conn.execute('PRAGMA cache_size=10000')  # 增加缓存大小
                self.connection_pool.append(conn)

    def _get_connection(self) -> sqlite3.Connection:
        """从连接池获取连接"""
        with self.pool_lock:
            if self.connection_pool:
                return self.connection_pool.pop()
            else:
                # 如果池为空，创建新连接
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA cache_size=10000')
                return conn

    def _return_connection(self, conn: sqlite3.Connection):
        """将连接返回池"""
        with self.pool_lock:
            if len(self.connection_pool) < self.connection_pool_size:
                self.connection_pool.append(conn)
            else:
                conn.close()

    def _init_warehouse_schema(self):
        """初始化数据仓库结构"""
        conn = self._get_connection()
        try:
            # 创建元数据表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS data_catalog (
                    catalog_id TEXT PRIMARY KEY,
                    table_name TEXT NOT NULL,
                    schema_info TEXT,
                    data_source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    record_count INTEGER,
                    quality_score REAL
                )
            ''')

            # 创建数据血缘表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS data_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    source_table TEXT,
                    target_table TEXT,
                    transformation_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建质量监控表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    metric_id TEXT PRIMARY KEY,
                    table_name TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to initialize warehouse schema: {e}")
            raise
        finally:
            self._return_connection(conn)

    async def store_structured_data(self, table_name: str, data: pd.DataFrame,
                                  schema_info: Dict[str, Any], metadata: Dict[str, Any] = None) -> str:
        """
        存储结构化数据到数据仓库

        Args:
            table_name: 表名
            data: 结构化数据
            schema_info: 模式信息
            metadata: 元数据

        Returns:
            catalog_id
        """
        try:
            catalog_id = f"{table_name}_{int(time.time())}"

            conn = self._get_connection()
            try:
                # 创建表
                await self._create_table_from_schema(conn, table_name, schema_info)

                # 插入数据
                data.to_sql(table_name, conn, if_exists='replace', index=False)

                # 记录到数据目录
                conn.execute('''
                    INSERT OR REPLACE INTO data_catalog
                    (catalog_id, table_name, schema_info, data_source, record_count, quality_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    catalog_id,
                    table_name,
                    json.dumps(schema_info),
                    metadata.get('data_source', 'unknown') if metadata else 'unknown',
                    len(data),
                    metadata.get('quality_score', 0.0) if metadata else 0.0
                ))

                conn.commit()

                logger.info(f"Structured data stored successfully: {table_name} (catalog_id: {catalog_id})")
                return catalog_id

            finally:
                self._return_connection(conn)

        except Exception as e:
            logger.error(f"Failed to store structured data {table_name}: {e}")
            raise

    async def _create_table_from_schema(self, conn: sqlite3.Connection, table_name: str, schema_info: Dict[str, Any]):
        """根据模式信息创建表"""
        try:
            columns = schema_info.get('columns', {})
            if not columns:
                return

            # 构建CREATE TABLE语句
            column_definitions = []
            for col_name, col_info in columns.items():
                col_type = self._map_data_type(col_info.get('data_type', 'TEXT'))
                constraints = col_info.get('constraints', [])

                col_def = f'"{col_name}" {col_type}'

                if 'NOT NULL' in constraints:
                    col_def += ' NOT NULL'
                if 'UNIQUE' in constraints:
                    col_def += ' UNIQUE'

                column_definitions.append(col_def)

            create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(column_definitions)})'

            conn.execute(create_sql)

            # 创建索引
            await self._create_indexes(conn, table_name, schema_info)

        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            raise

    def _map_data_type(self, pandas_dtype: str) -> str:
        """映射pandas数据类型到SQLite类型"""
        type_mapping = {
            'int64': 'INTEGER',
            'float64': 'REAL',
            'object': 'TEXT',
            'bool': 'INTEGER',
            'datetime64[ns]': 'TIMESTAMP',
            'category': 'TEXT'
        }

        return type_mapping.get(pandas_dtype, 'TEXT')

    async def _create_indexes(self, conn: sqlite3.Connection, table_name: str, schema_info: Dict[str, Any]):
        """创建索引"""
        try:
            columns = schema_info.get('columns', {})

            for col_name, col_info in columns.items():
                semantic_type = col_info.get('semantic_type', 'unknown')

                # 为重要字段创建索引
                if semantic_type in ['account_code', 'voucher_no', 'customer', 'date']:
                    index_name = f'idx_{table_name}_{col_name}'
                    conn.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{col_name}")')

        except Exception as e:
            logger.warning(f"Failed to create indexes for {table_name}: {e}")

    async def query_data(self, sql: str, params: tuple = None) -> pd.DataFrame:
        """查询数据"""
        conn = self._get_connection()
        try:
            if params:
                return pd.read_sql_query(sql, conn, params=params)
            else:
                return pd.read_sql_query(sql, conn)

        finally:
            self._return_connection(conn)

    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息"""
        conn = self._get_connection()
        try:
            cursor = conn.execute('''
                SELECT * FROM data_catalog WHERE table_name = ?
            ''', (table_name,))

            row = cursor.fetchone()
            if row:
                return {
                    'catalog_id': row[0],
                    'table_name': row[1],
                    'schema_info': json.loads(row[2]) if row[2] else {},
                    'data_source': row[3],
                    'created_at': row[4],
                    'updated_at': row[5],
                    'record_count': row[6],
                    'quality_score': row[7]
                }
            else:
                return {}

        finally:
            self._return_connection(conn)

class CacheManager:
    """缓存管理器 - 处理热点数据的快速访问"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.cache_type = self.config.get('cache_type', 'memory')  # memory 或 redis
        self.ttl_seconds = self.config.get('ttl_seconds', 3600)  # 1小时
        self.max_memory_items = self.config.get('max_memory_items', 1000)

        # 内存缓存
        self.memory_cache = {}
        self.cache_timestamps = {}
        self.cache_lock = threading.Lock()

        # Redis缓存
        self.redis_client = None
        if self.cache_type == 'redis' and REDIS_AVAILABLE:
            self._init_redis_client()

        logger.info(f"Cache Manager initialized: {self.cache_type}")

    def _init_redis_client(self):
        """初始化Redis客户端"""
        try:
            self.redis_client = redis.Redis(
                host=self.config.get('redis_host', 'localhost'),
                port=self.config.get('redis_port', 6379),
                db=self.config.get('redis_db', 0),
                decode_responses=False
            )

            # 测试连接
            self.redis_client.ping()
            logger.info("Redis client initialized successfully")

        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {e}")
            self.redis_client = None
            self.cache_type = 'memory'

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        try:
            if self.cache_type == 'redis' and self.redis_client:
                return await self._get_from_redis(key)
            else:
                return await self._get_from_memory(key)

        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存数据"""
        try:
            ttl = ttl or self.ttl_seconds

            if self.cache_type == 'redis' and self.redis_client:
                return await self._set_to_redis(key, value, ttl)
            else:
                return await self._set_to_memory(key, value, ttl)

        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False

    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """从Redis获取数据"""
        try:
            data = self.redis_client.get(key)
            if data:
                return pickle.loads(data)
            return None

        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    async def _set_to_redis(self, key: str, value: Any, ttl: int) -> bool:
        """设置数据到Redis"""
        try:
            serialized_value = pickle.dumps(value)
            self.redis_client.setex(key, ttl, serialized_value)
            return True

        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            return False

    async def _get_from_memory(self, key: str) -> Optional[Any]:
        """从内存获取数据"""
        with self.cache_lock:
            if key in self.memory_cache:
                # 检查是否过期
                timestamp = self.cache_timestamps.get(key, 0)
                if time.time() - timestamp < self.ttl_seconds:
                    return self.memory_cache[key]
                else:
                    # 移除过期数据
                    del self.memory_cache[key]
                    del self.cache_timestamps[key]

            return None

    async def _set_to_memory(self, key: str, value: Any, ttl: int) -> bool:
        """设置数据到内存"""
        with self.cache_lock:
            # 检查内存限制
            if len(self.memory_cache) >= self.max_memory_items:
                # 移除最旧的项
                oldest_key = min(self.cache_timestamps, key=self.cache_timestamps.get)
                del self.memory_cache[oldest_key]
                del self.cache_timestamps[oldest_key]

            self.memory_cache[key] = value
            self.cache_timestamps[key] = time.time()
            return True

    async def invalidate(self, key: str):
        """使缓存失效"""
        try:
            if self.cache_type == 'redis' and self.redis_client:
                self.redis_client.delete(key)
            else:
                with self.cache_lock:
                    self.memory_cache.pop(key, None)
                    self.cache_timestamps.pop(key, None)

        except Exception as e:
            logger.warning(f"Cache invalidation failed for key {key}: {e}")

    async def clear_all(self):
        """清空所有缓存"""
        try:
            if self.cache_type == 'redis' and self.redis_client:
                self.redis_client.flushdb()
            else:
                with self.cache_lock:
                    self.memory_cache.clear()
                    self.cache_timestamps.clear()

            logger.info("All cache cleared")

        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")

class HybridStorageManager:
    """混合存储管理器 - 统一管理三层存储"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 初始化三层存储
        self.data_lake = DataLakeManager(self.config.get('data_lake', {}))
        self.data_warehouse = DataWarehouseManager(self.config.get('data_warehouse', {}))
        self.cache = CacheManager(self.config.get('cache', {}))

        # 基础存储管理器（向下兼容）
        try:
            self.base_storage = StorageManager(self.config.get('base_storage_path', 'data/dap_data.db'))
        except:
            self.base_storage = None

        # 存储策略配置
        self.storage_strategy = {
            'auto_cache_threshold': self.config.get('auto_cache_threshold', 1000),  # 记录数阈值
            'warehouse_retention_days': self.config.get('warehouse_retention_days', 365),  # 1年
            'lake_compression_ratio': self.config.get('lake_compression_ratio', 0.3)  # 压缩比阈值
        }

        self.logger.info("Hybrid Storage Manager initialized")

    async def store_intelligently(self, cleaned_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能存储清洗后的数据

        Args:
            cleaned_data: 清洗后的数据
            schema: 数据模式

        Returns:
            存储结果
        """
        self.logger.info("Starting intelligent data storage")

        try:
            storage_result = {
                'data_lake_paths': {},
                'warehouse_catalog_ids': {},
                'cached_tables': [],
                'storage_metrics': {},
                'strategy_decisions': {}
            }

            for table_name, table_data in cleaned_data.items():
                if isinstance(table_data, pd.DataFrame) and not table_data.empty:
                    table_schema = schema.get('tables', {}).get(table_name, {})

                    # 智能存储决策
                    storage_decision = await self._make_storage_decision(table_name, table_data, table_schema)
                    storage_result['strategy_decisions'][table_name] = storage_decision

                    # 执行存储策略
                    table_storage_result = await self._execute_storage_strategy(
                        table_name, table_data, table_schema, storage_decision
                    )

                    # 合并结果
                    if table_storage_result.get('data_lake_path'):
                        storage_result['data_lake_paths'][table_name] = table_storage_result['data_lake_path']

                    if table_storage_result.get('warehouse_catalog_id'):
                        storage_result['warehouse_catalog_ids'][table_name] = table_storage_result['warehouse_catalog_id']

                    if table_storage_result.get('cached'):
                        storage_result['cached_tables'].append(table_name)

                    # 收集存储指标
                    storage_result['storage_metrics'][table_name] = table_storage_result.get('metrics', {})

            self.logger.info("Intelligent data storage completed")
            return storage_result

        except Exception as e:
            self.logger.error(f"Intelligent storage failed: {e}")
            raise

    async def _make_storage_decision(self, table_name: str, table_data: pd.DataFrame,
                                   table_schema: Dict[str, Any]) -> Dict[str, Any]:
        """制定存储策略决策"""
        decision = {
            'store_to_lake': True,     # 所有数据都存储到数据湖
            'store_to_warehouse': True, # 结构化数据存储到数据仓库
            'cache_data': False,       # 默认不缓存
            'retention_policy': 'standard',
            'compression_level': 3,
            'reasoning': []
        }

        # 数据大小考虑
        data_size = len(table_data)
        data_memory_usage = table_data.memory_usage(deep=True).sum()

        if data_size < self.storage_strategy['auto_cache_threshold']:
            decision['cache_data'] = True
            decision['reasoning'].append(f"Small dataset ({data_size} records) - eligible for caching")

        # 业务重要性考虑
        business_classification = table_schema.get('business_classification', 'unknown')
        audit_significance = table_schema.get('audit_significance', 'low')

        if audit_significance == 'high':
            decision['retention_policy'] = 'long_term'
            decision['compression_level'] = 1  # 更低压缩以保证速度
            decision['reasoning'].append("High audit significance - long-term retention with low compression")

        if business_classification == 'transaction_table':
            decision['store_to_warehouse'] = True
            decision['reasoning'].append("Transaction table - store in warehouse for query performance")

        # 数据质量考虑
        quality_score = table_schema.get('quality_score', 0.0)
        if quality_score < 0.5:
            decision['store_to_warehouse'] = False
            decision['reasoning'].append("Low quality data - lake storage only")

        return decision

    async def _execute_storage_strategy(self, table_name: str, table_data: pd.DataFrame,
                                      table_schema: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
        """执行存储策略"""
        result = {
            'data_lake_path': None,
            'warehouse_catalog_id': None,
            'cached': False,
            'metrics': {}
        }

        start_time = time.time()

        try:
            # 1. 存储到数据湖
            if decision['store_to_lake']:
                lake_metadata = {
                    'table_schema': table_schema,
                    'quality_score': table_schema.get('quality_score', 0.0),
                    'business_classification': table_schema.get('business_classification', 'unknown'),
                    'compression_level': decision['compression_level']
                }

                data_package = {
                    table_name: table_data.to_dict('records')
                }

                result['data_lake_path'] = await self.data_lake.store_raw_data(
                    f"{table_name}_{int(time.time())}", data_package, lake_metadata
                )

            # 2. 存储到数据仓库
            if decision['store_to_warehouse']:
                warehouse_metadata = {
                    'data_source': table_schema.get('data_source', 'unknown'),
                    'quality_score': table_schema.get('quality_score', 0.0),
                    'audit_significance': table_schema.get('audit_significance', 'low')
                }

                result['warehouse_catalog_id'] = await self.data_warehouse.store_structured_data(
                    table_name, table_data, table_schema, warehouse_metadata
                )

            # 3. 缓存热点数据
            if decision['cache_data']:
                cache_key = f"table:{table_name}"
                cache_data = {
                    'data': table_data.to_dict('records'),
                    'schema': table_schema,
                    'cached_at': datetime.now().isoformat()
                }

                result['cached'] = await self.cache.set(cache_key, cache_data)

            # 4. 向下兼容存储
            if self.base_storage:
                try:
                    # 使用基础存储管理器存储（向下兼容）
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.base_storage.store_data, {table_name: table_data}
                    )
                except Exception as e:
                    self.logger.warning(f"Base storage failed for {table_name}: {e}")

            # 计算存储指标
            storage_time = time.time() - start_time
            result['metrics'] = {
                'storage_time_seconds': storage_time,
                'data_size_bytes': table_data.memory_usage(deep=True).sum(),
                'record_count': len(table_data),
                'compression_ratio': decision.get('compression_level', 3) / 10.0,
                'storage_layers': sum([
                    1 if result['data_lake_path'] else 0,
                    1 if result['warehouse_catalog_id'] else 0,
                    1 if result['cached'] else 0
                ])
            }

        except Exception as e:
            self.logger.error(f"Storage strategy execution failed for {table_name}: {e}")
            raise

        return result

    async def retrieve_data(self, table_name: str, source_preference: List[str] = None) -> Optional[pd.DataFrame]:
        """
        智能数据检索

        Args:
            table_name: 表名
            source_preference: 数据源偏好顺序 ['cache', 'warehouse', 'lake']

        Returns:
            检索到的数据
        """
        source_preference = source_preference or ['cache', 'warehouse', 'lake']

        for source in source_preference:
            try:
                if source == 'cache':
                    data = await self._retrieve_from_cache(table_name)
                    if data is not None:
                        self.logger.info(f"Data retrieved from cache: {table_name}")
                        return data

                elif source == 'warehouse':
                    data = await self._retrieve_from_warehouse(table_name)
                    if data is not None:
                        self.logger.info(f"Data retrieved from warehouse: {table_name}")
                        return data

                elif source == 'lake':
                    data = await self._retrieve_from_lake(table_name)
                    if data is not None:
                        self.logger.info(f"Data retrieved from lake: {table_name}")
                        return data

            except Exception as e:
                self.logger.warning(f"Failed to retrieve from {source} for {table_name}: {e}")
                continue

        self.logger.warning(f"Failed to retrieve data for {table_name} from all sources")
        return None

    async def _retrieve_from_cache(self, table_name: str) -> Optional[pd.DataFrame]:
        """从缓存检索数据"""
        cache_key = f"table:{table_name}"
        cached_data = await self.cache.get(cache_key)

        if cached_data and 'data' in cached_data:
            return pd.DataFrame(cached_data['data'])

        return None

    async def _retrieve_from_warehouse(self, table_name: str) -> Optional[pd.DataFrame]:
        """从数据仓库检索数据"""
        try:
            sql = f'SELECT * FROM "{table_name}"'
            return await self.data_warehouse.query_data(sql)

        except Exception as e:
            self.logger.warning(f"Warehouse retrieval failed for {table_name}: {e}")
            return None

    async def _retrieve_from_lake(self, table_name: str) -> Optional[pd.DataFrame]:
        """从数据湖检索数据（需要额外的元数据来定位）"""
        # 这里需要实现基于元数据的数据湖检索逻辑
        # 由于数据湖存储的是原始数据包，需要额外的索引机制
        self.logger.warning("Lake retrieval not fully implemented - requires metadata indexing")
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """获取存储指标"""
        return {
            'storage_type': 'hybrid',
            'components': {
                'data_lake': {
                    'type': 'local' if not self.data_lake.minio_client else 'minio',
                    'compression': 'zstd'
                },
                'data_warehouse': {
                    'type': 'sqlite',
                    'connection_pool_size': self.data_warehouse.connection_pool_size
                },
                'cache': {
                    'type': self.cache.cache_type,
                    'ttl_seconds': self.cache.ttl_seconds
                }
            },
            'strategy': self.storage_strategy
        }

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        try:
            # 数据仓库统计
            warehouse_stats = {}
            if self.data_warehouse:
                # 这里可以添加更详细的统计逻辑
                warehouse_stats = {
                    'db_path': self.data_warehouse.db_path,
                    'db_size_bytes': Path(self.data_warehouse.db_path).stat().st_size if Path(self.data_warehouse.db_path).exists() else 0
                }

            # 数据湖统计
            lake_stats = {}
            if self.data_lake:
                lake_stats = {
                    'storage_path': str(self.data_lake.storage_path),
                    'file_count': len(list(self.data_lake.storage_path.glob('**/*.zst'))) if self.data_lake.storage_path.exists() else 0
                }

            return {
                'warehouse': warehouse_stats,
                'lake': lake_stats,
                'cache': {
                    'type': self.cache.cache_type,
                    'memory_items': len(self.cache.memory_cache) if self.cache.cache_type == 'memory' else 'unknown'
                }
            }

        except Exception as e:
            self.logger.warning(f"Failed to get usage stats: {e}")
            return {}

# 测试函数
async def test_hybrid_storage():
    """测试混合存储管理器"""
    print("Testing Hybrid Storage Manager...")

    # 创建测试数据
    test_data = {
        'general_ledger': pd.DataFrame({
            '科目编码': ['1001', '1002', '2001', '2002'],
            '科目名称': ['现金', '银行存款', '应付账款', '预收账款'],
            '借方金额': [1000.0, 2000.0, 0.0, 0.0],
            '贷方金额': [0.0, 0.0, 1500.0, 500.0],
            '凭证号': ['GL001', 'GL002', 'GL003', 'GL004'],
            '日期': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']
        })
    }

    test_schema = {
        'tables': {
            'general_ledger': {
                'business_classification': 'transaction_table',
                'audit_significance': 'high',
                'quality_score': 0.95,
                'columns': {
                    '科目编码': {'semantic_type': 'account_code', 'data_type': 'object'},
                    '科目名称': {'semantic_type': 'account_name', 'data_type': 'object'},
                    '借方金额': {'semantic_type': 'debit_amount', 'data_type': 'float64'},
                    '贷方金额': {'semantic_type': 'credit_amount', 'data_type': 'float64'},
                    '凭证号': {'semantic_type': 'voucher_no', 'data_type': 'object'},
                    '日期': {'semantic_type': 'date', 'data_type': 'object'}
                }
            }
        }
    }

    # 创建存储管理器
    storage_manager = HybridStorageManager()

    # 测试智能存储
    storage_result = await storage_manager.store_intelligently(test_data, test_schema)
    print(f"Storage result: {json.dumps(storage_result, indent=2, ensure_ascii=False, default=str)}")

    # 测试数据检索
    retrieved_data = await storage_manager.retrieve_data('general_ledger')
    if retrieved_data is not None:
        print(f"Retrieved data shape: {retrieved_data.shape}")
    else:
        print("No data retrieved")

    # 获取指标
    metrics = storage_manager.get_metrics()
    print(f"Storage metrics: {json.dumps(metrics, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    asyncio.run(test_hybrid_storage())