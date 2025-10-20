#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 智能缓存管理器
提供多级缓存、LRU淘汰、TTL过期等高级缓存功能
"""

import time
import pickle
import hashlib
import os
import threading
import logging
from typing import Any, Optional, Dict, Callable, Union
from collections import OrderedDict
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage: int = 0
    disk_usage: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheEntry:
    """缓存条目"""
    
    def __init__(self, value: Any, ttl: Optional[float] = None):
        self.value = value
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 1
        self.ttl = ttl
        self.size = self._calculate_size(value)
    
    def _calculate_size(self, value: Any) -> int:
        """计算值的内存大小"""
        try:
            if hasattr(value, '__sizeof__'):
                return value.__sizeof__()
            return len(pickle.dumps(value))
        except Exception:
            return 1000  # 默认大小
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def access(self) -> Any:
        """访问缓存项"""
        self.last_accessed = time.time()
        self.access_count += 1
        return self.value
    
    def get_age(self) -> float:
        """获取年龄（秒）"""
        return time.time() - self.created_at


class MemoryCache:
    """内存缓存（LRU + TTL）"""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            # 检查是否过期
            if entry.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                return None
            
            # 移动到末尾（LRU更新）
            self._cache.move_to_end(key)
            self._stats.hits += 1
            
            return entry.access()
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        with self._lock:
            if ttl is None:
                ttl = self.default_ttl
            
            entry = CacheEntry(value, ttl)
            
            # 如果键已存在，更新并移动到末尾
            if key in self._cache:
                old_entry = self._cache[key]
                self._stats.memory_usage -= old_entry.size
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            self._stats.memory_usage += entry.size
            
            # 检查大小限制
            self._evict_if_needed()
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._stats.memory_usage -= entry.size
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._stats.memory_usage = 0
    
    def _evict_if_needed(self) -> None:
        """根据需要淘汰缓存项"""
        while len(self._cache) > self.max_size:
            # 淘汰最久未使用的项
            key, entry = self._cache.popitem(last=False)
            self._stats.memory_usage -= entry.size
            self._stats.evictions += 1
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                entry = self._cache.pop(key)
                self._stats.memory_usage -= entry.size
                self._stats.evictions += 1
            
            return len(expired_keys)
    
    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                memory_usage=self._stats.memory_usage
            )


class DiskCache:
    """磁盘缓存"""
    
    def __init__(self, cache_dir: str = 'cache', max_size: int = 1000):
        self.cache_dir = cache_dir
        self.max_size = max_size
        self._stats = CacheStats()
        self._lock = threading.Lock()
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
        # 加载现有缓存统计
        self._scan_cache_directory()
    
    def _get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        # 使用MD5哈希作为文件名
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_key}.cache")
    
    def _scan_cache_directory(self) -> None:
        """扫描缓存目录统计"""
        try:
            total_size = 0
            for file_name in os.listdir(self.cache_dir):
                if file_name.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, file_name)
                    total_size += os.path.getsize(file_path)
            
            self._stats.disk_usage = total_size
        except Exception as e:
            logger.warning(f"扫描缓存目录失败: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        cache_path = self._get_cache_path(key)
        
        try:
            if not os.path.exists(cache_path):
                self._stats.misses += 1
                return None
            
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
            
            # 检查TTL
            if 'ttl' in data and data['ttl'] is not None:
                age = time.time() - data['created_at']
                if age > data['ttl']:
                    os.remove(cache_path)
                    self._stats.misses += 1
                    self._stats.evictions += 1
                    return None
            
            self._stats.hits += 1
            return data['value']
            
        except Exception as e:
            logger.warning(f"读取磁盘缓存失败 {key}: {e}")
            self._stats.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        cache_path = self._get_cache_path(key)
        
        try:
            data = {
                'value': value,
                'created_at': time.time(),
                'ttl': ttl
            }
            
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            
            # 更新磁盘使用统计
            file_size = os.path.getsize(cache_path)
            with self._lock:
                self._stats.disk_usage += file_size
            
            # 检查磁盘缓存大小限制
            self._cleanup_if_needed()
            
        except Exception as e:
            logger.error(f"写入磁盘缓存失败 {key}: {e}")
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        cache_path = self._get_cache_path(key)
        
        try:
            if os.path.exists(cache_path):
                file_size = os.path.getsize(cache_path)
                os.remove(cache_path)
                
                with self._lock:
                    self._stats.disk_usage -= file_size
                
                return True
            return False
            
        except Exception as e:
            logger.error(f"删除磁盘缓存失败 {key}: {e}")
            return False
    
    def clear(self) -> None:
        """清空磁盘缓存"""
        try:
            for file_name in os.listdir(self.cache_dir):
                if file_name.endswith('.cache'):
                    os.remove(os.path.join(self.cache_dir, file_name))
            
            self._stats.disk_usage = 0
            
        except Exception as e:
            logger.error(f"清空磁盘缓存失败: {e}")
    
    def _cleanup_if_needed(self) -> None:
        """根据需要清理磁盘缓存"""
        try:
            # 获取所有缓存文件信息
            cache_files = []
            for file_name in os.listdir(self.cache_dir):
                if file_name.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, file_name)
                    stat = os.stat(file_path)
                    cache_files.append({
                        'path': file_path,
                        'mtime': stat.st_mtime,
                        'size': stat.st_size
                    })
            
            # 如果超过最大数量，删除最旧的文件
            if len(cache_files) > self.max_size:
                # 按修改时间排序
                cache_files.sort(key=lambda x: x['mtime'])
                
                files_to_remove = len(cache_files) - self.max_size
                for i in range(files_to_remove):
                    file_info = cache_files[i]
                    os.remove(file_info['path'])
                    
                    with self._lock:
                        self._stats.disk_usage -= file_info['size']
                        self._stats.evictions += 1
                        
        except Exception as e:
            logger.error(f"清理磁盘缓存失败: {e}")
    
    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            evictions=self._stats.evictions,
            disk_usage=self._stats.disk_usage
        )


class MultiLevelCache:
    """多级缓存（内存 + 磁盘）"""
    
    def __init__(self,
                 memory_size: int = 1000,
                 disk_size: int = 10000,
                 cache_dir: str = 'cache',
                 default_ttl: Optional[float] = None):
        
        self.memory_cache = MemoryCache(memory_size, default_ttl)
        self.disk_cache = DiskCache(cache_dir, disk_size)
        self.default_ttl = default_ttl
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True
        )
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值（先内存后磁盘）"""
        # 首先尝试内存缓存
        value = self.memory_cache.get(key)
        if value is not None:
            return value
        
        # 内存缓存未命中，尝试磁盘缓存
        value = self.disk_cache.get(key)
        if value is not None:
            # 将热数据提升到内存缓存
            self.memory_cache.set(key, value, self.default_ttl)
            return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None,
            memory_only: bool = False) -> None:
        """设置缓存值"""
        if ttl is None:
            ttl = self.default_ttl
        
        # 设置内存缓存
        self.memory_cache.set(key, value, ttl)
        
        # 同时设置磁盘缓存（除非指定仅内存）
        if not memory_only:
            self.disk_cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        memory_deleted = self.memory_cache.delete(key)
        disk_deleted = self.disk_cache.delete(key)
        return memory_deleted or disk_deleted
    
    def clear(self) -> None:
        """清空所有缓存"""
        self.memory_cache.clear()
        self.disk_cache.clear()
    
    def _cleanup_worker(self) -> None:
        """清理工作线程"""
        while True:
            try:
                time.sleep(300)  # 每5分钟清理一次
                self.memory_cache.cleanup_expired()
            except Exception as e:
                logger.error(f"缓存清理失败: {e}")
    
    def get_stats(self) -> Dict[str, CacheStats]:
        """获取统计信息"""
        return {
            'memory': self.memory_cache.get_stats(),
            'disk': self.disk_cache.get_stats()
        }


