#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Storage Optimizer - 存储优化器
智能优化存储性能、成本和可用性

核心功能：
1. 冷热数据自动分离
2. 智能压缩策略
3. 动态索引管理
4. 存储成本优化
5. 查询性能优化
"""

import asyncio
import logging
import os
import time
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import threading

# 压缩相关导入
try:
    import zstandard as zstd
    import lz4.frame
    import gzip
    COMPRESSION_AVAILABLE = True
except ImportError:
    COMPRESSION_AVAILABLE = False

logger = logging.getLogger(__name__)

class ColdHotDataSeparator:
    """冷热数据分离器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 热数据阈值配置
        self.hot_data_criteria = {
            'access_frequency_threshold': self.config.get('hot_access_frequency', 10),  # 10次/月
            'recent_access_days': self.config.get('hot_recent_days', 30),  # 30天内
            'data_age_days': self.config.get('hot_age_threshold', 90),  # 90天内的数据
            'business_priority': self.config.get('hot_business_priority', ['high', 'critical'])
        }

        # 数据访问统计
        self.access_stats = defaultdict(lambda: {
            'access_count': 0,
            'last_access': None,
            'access_pattern': []
        })

        self.stats_lock = threading.Lock()

        logger.info("Cold-Hot Data Separator initialized")

    def classify_data_temperature(self, table_name: str, table_info: Dict[str, Any]) -> str:
        """
        分类数据温度

        Args:
            table_name: 表名
            table_info: 表信息

        Returns:
            'hot', 'warm', 'cold'
        """
        try:
            # 基础分类：hot, warm, cold
            temperature = 'cold'  # 默认为冷数据

            with self.stats_lock:
                stats = self.access_stats[table_name]

            # 1. 访问频率判断
            access_count = stats['access_count']
            last_access = stats.get('last_access')

            if last_access:
                days_since_access = (datetime.now() - last_access).days

                if days_since_access <= self.hot_data_criteria['recent_access_days']:
                    if access_count >= self.hot_data_criteria['access_frequency_threshold']:
                        temperature = 'hot'
                    else:
                        temperature = 'warm'

            # 2. 数据年龄判断
            created_at = table_info.get('created_at')
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        created_date = created_at

                    data_age_days = (datetime.now() - created_date).days

                    if data_age_days <= self.hot_data_criteria['data_age_days']:
                        # 新数据倾向于热数据
                        if temperature == 'cold':
                            temperature = 'warm'

                except Exception as e:
                    logger.warning(f"Failed to parse created_at for {table_name}: {e}")

            # 3. 业务优先级判断
            audit_significance = table_info.get('audit_significance', 'low')
            business_classification = table_info.get('business_classification', 'unknown')

            if audit_significance in self.hot_data_criteria['business_priority']:
                if temperature == 'cold':
                    temperature = 'warm'
                elif temperature == 'warm':
                    temperature = 'hot'

            # 4. 表类型判断
            if business_classification == 'transaction_table':
                # 交易表通常需要频繁访问
                if temperature == 'cold':
                    temperature = 'warm'

            logger.debug(f"Table {table_name} classified as: {temperature}")
            return temperature

        except Exception as e:
            logger.error(f"Failed to classify data temperature for {table_name}: {e}")
            return 'cold'

    def record_access(self, table_name: str, access_type: str = 'read'):
        """记录数据访问"""
        try:
            with self.stats_lock:
                stats = self.access_stats[table_name]
                stats['access_count'] += 1
                stats['last_access'] = datetime.now()
                stats['access_pattern'].append({
                    'timestamp': datetime.now().isoformat(),
                    'type': access_type
                })

                # 保持访问模式历史不超过100条
                if len(stats['access_pattern']) > 100:
                    stats['access_pattern'] = stats['access_pattern'][-100:]

        except Exception as e:
            logger.warning(f"Failed to record access for {table_name}: {e}")

    def get_access_statistics(self, table_name: str) -> Dict[str, Any]:
        """获取访问统计"""
        with self.stats_lock:
            stats = self.access_stats.get(table_name, {})

        return {
            'access_count': stats.get('access_count', 0),
            'last_access': stats.get('last_access'),
            'access_frequency_per_month': self._calculate_monthly_frequency(stats),
            'access_pattern_summary': self._analyze_access_pattern(stats)
        }

    def _calculate_monthly_frequency(self, stats: Dict[str, Any]) -> float:
        """计算月访问频率"""
        try:
            access_pattern = stats.get('access_pattern', [])
            if not access_pattern:
                return 0.0

            # 计算最近30天的访问频率
            cutoff_date = datetime.now() - timedelta(days=30)
            recent_accesses = [
                access for access in access_pattern
                if datetime.fromisoformat(access['timestamp']) > cutoff_date
            ]

            return len(recent_accesses)

        except Exception as e:
            logger.warning(f"Failed to calculate monthly frequency: {e}")
            return 0.0

    def _analyze_access_pattern(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """分析访问模式"""
        try:
            access_pattern = stats.get('access_pattern', [])
            if not access_pattern:
                return {'pattern': 'no_access'}

            # 分析访问时间分布
            access_hours = []
            for access in access_pattern[-50:]:  # 分析最近50次访问
                timestamp = datetime.fromisoformat(access['timestamp'])
                access_hours.append(timestamp.hour)

            # 判断访问模式
            if len(set(access_hours)) <= 3:
                pattern = 'concentrated'  # 集中访问
            elif all(8 <= hour <= 18 for hour in access_hours):
                pattern = 'business_hours'  # 工作时间访问
            else:
                pattern = 'distributed'  # 分散访问

            return {
                'pattern': pattern,
                'peak_hours': max(set(access_hours), key=access_hours.count) if access_hours else None,
                'access_variance': np.var(access_hours) if access_hours else 0
            }

        except Exception as e:
            logger.warning(f"Failed to analyze access pattern: {e}")
            return {'pattern': 'unknown'}

class CompressionManager:
    """压缩管理器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 压缩算法配置
        self.compression_algorithms = {
            'zstd': {
                'compressor': self._zstd_compress if COMPRESSION_AVAILABLE else None,
                'decompressor': self._zstd_decompress if COMPRESSION_AVAILABLE else None,
                'ratio': 0.3,  # 预期压缩比
                'speed': 'fast',
                'suitable_for': ['text', 'structured_data']
            },
            'lz4': {
                'compressor': self._lz4_compress if COMPRESSION_AVAILABLE else None,
                'decompressor': self._lz4_decompress if COMPRESSION_AVAILABLE else None,
                'ratio': 0.5,
                'speed': 'very_fast',
                'suitable_for': ['hot_data', 'frequent_access']
            },
            'gzip': {
                'compressor': self._gzip_compress,
                'decompressor': self._gzip_decompress,
                'ratio': 0.25,
                'speed': 'slow',
                'suitable_for': ['cold_data', 'archival']
            }
        }

        logger.info("Compression Manager initialized")

    def select_compression_algorithm(self, data_info: Dict[str, Any]) -> str:
        """
        选择最佳压缩算法

        Args:
            data_info: 数据信息

        Returns:
            压缩算法名称
        """
        try:
            data_size = data_info.get('size_bytes', 0)
            data_temperature = data_info.get('temperature', 'cold')
            access_frequency = data_info.get('access_frequency', 0)

            # 基于数据温度选择算法
            if data_temperature == 'hot' or access_frequency > 50:
                # 热数据优先速度
                return 'lz4' if COMPRESSION_AVAILABLE else 'gzip'
            elif data_temperature == 'warm':
                # 温数据平衡压缩比和速度
                return 'zstd' if COMPRESSION_AVAILABLE else 'gzip'
            else:
                # 冷数据优先压缩比
                return 'gzip'

        except Exception as e:
            logger.warning(f"Failed to select compression algorithm: {e}")
            return 'gzip'  # 默认使用gzip

    def _zstd_compress(self, data: bytes, level: int = 3) -> bytes:
        """ZSTD压缩"""
        if not COMPRESSION_AVAILABLE:
            raise NotImplementedError("ZSTD compression not available")

        compressor = zstd.ZstdCompressor(level=level)
        return compressor.compress(data)

    def _zstd_decompress(self, compressed_data: bytes) -> bytes:
        """ZSTD解压缩"""
        if not COMPRESSION_AVAILABLE:
            raise NotImplementedError("ZSTD decompression not available")

        decompressor = zstd.ZstdDecompressor()
        return decompressor.decompress(compressed_data)

    def _lz4_compress(self, data: bytes) -> bytes:
        """LZ4压缩"""
        if not COMPRESSION_AVAILABLE:
            raise NotImplementedError("LZ4 compression not available")

        return lz4.frame.compress(data)

    def _lz4_decompress(self, compressed_data: bytes) -> bytes:
        """LZ4解压缩"""
        if not COMPRESSION_AVAILABLE:
            raise NotImplementedError("LZ4 decompression not available")

        return lz4.frame.decompress(compressed_data)

    def _gzip_compress(self, data: bytes, level: int = 6) -> bytes:
        """GZIP压缩"""
        return gzip.compress(data, compresslevel=level)

    def _gzip_decompress(self, compressed_data: bytes) -> bytes:
        """GZIP解压缩"""
        return gzip.decompress(compressed_data)

    def compress_data(self, data: bytes, algorithm: str = 'gzip', **kwargs) -> Tuple[bytes, Dict[str, Any]]:
        """
        压缩数据

        Args:
            data: 原始数据
            algorithm: 压缩算法
            **kwargs: 算法参数

        Returns:
            (压缩数据, 压缩信息)
        """
        try:
            start_time = time.time()
            original_size = len(data)

            if algorithm in self.compression_algorithms:
                compressor = self.compression_algorithms[algorithm]['compressor']
                if compressor:
                    compressed_data = compressor(data, **kwargs)
                else:
                    raise ValueError(f"Compressor for {algorithm} not available")
            else:
                raise ValueError(f"Unknown compression algorithm: {algorithm}")

            compression_time = time.time() - start_time
            compressed_size = len(compressed_data)
            compression_ratio = compressed_size / original_size

            compression_info = {
                'algorithm': algorithm,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'compression_time': compression_time,
                'savings_bytes': original_size - compressed_size,
                'savings_percentage': (1 - compression_ratio) * 100
            }

            logger.debug(f"Compression completed: {algorithm}, ratio: {compression_ratio:.3f}")
            return compressed_data, compression_info

        except Exception as e:
            logger.error(f"Compression failed with {algorithm}: {e}")
            raise

    def decompress_data(self, compressed_data: bytes, algorithm: str) -> bytes:
        """解压缩数据"""
        try:
            if algorithm in self.compression_algorithms:
                decompressor = self.compression_algorithms[algorithm]['decompressor']
                if decompressor:
                    return decompressor(compressed_data)
                else:
                    raise ValueError(f"Decompressor for {algorithm} not available")
            else:
                raise ValueError(f"Unknown compression algorithm: {algorithm}")

        except Exception as e:
            logger.error(f"Decompression failed with {algorithm}: {e}")
            raise

class IndexManager:
    """动态索引管理器"""

    def __init__(self, db_path: str, config: Dict[str, Any] = None):
        self.db_path = db_path
        self.config = config or {}

        # 索引策略配置
        self.index_strategies = {
            'frequent_query_threshold': self.config.get('frequent_query_threshold', 100),
            'index_selectivity_threshold': self.config.get('index_selectivity_threshold', 0.1),
            'composite_index_max_columns': self.config.get('composite_index_max_columns', 3),
            'index_maintenance_interval': self.config.get('index_maintenance_interval', 3600)  # 1小时
        }

        # 查询统计
        self.query_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'columns_used': set(),
            'where_conditions': []
        })

        self.stats_lock = threading.Lock()

        logger.info(f"Index Manager initialized for: {db_path}")

    def record_query(self, sql: str, execution_time: float, columns_used: List[str] = None):
        """记录查询统计"""
        try:
            # 简化SQL作为key
            query_key = self._normalize_query(sql)

            with self.stats_lock:
                stats = self.query_stats[query_key]
                stats['count'] += 1
                stats['total_time'] += execution_time
                stats['avg_time'] = stats['total_time'] / stats['count']

                if columns_used:
                    stats['columns_used'].update(columns_used)

                # 解析WHERE条件
                where_conditions = self._extract_where_conditions(sql)
                stats['where_conditions'].extend(where_conditions)

        except Exception as e:
            logger.warning(f"Failed to record query statistics: {e}")

    def _normalize_query(self, sql: str) -> str:
        """标准化查询语句"""
        try:
            # 简化处理：提取表名和主要操作
            sql_lower = sql.lower().strip()

            if sql_lower.startswith('select'):
                # 提取FROM子句中的表名
                from_idx = sql_lower.find('from')
                if from_idx != -1:
                    remaining = sql_lower[from_idx + 4:].strip()
                    table_name = remaining.split()[0]
                    return f"select_from_{table_name}"

            elif sql_lower.startswith('insert'):
                table_name = sql_lower.split()[2]
                return f"insert_into_{table_name}"

            elif sql_lower.startswith('update'):
                table_name = sql_lower.split()[1]
                return f"update_{table_name}"

            elif sql_lower.startswith('delete'):
                from_idx = sql_lower.find('from')
                if from_idx != -1:
                    table_name = sql_lower[from_idx + 4:].strip().split()[0]
                    return f"delete_from_{table_name}"

            return "unknown_query"

        except Exception as e:
            logger.warning(f"Failed to normalize query: {e}")
            return "parse_error"

    def _extract_where_conditions(self, sql: str) -> List[str]:
        """提取WHERE条件中的列"""
        try:
            sql_lower = sql.lower()
            where_idx = sql_lower.find('where')

            if where_idx == -1:
                return []

            where_clause = sql[where_idx + 5:]

            # 简单提取列名（可以改进）
            import re
            column_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[=<>!]'
            matches = re.findall(column_pattern, where_clause)

            return matches

        except Exception as e:
            logger.warning(f"Failed to extract WHERE conditions: {e}")
            return []

    async def optimize_indexes(self, table_name: str) -> Dict[str, Any]:
        """优化表索引"""
        try:
            optimization_result = {
                'table_name': table_name,
                'existing_indexes': [],
                'recommended_indexes': [],
                'created_indexes': [],
                'dropped_indexes': [],
                'optimization_summary': {}
            }

            conn = sqlite3.connect(self.db_path)
            try:
                # 1. 获取现有索引
                existing_indexes = await self._get_existing_indexes(conn, table_name)
                optimization_result['existing_indexes'] = existing_indexes

                # 2. 分析查询模式
                query_analysis = await self._analyze_query_patterns(table_name)

                # 3. 生成索引推荐
                recommendations = await self._generate_index_recommendations(
                    conn, table_name, query_analysis
                )
                optimization_result['recommended_indexes'] = recommendations

                # 4. 创建推荐的索引
                created_indexes = await self._create_recommended_indexes(
                    conn, table_name, recommendations
                )
                optimization_result['created_indexes'] = created_indexes

                # 5. 删除无用索引
                dropped_indexes = await self._drop_unused_indexes(
                    conn, table_name, existing_indexes, query_analysis
                )
                optimization_result['dropped_indexes'] = dropped_indexes

                conn.commit()

                optimization_result['optimization_summary'] = {
                    'indexes_created': len(created_indexes),
                    'indexes_dropped': len(dropped_indexes),
                    'total_existing': len(existing_indexes),
                    'optimization_time': datetime.now().isoformat()
                }

                logger.info(f"Index optimization completed for {table_name}")
                return optimization_result

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Index optimization failed for {table_name}: {e}")
            raise

    async def _get_existing_indexes(self, conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
        """获取现有索引"""
        try:
            cursor = conn.execute("""
                SELECT name, sql FROM sqlite_master
                WHERE type = 'index' AND tbl_name = ?
                AND sql IS NOT NULL
            """, (table_name,))

            indexes = []
            for row in cursor.fetchall():
                index_name, index_sql = row
                indexes.append({
                    'name': index_name,
                    'sql': index_sql,
                    'columns': self._parse_index_columns(index_sql)
                })

            return indexes

        except Exception as e:
            logger.warning(f"Failed to get existing indexes: {e}")
            return []

    def _parse_index_columns(self, index_sql: str) -> List[str]:
        """解析索引SQL中的列名"""
        try:
            # 简单解析CREATE INDEX语句
            import re
            pattern = r'\((.*?)\)'
            match = re.search(pattern, index_sql)

            if match:
                columns_str = match.group(1)
                columns = [col.strip().strip('"') for col in columns_str.split(',')]
                return columns

            return []

        except Exception as e:
            logger.warning(f"Failed to parse index columns: {e}")
            return []

    async def _analyze_query_patterns(self, table_name: str) -> Dict[str, Any]:
        """分析查询模式"""
        try:
            with self.stats_lock:
                # 筛选与该表相关的查询
                table_queries = {
                    query_key: stats for query_key, stats in self.query_stats.items()
                    if table_name in query_key
                }

            analysis = {
                'total_queries': sum(stats['count'] for stats in table_queries.values()),
                'frequent_columns': defaultdict(int),
                'query_types': defaultdict(int),
                'performance_issues': []
            }

            # 分析频繁使用的列
            for query_key, stats in table_queries.items():
                for condition in stats['where_conditions']:
                    analysis['frequent_columns'][condition] += stats['count']

                # 分析查询类型
                if 'select' in query_key:
                    analysis['query_types']['select'] += stats['count']
                elif 'insert' in query_key:
                    analysis['query_types']['insert'] += stats['count']
                elif 'update' in query_key:
                    analysis['query_types']['update'] += stats['count']
                elif 'delete' in query_key:
                    analysis['query_types']['delete'] += stats['count']

                # 识别性能问题
                if stats['avg_time'] > 1.0:  # 平均执行时间超过1秒
                    analysis['performance_issues'].append({
                        'query_key': query_key,
                        'avg_time': stats['avg_time'],
                        'count': stats['count']
                    })

            return analysis

        except Exception as e:
            logger.warning(f"Failed to analyze query patterns: {e}")
            return {}

    async def _generate_index_recommendations(self, conn: sqlite3.Connection, table_name: str,
                                            query_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成索引推荐"""
        try:
            recommendations = []

            # 获取表结构
            cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
            columns_info = {row[1]: row[2] for row in cursor.fetchall()}

            # 基于频繁查询列推荐单列索引
            frequent_columns = query_analysis.get('frequent_columns', {})

            for column, frequency in frequent_columns.items():
                if (column in columns_info and
                    frequency >= self.index_strategies['frequent_query_threshold']):

                    # 检查列的选择性
                    selectivity = await self._calculate_column_selectivity(conn, table_name, column)

                    if selectivity >= self.index_strategies['index_selectivity_threshold']:
                        recommendations.append({
                            'type': 'single_column',
                            'columns': [column],
                            'reason': f'Frequent query column (used {frequency} times)',
                            'selectivity': selectivity,
                            'priority': frequency * selectivity
                        })

            # 推荐复合索引
            # 简化实现：基于经常一起出现的列
            composite_candidates = await self._find_composite_index_candidates(query_analysis)

            for candidate in composite_candidates:
                if len(candidate['columns']) <= self.index_strategies['composite_index_max_columns']:
                    recommendations.append({
                        'type': 'composite',
                        'columns': candidate['columns'],
                        'reason': candidate['reason'],
                        'priority': candidate['frequency']
                    })

            # 按优先级排序
            recommendations.sort(key=lambda x: x.get('priority', 0), reverse=True)

            return recommendations[:5]  # 最多推荐5个索引

        except Exception as e:
            logger.warning(f"Failed to generate index recommendations: {e}")
            return []

    async def _calculate_column_selectivity(self, conn: sqlite3.Connection,
                                          table_name: str, column: str) -> float:
        """计算列的选择性"""
        try:
            # 计算唯一值数量 / 总行数
            cursor = conn.execute(f'''
                SELECT
                    COUNT(DISTINCT "{column}") as unique_count,
                    COUNT(*) as total_count
                FROM "{table_name}"
            ''')

            row = cursor.fetchone()
            if row and row[1] > 0:
                unique_count, total_count = row
                return unique_count / total_count
            else:
                return 0.0

        except Exception as e:
            logger.warning(f"Failed to calculate selectivity for {column}: {e}")
            return 0.0

    async def _find_composite_index_candidates(self, query_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """查找复合索引候选"""
        try:
            # 简化实现：基于WHERE条件中经常一起出现的列
            candidates = []

            # 这里可以实现更复杂的逻辑来分析列的共现模式
            # 目前返回空列表
            return candidates

        except Exception as e:
            logger.warning(f"Failed to find composite index candidates: {e}")
            return []

    async def _create_recommended_indexes(self, conn: sqlite3.Connection, table_name: str,
                                        recommendations: List[Dict[str, Any]]) -> List[str]:
        """创建推荐的索引"""
        try:
            created_indexes = []

            for i, recommendation in enumerate(recommendations):
                try:
                    columns = recommendation['columns']
                    index_name = f"idx_{table_name}_{'_'.join(columns)}_{i}"

                    # 检查索引是否已存在
                    cursor = conn.execute("""
                        SELECT name FROM sqlite_master
                        WHERE type = 'index' AND name = ?
                    """, (index_name,))

                    if cursor.fetchone():
                        continue  # 索引已存在

                    # 创建索引
                    columns_quoted = [f'"{col}"' for col in columns]
                    create_sql = f'''
                        CREATE INDEX "{index_name}"
                        ON "{table_name}" ({", ".join(columns_quoted)})
                    '''

                    conn.execute(create_sql)
                    created_indexes.append(index_name)

                    logger.info(f"Created index: {index_name}")

                except Exception as e:
                    logger.warning(f"Failed to create index for {recommendation}: {e}")

            return created_indexes

        except Exception as e:
            logger.error(f"Failed to create recommended indexes: {e}")
            return []

    async def _drop_unused_indexes(self, conn: sqlite3.Connection, table_name: str,
                                 existing_indexes: List[Dict[str, Any]],
                                 query_analysis: Dict[str, Any]) -> List[str]:
        """删除无用索引"""
        try:
            dropped_indexes = []

            # 获取频繁使用的列
            frequent_columns = set(query_analysis.get('frequent_columns', {}).keys())

            for index_info in existing_indexes:
                index_name = index_info['name']
                index_columns = set(index_info['columns'])

                # 如果索引的所有列都不在频繁查询中，考虑删除
                if not index_columns.intersection(frequent_columns):
                    try:
                        conn.execute(f'DROP INDEX IF EXISTS "{index_name}"')
                        dropped_indexes.append(index_name)
                        logger.info(f"Dropped unused index: {index_name}")

                    except Exception as e:
                        logger.warning(f"Failed to drop index {index_name}: {e}")

            return dropped_indexes

        except Exception as e:
            logger.error(f"Failed to drop unused indexes: {e}")
            return []

class StorageOptimizer:
    """存储优化器 - 统一管理存储优化"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 初始化子组件
        self.cold_hot_separator = ColdHotDataSeparator(self.config.get('cold_hot_separation', {}))
        self.compression_manager = CompressionManager(self.config.get('compression', {}))

        # 索引管理器将在需要时初始化（需要数据库路径）
        self.index_managers = {}

        # 优化配置
        self.optimization_config = {
            'auto_optimization_enabled': self.config.get('auto_optimization', True),
            'optimization_interval_hours': self.config.get('optimization_interval', 24),
            'compression_enabled': self.config.get('compression_enabled', True),
            'index_optimization_enabled': self.config.get('index_optimization', True)
        }

        self.logger.info("Storage Optimizer initialized")

    async def optimize_storage(self, storage_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化存储

        Args:
            storage_result: 存储结果

        Returns:
            优化结果
        """
        self.logger.info("Starting storage optimization")

        try:
            optimization_result = {
                'temperature_classification': {},
                'compression_results': {},
                'index_optimizations': {},
                'overall_metrics': {},
                'optimization_summary': {}
            }

            # 1. 冷热数据分类
            temperature_classification = await self._classify_data_temperature(storage_result)
            optimization_result['temperature_classification'] = temperature_classification

            # 2. 压缩优化
            if self.optimization_config['compression_enabled']:
                compression_results = await self._optimize_compression(storage_result, temperature_classification)
                optimization_result['compression_results'] = compression_results

            # 3. 索引优化
            if self.optimization_config['index_optimization_enabled']:
                index_optimizations = await self._optimize_indexes(storage_result)
                optimization_result['index_optimizations'] = index_optimizations

            # 4. 计算整体指标
            overall_metrics = await self._calculate_optimization_metrics(optimization_result)
            optimization_result['overall_metrics'] = overall_metrics

            # 5. 生成优化摘要
            optimization_summary = await self._generate_optimization_summary(optimization_result)
            optimization_result['optimization_summary'] = optimization_summary

            self.logger.info("Storage optimization completed")
            return optimization_result

        except Exception as e:
            self.logger.error(f"Storage optimization failed: {e}")
            raise

    async def _classify_data_temperature(self, storage_result: Dict[str, Any]) -> Dict[str, str]:
        """分类数据温度"""
        temperature_classification = {}

        warehouse_catalog_ids = storage_result.get('warehouse_catalog_ids', {})

        for table_name, catalog_id in warehouse_catalog_ids.items():
            # 这里需要从数据仓库获取表信息
            # 简化实现：假设表信息
            table_info = {
                'created_at': datetime.now().isoformat(),
                'audit_significance': 'medium',
                'business_classification': 'unknown'
            }

            temperature = self.cold_hot_separator.classify_data_temperature(table_name, table_info)
            temperature_classification[table_name] = temperature

        return temperature_classification

    async def _optimize_compression(self, storage_result: Dict[str, Any],
                                  temperature_classification: Dict[str, str]) -> Dict[str, Any]:
        """优化压缩"""
        compression_results = {}

        # 这里可以实现具体的压缩优化逻辑
        # 目前返回示例结果
        for table_name, temperature in temperature_classification.items():
            compression_results[table_name] = {
                'recommended_algorithm': self.compression_manager.select_compression_algorithm({
                    'temperature': temperature,
                    'size_bytes': 1000000,  # 示例大小
                    'access_frequency': 10
                }),
                'estimated_savings': 0.3,
                'optimization_applied': False
            }

        return compression_results

    async def _optimize_indexes(self, storage_result: Dict[str, Any]) -> Dict[str, Any]:
        """优化索引"""
        index_optimizations = {}

        warehouse_catalog_ids = storage_result.get('warehouse_catalog_ids', {})

        for table_name, catalog_id in warehouse_catalog_ids.items():
            # 为每个数据库创建索引管理器
            db_path = self.config.get('warehouse_db_path', 'data/warehouse/dap_warehouse.db')

            if db_path not in self.index_managers:
                self.index_managers[db_path] = IndexManager(db_path, self.config.get('index_management', {}))

            index_manager = self.index_managers[db_path]

            try:
                optimization = await index_manager.optimize_indexes(table_name)
                index_optimizations[table_name] = optimization

            except Exception as e:
                self.logger.warning(f"Index optimization failed for {table_name}: {e}")
                index_optimizations[table_name] = {'error': str(e)}

        return index_optimizations

    async def _calculate_optimization_metrics(self, optimization_result: Dict[str, Any]) -> Dict[str, Any]:
        """计算优化指标"""
        try:
            metrics = {
                'total_tables_optimized': 0,
                'compression_savings_estimated': 0.0,
                'indexes_created_total': 0,
                'indexes_dropped_total': 0,
                'hot_data_tables': 0,
                'warm_data_tables': 0,
                'cold_data_tables': 0
            }

            # 统计温度分类
            temperature_classification = optimization_result.get('temperature_classification', {})
            for temperature in temperature_classification.values():
                if temperature == 'hot':
                    metrics['hot_data_tables'] += 1
                elif temperature == 'warm':
                    metrics['warm_data_tables'] += 1
                elif temperature == 'cold':
                    metrics['cold_data_tables'] += 1

            metrics['total_tables_optimized'] = len(temperature_classification)

            # 统计压缩节省
            compression_results = optimization_result.get('compression_results', {})
            total_savings = sum(
                result.get('estimated_savings', 0)
                for result in compression_results.values()
            )
            metrics['compression_savings_estimated'] = total_savings

            # 统计索引优化
            index_optimizations = optimization_result.get('index_optimizations', {})
            for table_optimization in index_optimizations.values():
                if isinstance(table_optimization, dict) and 'optimization_summary' in table_optimization:
                    summary = table_optimization['optimization_summary']
                    metrics['indexes_created_total'] += summary.get('indexes_created', 0)
                    metrics['indexes_dropped_total'] += summary.get('indexes_dropped', 0)

            return metrics

        except Exception as e:
            self.logger.warning(f"Failed to calculate optimization metrics: {e}")
            return {}

    async def _generate_optimization_summary(self, optimization_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成优化摘要"""
        try:
            overall_metrics = optimization_result.get('overall_metrics', {})

            summary = {
                'optimization_completed_at': datetime.now().isoformat(),
                'total_tables_processed': overall_metrics.get('total_tables_optimized', 0),
                'performance_improvements': [],
                'storage_improvements': [],
                'recommendations': []
            }

            # 性能改进
            indexes_created = overall_metrics.get('indexes_created_total', 0)
            if indexes_created > 0:
                summary['performance_improvements'].append(
                    f"Created {indexes_created} indexes to improve query performance"
                )

            indexes_dropped = overall_metrics.get('indexes_dropped_total', 0)
            if indexes_dropped > 0:
                summary['performance_improvements'].append(
                    f"Removed {indexes_dropped} unused indexes to reduce maintenance overhead"
                )

            # 存储改进
            estimated_savings = overall_metrics.get('compression_savings_estimated', 0)
            if estimated_savings > 0:
                summary['storage_improvements'].append(
                    f"Estimated compression savings: {estimated_savings:.1%}"
                )

            # 建议
            hot_tables = overall_metrics.get('hot_data_tables', 0)
            cold_tables = overall_metrics.get('cold_data_tables', 0)

            if hot_tables > 0:
                summary['recommendations'].append(
                    f"Consider caching {hot_tables} hot tables for better performance"
                )

            if cold_tables > 0:
                summary['recommendations'].append(
                    f"Consider archiving {cold_tables} cold tables to reduce active storage"
                )

            return summary

        except Exception as e:
            self.logger.warning(f"Failed to generate optimization summary: {e}")
            return {}

    def record_table_access(self, table_name: str, access_type: str = 'read'):
        """记录表访问（供外部调用）"""
        self.cold_hot_separator.record_access(table_name, access_type)

    def record_query_performance(self, sql: str, execution_time: float, db_path: str = None):
        """记录查询性能（供外部调用）"""
        db_path = db_path or self.config.get('warehouse_db_path', 'data/warehouse/dap_warehouse.db')

        if db_path not in self.index_managers:
            self.index_managers[db_path] = IndexManager(db_path, self.config.get('index_management', {}))

        self.index_managers[db_path].record_query(sql, execution_time)

# 测试函数
async def test_storage_optimizer():
    """测试存储优化器"""
    print("Testing Storage Optimizer...")

    # 创建测试存储结果
    test_storage_result = {
        'warehouse_catalog_ids': {
            'general_ledger': 'gl_123456',
            'accounts_payable': 'ap_123456',
            'accounts_receivable': 'ar_123456'
        },
        'data_lake_paths': {
            'general_ledger': 'lake/2024/01/01/gl_123456.zst'
        }
    }

    optimizer = StorageOptimizer()

    # 测试优化
    optimization_result = await optimizer.optimize_storage(test_storage_result)
    print(f"Optimization result: {json.dumps(optimization_result, indent=2, ensure_ascii=False, default=str)}")

if __name__ == "__main__":
    asyncio.run(test_storage_optimizer())