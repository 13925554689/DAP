"""
DAP - 增强日志配置模块
提供结构化、安全、高性能的日志功能
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path
import traceback
import threading
from contextlib import contextmanager

class SecureFormatter(logging.Formatter):
    """安全的日志格式化器"""
    
    # 需要脱敏的字段
    SENSITIVE_FIELDS = {
        'password', 'passwd', 'pwd', 'secret', 'token', 'key', 
        'api_key', 'auth', 'authorization', 'credential', 'private'
    }
    
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
    
    def format(self, record):
        # 脱敏处理
        if hasattr(record, 'args') and record.args:
            record.args = self._sanitize_args(record.args)
        
        if hasattr(record, 'msg'):
            record.msg = self._sanitize_message(record.msg)
        
        return super().format(record)
    
    def _sanitize_args(self, args):
        """脱敏参数"""
        if isinstance(args, (list, tuple)):
            return tuple(self._sanitize_value(arg) for arg in args)
        return args
    
    def _sanitize_message(self, msg):
        """脱敏消息"""
        if isinstance(msg, str):
            return self._sanitize_value(msg)
        return msg
    
    def _sanitize_value(self, value):
        """脱敏值"""
        if isinstance(value, str):
            # 简单的字符串脱敏
            for field in self.SENSITIVE_FIELDS:
                if field.lower() in value.lower():
                    return value.replace(value, "***SANITIZED***")
        elif isinstance(value, dict):
            # 字典脱敏
            return {
                k: "***SANITIZED***" if any(sensitive in k.lower() for sensitive in self.SENSITIVE_FIELDS) else v
                for k, v in value.items()
            }
        return value

class JSONFormatter(SecureFormatter):
    """JSON格式的日志格式化器"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
            'process': record.process,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # 添加额外字段
        if hasattr(record, 'extra_data'):
            log_entry['extra'] = record.extra_data
        
        # 脱敏处理
        log_entry = self._sanitize_value(log_entry)
        
        return json.dumps(log_entry, ensure_ascii=False)

class PerformanceFilter(logging.Filter):
    """性能相关的日志过滤器"""
    
    def filter(self, record):
        # 为性能相关的日志添加标记
        if any(keyword in record.getMessage().lower() for keyword in 
               ['耗时', 'duration', 'performance', '性能', 'slow', '慢']):
            record.category = 'performance'
        
        # 为错误日志添加标记
        if record.levelno >= logging.ERROR:
            record.category = 'error'
        
        return True

class DAPLoggerAdapter(logging.LoggerAdapter):
    """DAP日志适配器"""
    
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        # 添加通用的额外信息
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        extra['component'] = 'DAP'
        
        kwargs['extra'] = extra
        return msg, kwargs
    
    def performance(self, msg, **kwargs):
        """记录性能日志"""
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['category'] = 'performance'
        self.info(msg, **kwargs)
    
    def security(self, msg, **kwargs):
        """记录安全日志"""
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['category'] = 'security'
        self.warning(msg, **kwargs)