# 全局缓存实例
_global_cache: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = MultiLevelCache()
    return _global_cache


def cached(ttl: Optional[float] = None, 
          memory_only: bool = False,
          key_func: Optional[Callable] = None):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认使用函数名和参数生成键
                key_parts = [func.__name__]
                if args:
                    key_parts.extend(str(arg) for arg in args)
                if kwargs:
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = "|".join(key_parts)
            
            # 尝试从缓存获取
            cache = get_cache()
            result = cache.get(cache_key)
            
            if result is not None:
                return result
            
            # 缓存未命中，执行函数
            result = func(*args, **kwargs)
            
            # 存储到缓存
            cache.set(cache_key, result, ttl, memory_only)
            
            return result
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # 测试缓存系统
    import tempfile
    import shutil
    
    # 创建临时缓存目录
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 测试多级缓存
        cache = MultiLevelCache(
            memory_size=5,
            disk_size=10,
            cache_dir=temp_dir,
            default_ttl=300
        )
        
        print("=== 多级缓存测试 ===")
        
        # 设置一些测试数据
        test_data = {
            'key1': 'value1',
            'key2': {'data': 'complex_value'},
            'key3': [1, 2, 3, 4, 5],
            'key4': 'value4'
        }
        
        # 写入缓存
        for key, value in test_data.items():
            cache.set(key, value)
            print(f"设置缓存: {key} = {value}")
        
        # 读取缓存
        for key in test_data.keys():
            value = cache.get(key)
            print(f"读取缓存: {key} = {value}")
        
        # 显示统计信息
        stats = cache.get_stats()
        print(f"\n缓存统计:")
        for level, stat in stats.items():
            print(f"  {level}:")
            print(f"    命中率: {stat.hit_rate:.2%}")
            print(f"    命中: {stat.hits}, 未命中: {stat.misses}")
            print(f"    淘汰: {stat.evictions}")
            if level == 'memory':
                print(f"    内存使用: {stat.memory_usage} bytes")
            else:
                print(f"    磁盘使用: {stat.disk_usage} bytes")
        
        # 测试缓存装饰器
        print(f"\n=== 缓存装饰器测试 ===")
        
        @cached(ttl=60)
        def expensive_function(n: int) -> int:
            print(f"执行耗时计算: {n}")
            return n * n
        
        # 第一次调用
        result1 = expensive_function(10)
        print(f"第一次调用结果: {result1}")
        
        # 第二次调用（应该从缓存获取）
        result2 = expensive_function(10)
        print(f"第二次调用结果: {result2}")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
        
    print("缓存测试完成")