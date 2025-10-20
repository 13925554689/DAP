#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 性能优化工具
提供内存优化、并行处理、流式处理等性能提升功能
"""

import gc
import psutil
import pandas as pd
import numpy as np
import logging
import time
import threading
from typing import Iterator, Callable, Any, List, Dict, Optional, Union
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from functools import wraps
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    execution_time: float = 0.0
    memory_before: float = 0.0
    memory_after: float = 0.0
    memory_peak: float = 0.0
    cpu_usage: float = 0.0
    
    @property
    def memory_delta(self) -> float:
        return self.memory_after - self.memory_before


class MemoryOptimizer:
    """内存优化器"""
    
    @staticmethod
    def optimize_dataframe_dtypes(df: pd.DataFrame, 
                                 inplace: bool = False) -> pd.DataFrame:
        """优化DataFrame数据类型以节省内存"""
        if not inplace:
            df = df.copy()
        
        original_size = df.memory_usage(deep=True).sum()
        
        for col in df.columns:
            col_type = df[col].dtype
            
            if col_type == 'object':
                # 尝试转换为category类型
                unique_ratio = df[col].nunique() / len(df)
                if unique_ratio < 0.1:  # 重复度高的列
                    try:
                        df[col] = df[col].astype('category')
                    except Exception:
                        pass
                        
            elif pd.api.types.is_integer_dtype(col_type):
                # 优化整数类型
                min_val = df[col].min()
                max_val = df[col].max()
                
                if min_val >= 0:  # 无符号整数
                    if max_val < 255:
                        df[col] = df[col].astype('uint8')
                    elif max_val < 65535:
                        df[col] = df[col].astype('uint16')
                    elif max_val < 4294967295:
                        df[col] = df[col].astype('uint32')
                else:  # 有符号整数
                    if min_val >= -128 and max_val <= 127:
                        df[col] = df[col].astype('int8')
                    elif min_val >= -32768 and max_val <= 32767:
                        df[col] = df[col].astype('int16')
                    elif min_val >= -2147483648 and max_val <= 2147483647:
                        df[col] = df[col].astype('int32')
                        
            elif pd.api.types.is_float_dtype(col_type):
                # 优化浮点类型
                try:
                    if df[col].min() >= np.finfo(np.float32).min and \
                       df[col].max() <= np.finfo(np.float32).max:
                        df[col] = df[col].astype('float32')
                except Exception:
                    pass
        
        optimized_size = df.memory_usage(deep=True).sum()
        reduction = (original_size - optimized_size) / original_size * 100
        
        logger.info(f"内存优化完成: {original_size:,} -> {optimized_size:,} bytes "
                   f"({reduction:.1f}% 减少)")
        
        return df
    
    @staticmethod
    def get_memory_usage() -> float:
        """获取当前内存使用率"""
        return psutil.virtual_memory().percent
    
    @staticmethod
    def force_garbage_collection():
        """强制垃圾回收"""
        collected = gc.collect()
        logger.debug(f"垃圾回收: 回收了 {collected} 个对象")
        return collected
    
    @classmethod
    def monitor_memory(cls, threshold: float = 80.0):
        """内存监控装饰器"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 检查内存使用
                memory_before = cls.get_memory_usage()
                
                if memory_before > threshold:
                    logger.warning(f"内存使用率过高: {memory_before:.1f}%")
                    cls.force_garbage_collection()
                
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    memory_after = cls.get_memory_usage()
                    if memory_after > threshold:
                        cls.force_garbage_collection()
                        
            return wrapper
        return decorator


