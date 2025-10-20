"""
DAP - 统一异常处理模块
定义系统中使用的所有自定义异常和错误恢复机制
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorRecoveryMixin:
    """错误恢复混入类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recovery_suggestions = []
        self.is_recoverable = False
        self.occurred_at = datetime.now()
    
    def add_recovery_suggestion(self, suggestion: str):
        """添加恢复建议"""
        self.recovery_suggestions.append(suggestion)
        self.is_recoverable = True
    
    def get_recovery_info(self) -> Dict[str, Any]:
        """获取恢复信息"""
        return {
            'is_recoverable': self.is_recoverable,
            'suggestions': self.recovery_suggestions,
            'occurred_at': self.occurred_at.isoformat(),
            'error_code': getattr(self, 'error_code', 'UNKNOWN')
        }


def exception_handler(fallback_return=None, log_level=logging.ERROR):
    """异常处理装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except DAPException as e:
                logger.log(log_level, f"DAP异常 in {func.__name__}: {e.message}", 
                          extra={'error_code': e.error_code, 'details': e.details})
                if hasattr(e, 'get_recovery_info'):
                    logger.info(f"恢复信息: {e.get_recovery_info()}")
                return fallback_return
            except Exception as e:
                logger.log(log_level, f"未知异常 in {func.__name__}: {str(e)}", 
                          exc_info=True)
                return fallback_return
        return wrapper
    return decorator

class DAPException(ErrorRecoveryMixin, Exception):
    """DAP系统基础异常"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "DAP_ERROR"
        self.details = details or {}

class DataIngestionError(DAPException):
    """数据接入异常"""
    def __init__(self, message: str, file_path: str = None, **kwargs):
        super().__init__(message, "DATA_INGESTION_ERROR", **kwargs)
        self.file_path = file_path

class ProcessingError(DAPException):
    """数据处理异常"""
    def __init__(self, message: str, stage: str = None, **kwargs):
        super().__init__(message, "PROCESSING_ERROR", **kwargs)
        self.stage = stage

class StorageError(DAPException):
    """数据存储异常"""
    def __init__(self, message: str, table_name: str = None, **kwargs):
        super().__init__(message, "STORAGE_ERROR", **kwargs)
        self.table_name = table_name

class ValidationError(DAPException):
    """数据验证异常"""
    def __init__(self, message: str, field_name: str = None, **kwargs):
        super().__init__(message, "VALIDATION_ERROR", **kwargs)
        self.field_name = field_name

class SecurityError(DAPException):
    """安全异常"""
    def __init__(self, message: str, security_type: str = None, **kwargs):
        super().__init__(message, "SECURITY_ERROR", **kwargs)
        self.security_type = security_type

class APIError(DAPException):
    """API异常"""
    def __init__(self, message: str, status_code: int = 500, **kwargs):
        super().__init__(message, "API_ERROR", **kwargs)
        self.status_code = status_code

class ConfigurationError(DAPException):
    """配置异常"""
    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(message, "CONFIGURATION_ERROR", **kwargs)
        self.config_key = config_key