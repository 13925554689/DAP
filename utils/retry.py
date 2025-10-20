"""
DAP - 重试机制装饰器
提供智能重试功能
"""

import time
import logging
from functools import wraps
from typing import Type, Tuple, Callable, Any
from .exceptions import DAPException, DataIngestionError, StorageError

logger = logging.getLogger(__name__)

def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    exclude_exceptions: Tuple[Type[Exception], ...] = (),
    on_retry: Callable[[int, Exception], None] = None
):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避倍数
        exceptions: 需要重试的异常类型
        exclude_exceptions: 不重试的异常类型
        on_retry: 重试时的回调函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except exclude_exceptions as e:
                    # 不重试的异常直接抛出
                    logger.warning(f"函数 {func.__name__} 遇到不重试异常: {e}")
                    raise
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # 最后一次尝试失败
                        logger.error(f"函数 {func.__name__} 重试 {max_attempts} 次后仍失败: {e}")
                        raise
                    
                    # 记录重试信息
                    logger.warning(
                        f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}, "
                        f"将在 {current_delay:.1f} 秒后重试"
                    )
                    
                    # 调用重试回调
                    if on_retry:
                        try:
                            on_retry(attempt + 1, e)
                        except Exception as callback_error:
                            logger.error(f"重试回调函数执行失败: {callback_error}")
                    
                    # 等待后重试
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
                except Exception as e:
                    # 未预期的异常类型
                    logger.error(f"函数 {func.__name__} 遇到未预期异常: {e}")
                    raise
                    
            # 理论上不会到达这里
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

def smart_retry(func):
    """
    智能重试装饰器，根据异常类型自动选择重试策略
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DataIngestionError as e:
            # 数据接入错误，短延迟重试
            return retry(
                max_attempts=2,
                delay=0.5,
                exceptions=(DataIngestionError,)
            )(func)(*args, **kwargs)
        except StorageError as e:
            # 存储错误，长延迟重试
            return retry(
                max_attempts=3,
                delay=2.0,
                exceptions=(StorageError,)
            )(func)(*args, **kwargs)
        except Exception as e:
            # 其他异常，默认重试策略
            return retry(
                max_attempts=2,
                delay=1.0
            )(func)(*args, **kwargs)
    
    return wrapper

class RetryManager:
    """重试管理器"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.retry_stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0
        }
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数并在失败时重试"""
        for attempt in range(self.max_attempts):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    self.retry_stats['successful_retries'] += 1
                    logger.info(f"函数 {func.__name__} 在第 {attempt + 1} 次尝试后成功")
                return result
                
            except Exception as e:
                self.retry_stats['total_retries'] += 1
                
                if attempt == self.max_attempts - 1:
                    self.retry_stats['failed_retries'] += 1
                    logger.error(f"函数 {func.__name__} 重试 {self.max_attempts} 次后仍失败: {e}")
                    raise
                
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}, 等待 {delay:.1f} 秒后重试")
                time.sleep(delay)
    
    def get_stats(self) -> dict:
        """获取重试统计信息"""
        return self.retry_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.retry_stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0
        }

# 全局重试管理器实例
global_retry_manager = RetryManager()

def with_retry_manager(func):
    """使用全局重试管理器的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return global_retry_manager.execute_with_retry(func, *args, **kwargs)
    return wrapper