class StreamProcessor:
    """流式数据处理器"""
    
    def __init__(self, chunk_size: int = 10000):
        self.chunk_size = chunk_size
    
    def process_file_in_chunks(self, 
                              file_path: str,
                              processor: Callable[[pd.DataFrame], pd.DataFrame],
                              **read_kwargs) -> Iterator[pd.DataFrame]:
        """分块处理大文件"""
        logger.info(f"开始流式处理文件: {file_path}")
        
        try:
            # 根据文件类型选择读取方法
            if file_path.endswith('.csv'):
                reader = pd.read_csv(file_path, chunksize=self.chunk_size, **read_kwargs)
            elif file_path.endswith(('.xlsx', '.xls')):
                # Excel文件需要特殊处理
                df = pd.read_excel(file_path, **read_kwargs)
                reader = [df[i:i+self.chunk_size] for i in range(0, len(df), self.chunk_size)]
            else:
                raise ValueError(f"不支持的文件格式: {file_path}")
            
            for chunk_idx, chunk in enumerate(reader):
                logger.debug(f"处理数据块 {chunk_idx + 1}, 大小: {len(chunk)}")
                
                try:
                    processed_chunk = processor(chunk)
                    yield processed_chunk
                except Exception as e:
                    logger.error(f"处理数据块失败 {chunk_idx + 1}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"流式处理失败: {e}")
            raise
    
    def aggregate_chunks(self, 
                        chunks: Iterator[pd.DataFrame],
                        output_path: Optional[str] = None) -> pd.DataFrame:
        """聚合处理后的数据块"""
        aggregated_chunks = []
        total_rows = 0
        
        for chunk in chunks:
            aggregated_chunks.append(chunk)
            total_rows += len(chunk)
            
            # 定期检查内存使用
            if len(aggregated_chunks) % 10 == 0:
                memory_usage = MemoryOptimizer.get_memory_usage()
                if memory_usage > 80:
                    logger.warning("内存使用过高，执行中间聚合")
                    # 中间聚合
                    temp_df = pd.concat(aggregated_chunks, ignore_index=True)
                    aggregated_chunks = [temp_df]
        
        logger.info(f"聚合完成: 总行数 {total_rows}")
        
        result = pd.concat(aggregated_chunks, ignore_index=True)
        
        if output_path:
            result.to_csv(output_path, index=False)
            logger.info(f"结果已保存到: {output_path}")
        
        return result


class ParallelProcessor:
    """并行处理器"""
    
    def __init__(self, max_workers: Optional[int] = None, 
                 use_processes: bool = False):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.use_processes = use_processes
        
    def parallel_apply(self,
                      data_list: List[Any],
                      func: Callable,
                      progress_callback: Optional[Callable] = None) -> List[Any]:
        """并行应用函数到数据列表"""
        if not data_list:
            return []
        
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        
        with executor_class(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_index = {
                executor.submit(func, item): idx 
                for idx, item in enumerate(data_list)
            }
            
            # 收集结果
            results = [None] * len(data_list)
            completed = 0
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                
                try:
                    result = future.result()
                    results[index] = result
                    completed += 1
                    
                    if progress_callback:
                        progress_callback(completed, len(data_list))
                        
                except Exception as e:
                    logger.error(f"并行任务失败 {index}: {e}")
                    results[index] = None
        
        return results
    
    def parallel_dataframe_apply(self,
                                df: pd.DataFrame,
                                func: Callable,
                                axis: int = 0,
                                n_partitions: Optional[int] = None) -> pd.DataFrame:
        """并行应用函数到DataFrame"""
        if n_partitions is None:
            n_partitions = self.max_workers
        
        if axis == 0:
            # 按行分割
            partitions = np.array_split(df, n_partitions)
        else:
            # 按列分割
            col_partitions = np.array_split(df.columns, n_partitions)
            partitions = [df[cols] for cols in col_partitions]
        
        # 并行处理分割的数据
        results = self.parallel_apply(partitions, func)
        
        # 合并结果
        if axis == 0:
            return pd.concat([r for r in results if r is not None], 
                           ignore_index=True)
        else:
            return pd.concat([r for r in results if r is not None], 
                           axis=1)


class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
    
    def profile(self, func_name: str = ""):
        """性能分析装饰器"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self._profile_execution(func, func_name or func.__name__, 
                                             *args, **kwargs)
            return wrapper
        return decorator
    
    def _profile_execution(self, func: Callable, name: str, *args, **kwargs) -> Any:
        """执行性能分析"""
        # 获取初始指标
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        cpu_before = psutil.cpu_percent()
        
        start_time = time.time()
        
        try:
            # 执行函数
            result = func(*args, **kwargs)
            
            # 计算指标
            end_time = time.time()
            execution_time = end_time - start_time
            
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            cpu_after = psutil.cpu_percent()
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                execution_time=execution_time,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_peak=max(memory_before, memory_after),
                cpu_usage=(cpu_before + cpu_after) / 2
            )
            
            self.metrics_history.append(metrics)
            
            # 记录性能信息
            logger.info(f"性能分析 [{name}]: "
                       f"执行时间={execution_time:.3f}s, "
                       f"内存变化={metrics.memory_delta:.1f}MB, "
                       f"CPU使用={metrics.cpu_usage:.1f}%")
            
            return result
            
        except Exception as e:
            logger.error(f"性能分析失败 [{name}]: {e}")
            raise
    
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.metrics_history:
            return {}
        
        execution_times = [m.execution_time for m in self.metrics_history]
        memory_deltas = [m.memory_delta for m in self.metrics_history]
        cpu_usages = [m.cpu_usage for m in self.metrics_history]
        
        return {
            'total_executions': len(self.metrics_history),
            'avg_execution_time': np.mean(execution_times),
            'max_execution_time': np.max(execution_times),
            'avg_memory_delta': np.mean(memory_deltas),
            'max_memory_delta': np.max(memory_deltas),
            'avg_cpu_usage': np.mean(cpu_usages),
            'max_cpu_usage': np.max(cpu_usages)
        }


# 全局性能分析器实例
profiler = PerformanceProfiler()


# 便捷装饰器
def profile_performance(name: str = ""):
    """性能分析装饰器"""
    return profiler.profile(name)


def optimize_memory(threshold: float = 80.0):
    """内存优化装饰器"""
    return MemoryOptimizer.monitor_memory(threshold)


if __name__ == "__main__":
    # 测试性能优化工具
    import tempfile
    import os
    
    print("=== 性能优化工具测试 ===")
    
    # 测试DataFrame内存优化
    print("\n1. DataFrame内存优化测试")
    
    # 创建测试数据
    test_data = pd.DataFrame({
        'int_col': np.random.randint(0, 100, 10000),
        'float_col': np.random.random(10000),
        'category_col': np.random.choice(['A', 'B', 'C'], 10000),
        'text_col': [f"text_{i}" for i in range(10000)]
    })
    
    print(f"原始大小: {test_data.memory_usage(deep=True).sum():,} bytes")
    print(f"原始类型:")
    print(test_data.dtypes)
    
    # 优化内存
    optimized_data = MemoryOptimizer.optimize_dataframe_dtypes(test_data)
    
    print(f"\n优化后大小: {optimized_data.memory_usage(deep=True).sum():,} bytes")
    print(f"优化后类型:")
    print(optimized_data.dtypes)
    
    # 测试性能分析器
    print("\n2. 性能分析器测试")
    
    @profile_performance("test_function")
    def test_function(n: int) -> int:
        # 模拟耗时操作
        result = 0
        for i in range(n):
            result += i ** 2
        return result
    
    # 执行测试函数
    result = test_function(1000000)
    print(f"函数结果: {result}")
    
    # 显示性能摘要
    summary = profiler.get_summary()
    print(f"性能摘要: {summary}")
    
    # 测试并行处理器
    print("\n3. 并行处理器测试")
    
    processor = ParallelProcessor(max_workers=4)
    
    def square_function(x):
        return x ** 2
    
    test_numbers = list(range(100))
    
    # 串行处理时间
    start_time = time.time()
    serial_results = [square_function(x) for x in test_numbers]
    serial_time = time.time() - start_time
    
    # 并行处理时间
    start_time = time.time()
    parallel_results = processor.parallel_apply(test_numbers, square_function)
    parallel_time = time.time() - start_time
    
    print(f"串行处理时间: {serial_time:.4f}s")
    print(f"并行处理时间: {parallel_time:.4f}s")
    print(f"加速比: {serial_time/parallel_time:.2f}x")
    
    # 验证结果一致性
    assert serial_results == parallel_results, "结果不一致！"
    print("结果验证通过")
    
    print("\n性能优化工具测试完成")