class LoggingConfig:
    """日志配置管理器"""
    
    def __init__(self, 
                 log_dir: str = "logs",
                 log_level: str = "INFO",
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5,
                 console_output: bool = True,
                 json_format: bool = False):
        
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.console_output = console_output
        self.json_format = json_format
        
        # 确保日志目录存在
        self.log_dir.mkdir(exist_ok=True)
        
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 移除现有的处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 设置根日志级别
        root_logger.setLevel(self.log_level)
        
        # 创建格式化器
        if self.json_format:
            formatter = JSONFormatter()
        else:
            formatter = SecureFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # 创建文件处理器
        self._create_file_handlers(formatter)
        
        # 创建控制台处理器
        if self.console_output:
            self._create_console_handler(formatter)
        
        # 设置第三方库的日志级别
        self._configure_third_party_loggers()
    
    def _create_file_handlers(self, formatter):
        """创建文件处理器"""
        handlers = [
            # 主日志文件
            {
                'filename': self.log_dir / 'dap.log',
                'level': logging.INFO,
                'filter_func': lambda record: True
            },
            # 错误日志文件
            {
                'filename': self.log_dir / 'error.log',
                'level': logging.ERROR,
                'filter_func': lambda record: record.levelno >= logging.ERROR
            },
            # 性能日志文件
            {
                'filename': self.log_dir / 'performance.log',
                'level': logging.INFO,
                'filter_func': lambda record: getattr(record, 'category', '') == 'performance'
            },
            # 安全日志文件
            {
                'filename': self.log_dir / 'security.log',
                'level': logging.WARNING,
                'filter_func': lambda record: getattr(record, 'category', '') == 'security'
            }
        ]
        
        for handler_config in handlers:
            handler = logging.handlers.RotatingFileHandler(
                filename=handler_config['filename'],
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            handler.setLevel(handler_config['level'])
            handler.setFormatter(formatter)
            
            # 添加过滤器
            if handler_config['filter_func']:
                handler.addFilter(lambda record, func=handler_config['filter_func']: func(record))
            
            # 添加性能过滤器
            handler.addFilter(PerformanceFilter())
            
            logging.getLogger().addHandler(handler)
    
    def _create_console_handler(self, formatter):
        """创建控制台处理器"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        
        # 控制台使用简化的格式
        if not self.json_format:
            console_formatter = SecureFormatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
        else:
            console_handler.setFormatter(formatter)
        
        logging.getLogger().addHandler(console_handler)
    
    def _configure_third_party_loggers(self):
        """配置第三方库的日志级别"""
        third_party_loggers = {
            'urllib3': logging.WARNING,
            'requests': logging.WARNING,
            'fastapi': logging.INFO,
            'uvicorn': logging.INFO,
            'pandas': logging.WARNING,
            'openpyxl': logging.WARNING,
        }
        
        for logger_name, level in third_party_loggers.items():
            logging.getLogger(logger_name).setLevel(level)
    
    def get_logger(self, name: str = None) -> DAPLoggerAdapter:
        """获取日志记录器"""
        logger = logging.getLogger(name or __name__)
        return DAPLoggerAdapter(logger, {'source': 'DAP'})
    
    def set_level(self, level: Union[str, int]):
        """设置日志级别"""
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(level)

# 全局日志配置实例
_logging_config = None

def setup_logging(log_dir: str = "logs", 
                 log_level: str = "INFO", 
                 json_format: bool = False,
                 console_output: bool = True) -> LoggingConfig:
    """设置全局日志配置"""
    global _logging_config
    _logging_config = LoggingConfig(
        log_dir=log_dir,
        log_level=log_level,
        json_format=json_format,
        console_output=console_output
    )
    return _logging_config

def get_logger(name: str = None) -> DAPLoggerAdapter:
    """获取日志记录器"""
    if _logging_config is None:
        setup_logging()
    return _logging_config.get_logger(name)

@contextmanager
def log_context(**context_data):
    """日志上下文管理器"""
    logger = get_logger()
    
    # 记录开始
    start_time = datetime.now()
    logger.info("操作开始", extra={'context': context_data, 'start_time': start_time.isoformat()})
    
    try:
        yield logger
    except Exception as e:
        # 记录异常
        logger.error(f"操作失败: {e}", exc_info=True, extra={'context': context_data})
        raise
    finally:
        # 记录结束
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("操作结束", extra={
            'context': context_data,
            'end_time': end_time.isoformat(),
            'duration': duration
        })

class LogAnalyzer:
    """日志分析器"""
    
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
    
    def analyze_errors(self, hours: int = 24) -> Dict[str, Any]:
        """分析错误日志"""
        if not self.log_file.exists():
            return {"error": "日志文件不存在"}
        
        try:
            error_count = 0
            error_types = {}
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'ERROR' in line:
                        error_count += 1
                        # 简单的错误类型统计
                        if 'ValidationError' in line:
                            error_types['validation'] = error_types.get('validation', 0) + 1
                        elif 'StorageError' in line:
                            error_types['storage'] = error_types.get('storage', 0) + 1
                        elif 'DataIngestionError' in line:
                            error_types['data_ingestion'] = error_types.get('data_ingestion', 0) + 1
                        else:
                            error_types['other'] = error_types.get('other', 0) + 1
            
            return {
                'total_errors': error_count,
                'error_types': error_types,
                'analysis_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"分析失败: {e}"}
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        if not self.log_file.exists():
            return {"error": "日志文件不存在"}
        
        try:
            performance_entries = []
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '性能监控' in line and '耗时=' in line:
                        # 解析性能数据
                        try:
                            if '耗时=' in line:
                                duration_str = line.split('耗时=')[1].split('s')[0]
                                duration = float(duration_str)
                                performance_entries.append(duration)
                        except:
                            continue
            
            if performance_entries:
                return {
                    'total_operations': len(performance_entries),
                    'avg_duration': sum(performance_entries) / len(performance_entries),
                    'max_duration': max(performance_entries),
                    'min_duration': min(performance_entries),
                    'slow_operations': len([d for d in performance_entries if d > 1.0])
                }
            else:
                return {"message": "没有找到性能数据"}
                
        except Exception as e:
            return {"error": f"分析失败: {e}"}