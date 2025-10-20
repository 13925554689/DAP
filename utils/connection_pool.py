#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 数据库连接池管理器
提供高效的数据库连接管理和优化
"""

import sqlite3
import threading
import time
import logging
from contextlib import contextmanager
from queue import Queue, Empty, Full
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConnectionStats:
    """连接统计信息"""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    average_wait_time: float = 0.0
    peak_connections: int = 0


class DatabaseConnection:
    """数据库连接包装器"""

    def __init__(self, connection: sqlite3.Connection, pool: "ConnectionPool"):
        self.connection = connection
        self.pool = pool
        self.created_at = time.time()
        self.last_used = time.time()
        self.in_use = False
        self.transaction_count = 0

    def __enter__(self):
        self.in_use = True
        self.last_used = time.time()
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.in_use = False
        if exc_type:
            # 发生异常时回滚事务
            try:
                self.connection.rollback()
            except Exception as e:
                logger.error(f"回滚事务失败: {e}")

        # 返回连接到池中
        self.pool._return_connection(self)

    def is_valid(self) -> bool:
        """检查连接是否有效"""
        try:
            self.connection.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_age(self) -> float:
        """获取连接年龄（秒）"""
        return time.time() - self.created_at

    def get_idle_time(self) -> float:
        """获取空闲时间（秒）"""
        return time.time() - self.last_used


class ConnectionPool:
    """SQLite连接池"""

    def __init__(
        self,
        database_path: str,
        pool_size: int = 10,
        max_connections: int = 20,
        connection_timeout: float = 30.0,
        idle_timeout: float = 300.0,
    ):
        self.database_path = database_path
        self.pool_size = pool_size
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout

        # 连接池和统计
        self._pool: Queue = Queue(maxsize=max_connections)
        self._active_connections: Dict[int, DatabaseConnection] = {}
        self._stats = ConnectionStats()
        self._lock = threading.RLock()

        # 初始化连接池
        self._initialize_pool()

        # 启动维护线程
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_worker, daemon=True
        )
        self._maintenance_thread.start()

        logger.info(f"连接池初始化完成: {database_path}, 池大小: {pool_size}")

    def _initialize_pool(self):
        """初始化连接池"""
        for _ in range(self.pool_size):
            try:
                conn = self._create_connection()
                db_conn = DatabaseConnection(conn, self)
                self._pool.put(db_conn, block=False)
                self._stats.total_connections += 1
                self._stats.idle_connections += 1
            except Exception as e:
                logger.error(f"初始化连接失败: {e}")

    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(
            self.database_path, timeout=self.connection_timeout, check_same_thread=False
        )

        # 配置SQLite优化参数
        optimizations = [
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA cache_size=10000",
            "PRAGMA foreign_keys=ON",
            "PRAGMA temp_store=memory",
            "PRAGMA mmap_size=268435456",  # 256MB
        ]

        for pragma in optimizations:
            try:
                conn.execute(pragma)
            except Exception as e:
                logger.warning(f"SQLite优化失败: {pragma} - {e}")

        return conn

    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        start_time = time.time()
        connection = None

        try:
            # 更新统计
            with self._lock:
                self._stats.total_requests += 1

            # 尝试从池中获取连接
            try:
                connection = self._pool.get(timeout=self.connection_timeout)
                with self._lock:
                    self._stats.idle_connections -= 1
                    self._stats.active_connections += 1
                    if self._stats.active_connections > self._stats.peak_connections:
                        self._stats.peak_connections = self._stats.active_connections
            except Empty:
                # 池中无可用连接，尝试创建新连接
                if self._stats.total_connections < self.max_connections:
                    conn = self._create_connection()
                    connection = DatabaseConnection(conn, self)
                    with self._lock:
                        self._stats.total_connections += 1
                        self._stats.active_connections += 1
                else:
                    raise RuntimeError("连接池已满，无法获取新连接")

            # 检查连接有效性
            if not connection.is_valid():
                logger.warning("检测到无效连接，重新创建")
                connection.connection.close()
                conn = self._create_connection()
                connection.connection = conn

            # 记录连接信息
            with self._lock:
                self._active_connections[id(connection)] = connection

            # 更新等待时间统计
            wait_time = time.time() - start_time
            with self._lock:
                self._stats.average_wait_time = (
                    self._stats.average_wait_time * (self._stats.total_requests - 1)
                    + wait_time
                ) / self._stats.total_requests

            yield connection.connection

        except Exception as e:
            with self._lock:
                self._stats.failed_requests += 1
            logger.error(f"获取数据库连接失败: {e}")
            raise

        finally:
            if connection:
                self._return_connection(connection)

    def _return_connection(self, connection: DatabaseConnection):
        """返回连接到池中"""
        try:
            with self._lock:
                # 从活跃连接中移除
                if id(connection) in self._active_connections:
                    del self._active_connections[id(connection)]
                self._stats.active_connections -= 1

                # 检查连接是否可重用
                if (
                    connection.is_valid()
                    and connection.get_age() < self.idle_timeout
                    and not self._pool.full()
                ):
                    connection.last_used = time.time()
                    self._pool.put(connection, block=False)
                    self._stats.idle_connections += 1
                else:
                    # 关闭过期或无效连接
                    connection.connection.close()
                    self._stats.total_connections -= 1

        except Exception as e:
            logger.error(f"返回连接失败: {e}")

    def _maintenance_worker(self):
        """维护工作线程"""
        while True:
            try:
                time.sleep(60)  # 每分钟维护一次
                self._cleanup_idle_connections()
                self._ensure_minimum_connections()
            except Exception as e:
                logger.error(f"连接池维护失败: {e}")

    def _cleanup_idle_connections(self):
        """清理空闲连接"""
        with self._lock:
            # 检查池中的空闲连接
            temp_connections = []

            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    if conn.is_valid() and conn.get_idle_time() < self.idle_timeout:
                        temp_connections.append(conn)
                    else:
                        # 关闭过期连接
                        conn.connection.close()
                        self._stats.total_connections -= 1
                        self._stats.idle_connections -= 1
                except Empty:
                    break

            # 将有效连接放回池中
            for conn in temp_connections:
                try:
                    self._pool.put_nowait(conn)
                except Full:
                    conn.connection.close()
                    self._stats.total_connections -= 1
                    self._stats.idle_connections -= 1

    def _ensure_minimum_connections(self):
        """确保最少连接数"""
        with self._lock:
            while (
                self._stats.idle_connections < self.pool_size
                and self._stats.total_connections < self.max_connections
            ):
                try:
                    conn = self._create_connection()
                    db_conn = DatabaseConnection(conn, self)
                    self._pool.put_nowait(db_conn)
                    self._stats.total_connections += 1
                    self._stats.idle_connections += 1
                except Exception as e:
                    logger.error(f"创建最少连接失败: {e}")
                    break

    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        with self._lock:
            return asdict(self._stats)

    def close_all(self):
        """关闭所有连接"""
        logger.info("关闭连接池中的所有连接")

        with self._lock:
            # 关闭池中的空闲连接
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.connection.close()
                except Empty:
                    break

            # 关闭活跃连接
            for conn in self._active_connections.values():
                try:
                    conn.connection.close()
                except Exception as e:
                    logger.error(f"关闭活跃连接失败: {e}")

            # 重置统计
            self._stats = ConnectionStats()
            self._active_connections.clear()


# 全局连接池实例
_connection_pools: Dict[str, ConnectionPool] = {}
_pool_lock = threading.Lock()


class DatabaseConnectionPool(ConnectionPool):
    """Backwards compatible alias for legacy imports."""

    pass


def get_connection_pool(database_path: str, **kwargs) -> ConnectionPool:
    """获取或创建连接池"""
    if database_path == ":memory:":
        return ConnectionPool(database_path, **kwargs)

    with _pool_lock:
        if database_path not in _connection_pools:
            _connection_pools[database_path] = ConnectionPool(database_path, **kwargs)
        return _connection_pools[database_path]


def close_all_pools():
    """关闭所有连接池"""
    with _pool_lock:
        for pool in _connection_pools.values():
            pool.close_all()
        _connection_pools.clear()


if __name__ == "__main__":
    # 测试连接池
    import tempfile
    import os

    # 创建临时数据库
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db.close()

    try:
        # 创建连接池
        pool = ConnectionPool(temp_db.name, pool_size=5, max_connections=10)

        # 测试获取连接
        print("测试连接池...")

        with pool.get_connection() as conn:
            with conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("INSERT INTO test (name) VALUES (?)", ("test",))

        # 显示统计信息
        stats = pool.get_stats()
        print(f"连接池统计:")
        print(f"  总连接数: {stats.total_connections}")
        print(f"  活跃连接数: {stats.active_connections}")
        print(f"  空闲连接数: {stats.idle_connections}")
        print(f"  总请求数: {stats.total_requests}")
        print(f"  平均等待时间: {stats.average_wait_time:.3f}s")

        # 关闭连接池
        pool.close_all()

    finally:
        # 清理临时文件
        os.unlink(temp_db.name)

    print("连接池测试完成")
