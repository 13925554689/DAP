"""
性能优化器 - Layer 2
动态索引和查询优化管理

核心功能：
1. 动态索引管理和优化
2. 查询性能分析和优化
3. 内存使用优化
4. 缓存策略管理
5. 性能监控和报告
"""

import asyncio
import logging
import json
import sqlite3
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, deque
import statistics
import gc

# 高级数据结构
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# 缓存支持
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# 内存分析
try:
    import pympler
    from pympler import muppy, summary
    PYMPLER_AVAILABLE = True
except ImportError:
    PYMPLER_AVAILABLE = False

# 查询分析
try:
    import sqlparse
    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False

@dataclass
class QueryStats:
    """查询统计信息"""
    query_hash: str
    query_text: str
    execution_count: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    last_executed: datetime
    affected_tables: List[str]
    index_usage: Dict[str, Any]

@dataclass
class IndexStats:
    """索引统计信息"""
    index_name: str
    table_name: str
    columns: List[str]
    usage_count: int
    last_used: datetime
    size_estimate: int
    selectivity: float
    maintenance_cost: float

@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_io: Dict[str, float]
    query_count: int
    avg_query_time: float
    cache_hit_ratio: float
    active_connections: int

class PerformanceOptimizer:
    """性能优化器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 性能数据库配置
        self.perf_db_path = self.config.get('perf_db_path', 'data/performance.db')
        self.monitoring_enabled = self.config.get('monitoring_enabled', True)
        self.optimization_interval = self.config.get('optimization_interval', 3600)  # 1小时
        self.monitor_interval = max(5, int(self.config.get('monitor_interval', 60)))

        # 查询监控
        self.query_cache = {}
        self.query_stats = defaultdict(list)
        self.recent_queries = deque(maxlen=1000)

        # 索引管理
        self.active_indexes = {}
        self.index_usage_stats = defaultdict(int)

        # 性能指标
        self.metrics_history = deque(maxlen=1440)  # 24小时的分钟级数据

        # 缓存管理
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }

        # 并发控制
        self.max_workers = self.config.get('max_workers', 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._lock = threading.RLock()
        self._monitor_stop_event = threading.Event()
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_thread_error: Optional[Exception] = None

        # Redis缓存（可选）
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=self.config.get('redis_host', 'localhost'),
                    port=self.config.get('redis_port', 6379),
                    db=self.config.get('redis_db', 4),
                    decode_responses=True
                )
                self.redis_client.ping()
            except:
                self.redis_client = None
        else:
            self.redis_client = None

        # 初始化数据库
        self._init_database()

        # 启动性能监控
        if self.monitoring_enabled:
            self._start_background_monitoring()

    def _init_database(self):
        """初始化性能数据库"""
        try:
            Path(self.perf_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.perf_db_path) as conn:
                cursor = conn.cursor()

                # 查询统计表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS query_stats (
                        query_hash TEXT PRIMARY KEY,
                        query_text TEXT NOT NULL,
                        execution_count INTEGER DEFAULT 0,
                        total_time REAL DEFAULT 0,
                        avg_time REAL DEFAULT 0,
                        min_time REAL DEFAULT 0,
                        max_time REAL DEFAULT 0,
                        last_executed TEXT,
                        affected_tables TEXT,
                        index_usage TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 索引统计表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS index_stats (
                        index_name TEXT PRIMARY KEY,
                        table_name TEXT NOT NULL,
                        columns TEXT NOT NULL,
                        usage_count INTEGER DEFAULT 0,
                        last_used TEXT,
                        size_estimate INTEGER DEFAULT 0,
                        selectivity REAL DEFAULT 0,
                        maintenance_cost REAL DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 性能指标表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        cpu_percent REAL,
                        memory_percent REAL,
                        disk_io TEXT,
                        query_count INTEGER,
                        avg_query_time REAL,
                        cache_hit_ratio REAL,
                        active_connections INTEGER,
                        metadata TEXT
                    )
                ''')

                # 优化建议表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS optimization_recommendations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recommendation_type TEXT NOT NULL,
                        target TEXT NOT NULL,
                        description TEXT NOT NULL,
                        impact_estimate TEXT,
                        implementation_cost TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        applied_at TEXT
                    )
                ''')

                # 索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_query_stats_hash ON query_stats (query_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_index_stats_table ON index_stats (table_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_perf_metrics_time ON performance_metrics (timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_type ON optimization_recommendations (recommendation_type)')

                conn.commit()

            self.logger.info("性能优化数据库初始化完成")

        except Exception as e:
            self.logger.error(f"性能优化数据库初始化失败: {e}")
            raise

    def _start_background_monitoring(self) -> None:
        """在后台线程中启动性能监控，避免阻塞主线程。"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return

        self._monitor_stop_event.clear()
        self._monitoring_thread_error = None

        def _runner():
            try:
                asyncio.run(self._start_monitoring())
            except Exception as exc:  # pragma: no cover - 防御性
                self._monitoring_thread_error = exc
                self.logger.error("性能监控循环异常终止: %s", exc, exc_info=True)

        self._monitoring_thread = threading.Thread(
            target=_runner,
            name="PerformanceMonitoringLoop",
            daemon=True,
        )
        self._monitoring_thread.start()

    async def _sleep_with_stop(self, delay: float) -> None:
        """分段休眠，便于及时响应停止信号。"""
        elapsed = 0.0
        step = min(5.0, max(0.5, delay / 6))
        while elapsed < delay and not self._monitor_stop_event.is_set():
            interval = min(step, delay - elapsed)
            await asyncio.sleep(interval)
            elapsed += interval

    def stop_monitoring(self, timeout: float = 5.0) -> None:
        """停止后台监控线程。"""
        self._monitor_stop_event.set()
        thread = self._monitoring_thread
        if thread and thread.is_alive():
            thread.join(timeout)
        if self._monitoring_thread_error:
            self.logger.warning(
                "性能监控线程曾经异常退出: %s", self._monitoring_thread_error
            )
        self._monitoring_thread = None

    def close(self) -> None:
        """释放性能优化器资源。"""
        self.stop_monitoring()

    async def _start_monitoring(self):
        """启动性能监控"""
        self.logger.info("性能监控后台线程已启动")
        try:
            while not self._monitor_stop_event.is_set():
                await self._sleep_with_stop(self.monitor_interval)
                if self._monitor_stop_event.is_set():
                    break
                await self._collect_metrics()
                await self._analyze_performance()
        except asyncio.CancelledError:  # pragma: no cover - 防御性
            self.logger.info("性能监控后台线程被取消")
        except Exception as e:
            self.logger.error(f"性能监控失败: {e}", exc_info=True)
        finally:
            self.logger.info("性能监控后台线程已停止")

    async def _collect_metrics(self):
        """收集性能指标"""
        try:
            # 系统资源指标
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()

            # 查询统计
            with self._lock:
                recent_query_times = [q.get('execution_time', 0) for q in list(self.recent_queries)]
                avg_query_time = statistics.mean(recent_query_times) if recent_query_times else 0
                query_count = len(self.recent_queries)

            # 缓存命中率
            total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
            cache_hit_ratio = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0

            # 创建性能指标
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_io={
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0
                },
                query_count=query_count,
                avg_query_time=avg_query_time,
                cache_hit_ratio=cache_hit_ratio,
                active_connections=0  # 需要实际连接数
            )

            # 存储指标
            with self._lock:
                self.metrics_history.append(metrics)

            # 保存到数据库
            await self._save_metrics_to_db(metrics)

        except Exception as e:
            self.logger.error(f"收集性能指标失败: {e}")

    async def _save_metrics_to_db(self, metrics: PerformanceMetrics):
        """保存指标到数据库"""
        try:
            with sqlite3.connect(self.perf_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO performance_metrics
                    (timestamp, cpu_percent, memory_percent, disk_io,
                     query_count, avg_query_time, cache_hit_ratio, active_connections)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.timestamp.isoformat(),
                    metrics.cpu_percent,
                    metrics.memory_percent,
                    json.dumps(metrics.disk_io),
                    metrics.query_count,
                    metrics.avg_query_time,
                    metrics.cache_hit_ratio,
                    metrics.active_connections
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"保存性能指标失败: {e}")

    async def optimize_performance(self, optimization_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行性能优化"""
        try:
            config = optimization_config or {}

            result = {
                'optimization_id': f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'started_at': datetime.now().isoformat(),
                'optimizations_applied': [],
                'recommendations': [],
                'performance_improvement': {},
                'status': 'success'
            }

            # 1. 查询优化
            if config.get('optimize_queries', True):
                query_optimizations = await self._optimize_queries()
                result['optimizations_applied'].extend(query_optimizations)

            # 2. 索引优化
            if config.get('optimize_indexes', True):
                index_optimizations = await self._optimize_indexes()
                result['optimizations_applied'].extend(index_optimizations)

            # 3. 内存优化
            if config.get('optimize_memory', True):
                memory_optimizations = await self._optimize_memory()
                result['optimizations_applied'].extend(memory_optimizations)

            # 4. 缓存优化
            if config.get('optimize_cache', True):
                cache_optimizations = await self._optimize_cache()
                result['optimizations_applied'].extend(cache_optimizations)

            # 5. 生成优化建议
            recommendations = await self._generate_optimization_recommendations()
            result['recommendations'] = recommendations

            # 6. 计算性能改进
            performance_improvement = await self._calculate_performance_improvement()
            result['performance_improvement'] = performance_improvement

            result['completed_at'] = datetime.now().isoformat()

            self.logger.info(f"性能优化完成: {len(result['optimizations_applied'])} 项优化, {len(result['recommendations'])} 项建议")

            return result

        except Exception as e:
            self.logger.error(f"性能优化失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'started_at': datetime.now().isoformat()
            }

    async def _optimize_queries(self) -> List[Dict[str, Any]]:
        """优化查询"""
        optimizations = []

        try:
            # 分析慢查询
            slow_queries = await self._identify_slow_queries()

            for query_hash, stats in slow_queries.items():
                # 查询重写建议
                optimization = await self._optimize_query(stats)
                if optimization:
                    optimizations.append({
                        'type': 'query_optimization',
                        'target': query_hash,
                        'original_avg_time': stats.avg_time,
                        'optimization': optimization,
                        'estimated_improvement': optimization.get('estimated_improvement', 0)
                    })

            # 查询缓存优化
            cache_optimization = await self._optimize_query_cache()
            if cache_optimization:
                optimizations.append(cache_optimization)

        except Exception as e:
            self.logger.error(f"查询优化失败: {e}")

        return optimizations

    async def _identify_slow_queries(self) -> Dict[str, QueryStats]:
        """识别慢查询"""
        slow_queries = {}

        try:
            with sqlite3.connect(self.perf_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT query_hash, query_text, execution_count, avg_time,
                           affected_tables, index_usage
                    FROM query_stats
                    WHERE avg_time > ? AND execution_count > ?
                    ORDER BY avg_time DESC
                    LIMIT 20
                ''', (
                    self.config.get('slow_query_threshold', 1.0),  # 1秒
                    self.config.get('min_execution_count', 5)
                ))

                for row in cursor.fetchall():
                    query_hash = row[0]
                    slow_queries[query_hash] = QueryStats(
                        query_hash=query_hash,
                        query_text=row[1],
                        execution_count=row[2],
                        total_time=0,  # 不需要
                        avg_time=row[3],
                        min_time=0,    # 不需要
                        max_time=0,    # 不需要
                        last_executed=datetime.now(),  # 不需要
                        affected_tables=json.loads(row[4]) if row[4] else [],
                        index_usage=json.loads(row[5]) if row[5] else {}
                    )

        except Exception as e:
            self.logger.error(f"识别慢查询失败: {e}")

        return slow_queries

    async def _optimize_query(self, query_stats: QueryStats) -> Optional[Dict[str, Any]]:
        """优化单个查询"""
        try:
            optimization_suggestions = []

            # 分析查询文本（如果有sqlparse）
            if SQLPARSE_AVAILABLE:
                parsed = sqlparse.parse(query_stats.query_text)
                if parsed:
                    # 查找缺失的索引
                    missing_indexes = self._analyze_missing_indexes(parsed[0], query_stats.affected_tables)
                    if missing_indexes:
                        optimization_suggestions.extend(missing_indexes)

            # 基于使用模式的优化建议
            if query_stats.execution_count > 100:
                optimization_suggestions.append({
                    'type': 'add_to_cache',
                    'reason': '高频查询，建议加入缓存',
                    'estimated_improvement': 0.8
                })

            if query_stats.avg_time > 5.0:
                optimization_suggestions.append({
                    'type': 'query_rewrite',
                    'reason': '查询时间过长，建议重写或分解',
                    'estimated_improvement': 0.5
                })

            if optimization_suggestions:
                return {
                    'suggestions': optimization_suggestions,
                    'estimated_improvement': max(s.get('estimated_improvement', 0) for s in optimization_suggestions)
                }

            return None

        except Exception as e:
            self.logger.error(f"查询优化分析失败: {e}")
            return None

    def _analyze_missing_indexes(self, parsed_query, affected_tables: List[str]) -> List[Dict[str, Any]]:
        """分析缺失的索引"""
        suggestions = []

        try:
            # 简单的索引建议逻辑
            # 在实际实现中，需要更复杂的SQL解析和分析

            for table in affected_tables:
                # 检查是否有WHERE子句但缺少对应索引
                if 'WHERE' in str(parsed_query).upper():
                    suggestions.append({
                        'type': 'create_index',
                        'table': table,
                        'reason': '检测到WHERE条件但可能缺少索引',
                        'estimated_improvement': 0.6
                    })

        except Exception as e:
            self.logger.error(f"分析缺失索引失败: {e}")

        return suggestions

    async def _optimize_indexes(self) -> List[Dict[str, Any]]:
        """优化索引"""
        optimizations = []

        try:
            # 识别未使用的索引
            unused_indexes = await self._identify_unused_indexes()
            for index_name in unused_indexes:
                optimizations.append({
                    'type': 'drop_index',
                    'target': index_name,
                    'reason': '索引未被使用，建议删除以节省空间和维护成本',
                    'estimated_improvement': 0.1
                })

            # 识别缺失的索引
            missing_indexes = await self._identify_missing_indexes()
            for index_suggestion in missing_indexes:
                optimizations.append({
                    'type': 'create_index',
                    'target': index_suggestion['table'],
                    'columns': index_suggestion['columns'],
                    'reason': index_suggestion['reason'],
                    'estimated_improvement': index_suggestion.get('estimated_improvement', 0.5)
                })

            # 识别重复的索引
            duplicate_indexes = await self._identify_duplicate_indexes()
            for duplicate_group in duplicate_indexes:
                optimizations.append({
                    'type': 'merge_indexes',
                    'targets': duplicate_group,
                    'reason': '发现重复索引，建议合并',
                    'estimated_improvement': 0.2
                })

        except Exception as e:
            self.logger.error(f"索引优化失败: {e}")

        return optimizations

    async def _identify_unused_indexes(self) -> List[str]:
        """识别未使用的索引"""
        unused_indexes = []

        try:
            threshold_days = self.config.get('unused_index_threshold_days', 30)
            threshold_date = datetime.now() - timedelta(days=threshold_days)

            with sqlite3.connect(self.perf_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT index_name FROM index_stats
                    WHERE (last_used IS NULL OR last_used < ?)
                    AND usage_count < ?
                ''', (threshold_date.isoformat(), self.config.get('min_index_usage', 10)))

                unused_indexes = [row[0] for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"识别未使用索引失败: {e}")

        return unused_indexes

    async def _identify_missing_indexes(self) -> List[Dict[str, Any]]:
        """识别缺失的索引"""
        # 基于查询模式识别可能需要的索引
        return []

    async def _identify_duplicate_indexes(self) -> List[List[str]]:
        """识别重复的索引"""
        # 识别覆盖相同列的索引
        return []

    async def _optimize_memory(self) -> List[Dict[str, Any]]:
        """优化内存使用"""
        optimizations = []

        try:
            # 分析内存使用情况
            memory_info = await self._analyze_memory_usage()

            # 垃圾回收优化
            if memory_info.get('memory_pressure', False):
                gc.collect()
                optimizations.append({
                    'type': 'garbage_collection',
                    'reason': '检测到内存压力，执行垃圾回收',
                    'memory_freed': memory_info.get('memory_freed', 0)
                })

            # 缓存大小调整
            cache_memory = memory_info.get('cache_memory_mb', 0)
            if cache_memory > self.config.get('max_cache_memory_mb', 512):
                optimizations.append({
                    'type': 'reduce_cache_size',
                    'current_size_mb': cache_memory,
                    'recommended_size_mb': self.config.get('max_cache_memory_mb', 512),
                    'reason': '缓存内存使用过多'
                })

            # 数据结构优化
            if PANDAS_AVAILABLE:
                df_memory_optimization = await self._optimize_dataframe_memory()
                if df_memory_optimization:
                    optimizations.append(df_memory_optimization)

        except Exception as e:
            self.logger.error(f"内存优化失败: {e}")

        return optimizations

    async def _analyze_memory_usage(self) -> Dict[str, Any]:
        """分析内存使用情况"""
        try:
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()

            analysis = {
                'total_memory_gb': memory.total / (1024**3),
                'available_memory_gb': memory.available / (1024**3),
                'memory_percent': memory.percent,
                'process_memory_mb': process_memory.rss / (1024**2),
                'memory_pressure': memory.percent > 85
            }

            # 使用pympler分析Python对象内存（如果可用）
            if PYMPLER_AVAILABLE:
                all_objects = muppy.get_objects()
                sum1 = summary.summarize(all_objects)
                analysis['top_objects'] = summary.format_(sum1)[:10]

            return analysis

        except Exception as e:
            self.logger.error(f"内存使用分析失败: {e}")
            return {}

    async def _optimize_dataframe_memory(self) -> Optional[Dict[str, Any]]:
        """优化DataFrame内存使用"""
        # Pandas内存优化逻辑
        return None

    async def _optimize_cache(self) -> List[Dict[str, Any]]:
        """优化缓存"""
        optimizations = []

        try:
            # 缓存命中率分析
            hit_ratio = self.cache_stats['hits'] / (self.cache_stats['hits'] + self.cache_stats['misses']) if (self.cache_stats['hits'] + self.cache_stats['misses']) > 0 else 0

            if hit_ratio < 0.7:
                optimizations.append({
                    'type': 'improve_cache_strategy',
                    'current_hit_ratio': hit_ratio,
                    'reason': '缓存命中率较低，建议调整缓存策略',
                    'recommendations': [
                        '增加缓存大小',
                        '调整缓存过期时间',
                        '优化缓存键策略'
                    ]
                })

            # Redis缓存优化
            if self.redis_client:
                redis_optimization = await self._optimize_redis_cache()
                if redis_optimization:
                    optimizations.append(redis_optimization)

        except Exception as e:
            self.logger.error(f"缓存优化失败: {e}")

        return optimizations

    async def _optimize_redis_cache(self) -> Optional[Dict[str, Any]]:
        """优化Redis缓存"""
        try:
            if not self.redis_client:
                return None

            # 获取Redis信息
            info = self.redis_client.info()
            memory_usage = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)

            if max_memory > 0 and memory_usage / max_memory > 0.8:
                return {
                    'type': 'redis_memory_optimization',
                    'current_usage_mb': memory_usage / (1024**2),
                    'max_memory_mb': max_memory / (1024**2),
                    'usage_percent': (memory_usage / max_memory) * 100,
                    'reason': 'Redis内存使用率过高',
                    'recommendations': [
                        '清理过期键',
                        '调整过期策略',
                        '增加内存限制'
                    ]
                }

            return None

        except Exception as e:
            self.logger.error(f"Redis缓存优化失败: {e}")
            return None

    async def _generate_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """生成优化建议"""
        recommendations = []

        try:
            # 基于性能历史数据生成建议
            if len(self.metrics_history) > 10:
                recent_metrics = list(self.metrics_history)[-10:]

                # CPU使用建议
                avg_cpu = statistics.mean([m.cpu_percent for m in recent_metrics])
                if avg_cpu > 80:
                    recommendations.append({
                        'type': 'cpu_optimization',
                        'priority': 'high',
                        'description': f'平均CPU使用率 {avg_cpu:.1f}%，建议优化计算密集型操作',
                        'suggestions': [
                            '启用异步处理',
                            '增加并发工作线程',
                            '优化算法复杂度'
                        ]
                    })

                # 内存使用建议
                avg_memory = statistics.mean([m.memory_percent for m in recent_metrics])
                if avg_memory > 85:
                    recommendations.append({
                        'type': 'memory_optimization',
                        'priority': 'high',
                        'description': f'平均内存使用率 {avg_memory:.1f}%，建议优化内存使用',
                        'suggestions': [
                            '增加内存容量',
                            '优化数据结构',
                            '实施内存池'
                        ]
                    })

                # 查询性能建议
                avg_query_time = statistics.mean([m.avg_query_time for m in recent_metrics if m.avg_query_time > 0])
                if avg_query_time > 1.0:
                    recommendations.append({
                        'type': 'query_performance',
                        'priority': 'medium',
                        'description': f'平均查询时间 {avg_query_time:.2f}秒，建议优化查询性能',
                        'suggestions': [
                            '添加必要索引',
                            '优化查询语句',
                            '启用查询缓存'
                        ]
                    })

        except Exception as e:
            self.logger.error(f"生成优化建议失败: {e}")

        return recommendations

    async def _calculate_performance_improvement(self) -> Dict[str, Any]:
        """计算性能改进"""
        try:
            if len(self.metrics_history) < 20:
                return {'message': '数据不足，无法计算性能改进'}

            recent_metrics = list(self.metrics_history)
            before_metrics = recent_metrics[-20:-10]  # 优化前
            after_metrics = recent_metrics[-10:]      # 优化后

            before_avg_cpu = statistics.mean([m.cpu_percent for m in before_metrics])
            after_avg_cpu = statistics.mean([m.cpu_percent for m in after_metrics])

            before_avg_memory = statistics.mean([m.memory_percent for m in before_metrics])
            after_avg_memory = statistics.mean([m.memory_percent for m in after_metrics])

            before_avg_query_time = statistics.mean([m.avg_query_time for m in before_metrics if m.avg_query_time > 0])
            after_avg_query_time = statistics.mean([m.avg_query_time for m in after_metrics if m.avg_query_time > 0])

            return {
                'cpu_improvement_percent': ((before_avg_cpu - after_avg_cpu) / before_avg_cpu * 100) if before_avg_cpu > 0 else 0,
                'memory_improvement_percent': ((before_avg_memory - after_avg_memory) / before_avg_memory * 100) if before_avg_memory > 0 else 0,
                'query_time_improvement_percent': ((before_avg_query_time - after_avg_query_time) / before_avg_query_time * 100) if before_avg_query_time > 0 else 0,
                'before_metrics': {
                    'avg_cpu_percent': before_avg_cpu,
                    'avg_memory_percent': before_avg_memory,
                    'avg_query_time': before_avg_query_time
                },
                'after_metrics': {
                    'avg_cpu_percent': after_avg_cpu,
                    'avg_memory_percent': after_avg_memory,
                    'avg_query_time': after_avg_query_time
                }
            }

        except Exception as e:
            self.logger.error(f"计算性能改进失败: {e}")
            return {'error': str(e)}

    async def track_query_performance(self, query: str, execution_time: float, affected_tables: List[str] = None):
        """跟踪查询性能"""
        try:
            query_hash = hashlib.md5(query.encode()).hexdigest()
            affected_tables = affected_tables or []

            # 更新最近查询记录
            with self._lock:
                self.recent_queries.append({
                    'query_hash': query_hash,
                    'query': query,
                    'execution_time': execution_time,
                    'timestamp': datetime.now(),
                    'affected_tables': affected_tables
                })

            # 更新统计信息
            await self._update_query_stats(query_hash, query, execution_time, affected_tables)

        except Exception as e:
            self.logger.error(f"跟踪查询性能失败: {e}")

    async def _update_query_stats(self, query_hash: str, query: str, execution_time: float, affected_tables: List[str]):
        """更新查询统计"""
        try:
            with sqlite3.connect(self.perf_db_path) as conn:
                cursor = conn.cursor()

                # 检查是否已存在
                cursor.execute('SELECT execution_count, total_time, min_time, max_time FROM query_stats WHERE query_hash = ?', (query_hash,))
                result = cursor.fetchone()

                if result:
                    # 更新现有记录
                    count, total_time, min_time, max_time = result
                    new_count = count + 1
                    new_total_time = total_time + execution_time
                    new_avg_time = new_total_time / new_count
                    new_min_time = min(min_time, execution_time)
                    new_max_time = max(max_time, execution_time)

                    cursor.execute('''
                        UPDATE query_stats
                        SET execution_count = ?, total_time = ?, avg_time = ?,
                            min_time = ?, max_time = ?, last_executed = ?,
                            affected_tables = ?, updated_at = ?
                        WHERE query_hash = ?
                    ''', (
                        new_count, new_total_time, new_avg_time,
                        new_min_time, new_max_time, datetime.now().isoformat(),
                        json.dumps(affected_tables), datetime.now().isoformat(),
                        query_hash
                    ))
                else:
                    # 插入新记录
                    cursor.execute('''
                        INSERT INTO query_stats
                        (query_hash, query_text, execution_count, total_time, avg_time,
                         min_time, max_time, last_executed, affected_tables)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        query_hash, query, 1, execution_time, execution_time,
                        execution_time, execution_time, datetime.now().isoformat(),
                        json.dumps(affected_tables)
                    ))

                conn.commit()

        except Exception as e:
            self.logger.error(f"更新查询统计失败: {e}")

    async def generate_performance_report(self, report_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成性能报告"""
        try:
            config = report_config or {}

            report = {
                'report_id': f"perf_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'generated_at': datetime.now().isoformat(),
                'summary': {},
                'detailed_metrics': {},
                'top_queries': {},
                'optimization_history': {},
                'recommendations': []
            }

            # 性能摘要
            report['summary'] = await self._generate_performance_summary()

            # 详细指标
            if config.get('include_detailed_metrics', True):
                report['detailed_metrics'] = await self._generate_detailed_metrics()

            # 热门查询
            if config.get('include_top_queries', True):
                report['top_queries'] = await self._generate_top_queries_report()

            # 优化历史
            if config.get('include_optimization_history', True):
                report['optimization_history'] = await self._generate_optimization_history()

            # 优化建议
            if config.get('include_recommendations', True):
                report['recommendations'] = await self._generate_optimization_recommendations()

            return report

        except Exception as e:
            self.logger.error(f"生成性能报告失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }

    async def _generate_performance_summary(self) -> Dict[str, Any]:
        """生成性能摘要"""
        try:
            if not self.metrics_history:
                return {'message': '暂无性能数据'}

            recent_metrics = list(self.metrics_history)[-60:]  # 最近1小时

            return {
                'time_range': {
                    'start': recent_metrics[0].timestamp.isoformat(),
                    'end': recent_metrics[-1].timestamp.isoformat(),
                    'duration_minutes': len(recent_metrics)
                },
                'averages': {
                    'cpu_percent': statistics.mean([m.cpu_percent for m in recent_metrics]),
                    'memory_percent': statistics.mean([m.memory_percent for m in recent_metrics]),
                    'avg_query_time': statistics.mean([m.avg_query_time for m in recent_metrics if m.avg_query_time > 0]),
                    'cache_hit_ratio': statistics.mean([m.cache_hit_ratio for m in recent_metrics if m.cache_hit_ratio > 0])
                },
                'peaks': {
                    'max_cpu_percent': max([m.cpu_percent for m in recent_metrics]),
                    'max_memory_percent': max([m.memory_percent for m in recent_metrics]),
                    'max_query_time': max([m.avg_query_time for m in recent_metrics if m.avg_query_time > 0], default=0)
                },
                'total_queries': sum([m.query_count for m in recent_metrics])
            }

        except Exception as e:
            self.logger.error(f"生成性能摘要失败: {e}")
            return {'error': str(e)}

    async def _analyze_performance(self):
        """分析性能趋势"""
        try:
            if len(self.metrics_history) < 10:
                return

            # 检测性能异常
            await self._detect_performance_anomalies()

            # 定期优化建议
            if len(self.metrics_history) % 60 == 0:  # 每小时
                await self._generate_periodic_recommendations()

        except Exception as e:
            self.logger.error(f"性能分析失败: {e}")

    async def _detect_performance_anomalies(self):
        """检测性能异常"""
        try:
            if len(self.metrics_history) < 20:
                return

            recent_metrics = list(self.metrics_history)[-20:]
            latest_metric = recent_metrics[-1]

            # CPU异常检测
            cpu_values = [m.cpu_percent for m in recent_metrics[:-1]]
            cpu_mean = statistics.mean(cpu_values)
            cpu_stdev = statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0

            if cpu_stdev > 0 and abs(latest_metric.cpu_percent - cpu_mean) > 2 * cpu_stdev:
                self.logger.warning(f"检测到CPU使用异常: 当前 {latest_metric.cpu_percent:.1f}%, 平均 {cpu_mean:.1f}%")

            # 内存异常检测
            memory_values = [m.memory_percent for m in recent_metrics[:-1]]
            memory_mean = statistics.mean(memory_values)
            memory_stdev = statistics.stdev(memory_values) if len(memory_values) > 1 else 0

            if memory_stdev > 0 and abs(latest_metric.memory_percent - memory_mean) > 2 * memory_stdev:
                self.logger.warning(f"检测到内存使用异常: 当前 {latest_metric.memory_percent:.1f}%, 平均 {memory_mean:.1f}%")

        except Exception as e:
            self.logger.error(f"性能异常检测失败: {e}")

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

            if self.redis_client:
                try:
                    self.redis_client.close()
                except:
                    pass

            self.logger.info("性能优化器资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")


async def main():
    """测试主函数"""
    config = {
        'perf_db_path': 'data/test_performance.db',
        'monitoring_enabled': True,
        'optimization_interval': 60,
        'slow_query_threshold': 0.1,
        'min_execution_count': 1
    }

    async with PerformanceOptimizer(config) as optimizer:
        # 模拟查询跟踪
        await optimizer.track_query_performance(
            query="SELECT * FROM financial_data WHERE account_code = '1001'",
            execution_time=0.5,
            affected_tables=['financial_data']
        )

        await optimizer.track_query_performance(
            query="SELECT SUM(amount) FROM transactions WHERE date > '2024-01-01'",
            execution_time=2.1,
            affected_tables=['transactions']
        )

        # 执行性能优化
        optimization_result = await optimizer.optimize_performance({
            'optimize_queries': True,
            'optimize_indexes': True,
            'optimize_memory': True,
            'optimize_cache': True
        })

        print(f"性能优化结果: {json.dumps(optimization_result, indent=2, ensure_ascii=False)}")

        # 生成性能报告
        performance_report = await optimizer.generate_performance_report()
        print(f"性能报告: {json.dumps(performance_report, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
