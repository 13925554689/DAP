#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 安全工具模块
提供路径验证、SQL注入防护、文件安全检查等安全功能
"""

import os
import re
import hashlib
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """安全配置"""
    max_file_size: int = 1024 * 1024 * 1024  # 1GB
    allowed_extensions: List[str] = None
    blocked_patterns: List[str] = None
    enable_path_validation: bool = True
    enable_sql_protection: bool = True
    
    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = [
                '.xlsx', '.xls', '.csv', '.db', '.sqlite', 
                '.mdb', '.accdb', '.ais', '.zip', '.rar',
                '.bak', '.sql'
            ]
        
        if self.blocked_patterns is None:
            self.blocked_patterns = [
                r'\.\./',  # 路径遍历
                r'\.\.\\',  # Windows路径遍历
                r'<script',  # XSS
                r'javascript:',  # JavaScript注入
                r'union\s+select',  # SQL注入
                r'drop\s+table',  # SQL删除
                r'delete\s+from',  # SQL删除
            ]


class PathValidator:
    """路径安全验证器"""
    
    def __init__(self, allowed_base_paths: Optional[List[str]] = None):
        self.allowed_base_paths = allowed_base_paths or []
        
        # 默认允许的基础路径
        if not self.allowed_base_paths:
            current_dir = os.path.abspath(os.getcwd())
            self.allowed_base_paths = [
                current_dir,
                os.path.join(current_dir, 'data'),
                os.path.join(current_dir, 'temp'),
                os.path.join(current_dir, 'exports'),
                os.path.join(current_dir, 'cache')
            ]
    
    def validate_path(self, file_path: str) -> bool:
        """验证路径安全性"""
        try:
            # 获取绝对路径
            abs_path = os.path.abspath(file_path)
            
            # 检查路径遍历攻击
            if '..' in file_path or '..' in abs_path:
                logger.warning(f"检测到路径遍历攻击: {file_path}")
                return False
            
            # 检查是否在允许的基础路径内
            for base_path in self.allowed_base_paths:
                if abs_path.startswith(os.path.abspath(base_path)):
                    return True
            
            logger.warning(f"路径不在允许的范围内: {abs_path}")
            return False
            
        except Exception as e:
            logger.error(f"路径验证失败: {e}")
            return False
    
    def sanitize_path(self, file_path: str) -> str:
        """清理路径"""
        # 移除危险字符
        sanitized = re.sub(r'[<>:"|?*]', '_', file_path)
        
        # 移除路径遍历尝试
        sanitized = sanitized.replace('..', '_')
        
        # 限制路径长度
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
        
        return sanitized
    
    def is_safe_filename(self, filename: str) -> bool:
        """检查文件名是否安全"""
        # 危险文件名模式
        dangerous_patterns = [
            r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',  # Windows保留名
            r'^\.',  # 隐藏文件
            r'[<>:"|?*]',  # 非法字符
            r'\s+$',  # 以空格结尾
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return False
        
        return True


class SQLSafetyGuard:
    """SQL安全防护"""
    
    def __init__(self):
        # SQL注入检测模式
        self.injection_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\s)",
            r"(\b(or|and)\s+\d+\s*=\s*\d+)",
            r"(['\"](\s*(or|and)\s+)*\d+(\s*(or|and)\s+)*['\"])",
            r"(['\"][^'\"]*['\"];\s*(drop|delete|insert|update))",
            r"(\|\||&&)",
            r"(char\(|ascii\(|substring\()",
            r"(\s+(or|and)\s+['\"].*['\"])",
        ]
        
        # 编译正则表达式
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.injection_patterns
        ]
    
    def is_safe_query(self, query: str) -> bool:
        """检查SQL查询是否安全"""
        if not query:
            return True
        
        # 检查SQL注入模式
        for pattern in self.compiled_patterns:
            if pattern.search(query):
                logger.warning(f"检测到潜在SQL注入: {query[:100]}...")
                return False
        
        return True
    
    def sanitize_identifier(self, identifier: str) -> str:
        """清理SQL标识符"""
        # 只保留字母、数字和下划线
        sanitized = re.sub(r'[^\w]', '_', identifier)
        
        # 确保以字母开头
        if sanitized and not sanitized[0].isalpha():
            sanitized = 'col_' + sanitized
        
        return sanitized
    
    def build_safe_query(self, template: str, **params) -> str:
        """构建安全的参数化查询"""
        # 验证模板
        if not self.is_safe_query(template):
            raise ValueError("不安全的查询模板")
        
        # 清理参数
        safe_params = {}
        for key, value in params.items():
            if isinstance(value, str):
                # 转义单引号
                safe_value = value.replace("'", "''")
                safe_params[key] = safe_value
            else:
                safe_params[key] = value
        
        return template.format(**safe_params)
    
    def execute_safe_query(self, connection: sqlite3.Connection, 
                          query: str, params: Optional[tuple] = None):
        """执行安全查询"""
        if not self.is_safe_query(query):
            raise ValueError("不安全的SQL查询")
        
        try:
            if params:
                return connection.execute(query, params)
            else:
                return connection.execute(query)
        except Exception as e:
            logger.error(f"SQL查询执行失败: {e}")
            raise


class FileSecurityScanner:
    """文件安全扫描器"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def scan_file(self, file_path: str) -> Dict[str, Any]:
        """扫描文件安全性"""
        result = {
            'is_safe': True,
            'issues': [],
            'file_info': {},
            'scan_time': None
        }
        
        start_time = time.time()
        
        try:
            if not os.path.exists(file_path):
                result['is_safe'] = False
                result['issues'].append('文件不存在')
                return result
            
            # 获取文件信息
            stat_info = os.stat(file_path)
            result['file_info'] = {
                'size': stat_info.st_size,
                'modified': stat_info.st_mtime,
                'extension': Path(file_path).suffix.lower()
            }
            
            # 检查文件大小
            if stat_info.st_size > self.config.max_file_size:
                result['is_safe'] = False
                result['issues'].append(f'文件过大: {stat_info.st_size} bytes')
            
            # 检查文件扩展名
            ext = Path(file_path).suffix.lower()
            if ext not in self.config.allowed_extensions:
                result['is_safe'] = False
                result['issues'].append(f'不允许的文件类型: {ext}')
            
            # 检查文件内容（文本文件）
            if ext in ['.txt', '.csv', '.sql', '.py', '.js', '.html']:
                self._scan_text_content(file_path, result)
            
            # 检查文件头部（二进制文件）
            else:
                self._scan_binary_header(file_path, result)
                
        except Exception as e:
            result['is_safe'] = False
            result['issues'].append(f'扫描失败: {e}')
        
        finally:
            result['scan_time'] = time.time() - start_time
        
        return result
    
    def _scan_text_content(self, file_path: str, result: Dict[str, Any]):
        """扫描文本文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # 只读取前1MB内容
                content = f.read(1024 * 1024)
            
            # 检查恶意模式
            for pattern in self.config.blocked_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    result['is_safe'] = False
                    result['issues'].append(f'检测到可疑内容: {pattern}')
                    
        except Exception as e:
            result['issues'].append(f'文本内容扫描失败: {e}')
    
    def _scan_binary_header(self, file_path: str, result: Dict[str, Any]):
        """扫描二进制文件头部"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(1024)  # 读取前1KB
            
            # 检查已知的恶意文件签名
            malicious_signatures = [
                b'MZ',  # PE执行文件
                b'\x7fELF',  # ELF执行文件
                b'<?php',  # PHP代码
                b'<script',  # 脚本代码
            ]
            
            for signature in malicious_signatures:
                if header.startswith(signature):
                    result['is_safe'] = False
                    result['issues'].append(f'检测到可疑文件签名')
                    break
                    
        except Exception as e:
            result['issues'].append(f'二进制头部扫描失败: {e}')
    
    def calculate_file_hash(self, file_path: str, algorithm: str = 'sha256') -> str:
        """计算文件哈希值"""
        hash_algo = hashlib.new(algorithm)
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_algo.update(chunk)
            
            return hash_algo.hexdigest()
            
        except Exception as e:
            logger.error(f"计算文件哈希失败: {e}")
            return ""


class SecurityManager:
    """安全管理器"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.path_validator = PathValidator()
        self.sql_guard = SQLSafetyGuard()
        self.file_scanner = FileSecurityScanner(self.config)
        
        # 安全事件日志
        self.security_events: List[Dict[str, Any]] = []
    
    def validate_file_access(self, file_path: str) -> bool:
        """验证文件访问安全性"""
        # 路径验证
        if self.config.enable_path_validation:
            if not self.path_validator.validate_path(file_path):
                self._log_security_event('path_validation_failed', file_path)
                return False
        
        # 文件名验证
        filename = os.path.basename(file_path)
        if not self.path_validator.is_safe_filename(filename):
            self._log_security_event('unsafe_filename', file_path)
            return False
        
        return True
    
    def validate_sql_query(self, query: str) -> bool:
        """验证SQL查询安全性"""
        if self.config.enable_sql_protection:
            if not self.sql_guard.is_safe_query(query):
                self._log_security_event('sql_injection_attempt', query[:100])
                return False
        
        return True
    
    def scan_file_security(self, file_path: str) -> Dict[str, Any]:
        """扫描文件安全性"""
        scan_result = self.file_scanner.scan_file(file_path)
        
        if not scan_result['is_safe']:
            self._log_security_event('file_security_violation', 
                                   file_path, scan_result['issues'])
        
        return scan_result
    
    def _log_security_event(self, event_type: str, details: str, 
                           additional_info: Optional[Any] = None):
        """记录安全事件"""
        event = {
            'timestamp': time.time(),
            'type': event_type,
            'details': details,
            'additional_info': additional_info
        }
        
        self.security_events.append(event)
        logger.warning(f"安全事件: {event_type} - {details}")
    
    def get_security_report(self) -> Dict[str, Any]:
        """获取安全报告"""
        return {
            'total_events': len(self.security_events),
            'recent_events': self.security_events[-10:],  # 最近10个事件
            'event_types': self._count_event_types(),
            'config': self.config.__dict__
        }
    
    def _count_event_types(self) -> Dict[str, int]:
        """统计事件类型"""
        counts = {}
        for event in self.security_events:
            event_type = event['type']
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts


# 全局安全管理器实例
security_manager = SecurityManager()


def secure_file_access(func):
    """文件访问安全装饰器"""
    def wrapper(*args, **kwargs):
        # 尝试从参数中找到文件路径
        file_path = None
        
        if args and isinstance(args[0], str):
            file_path = args[0]
        elif 'file_path' in kwargs:
            file_path = kwargs['file_path']
        elif 'path' in kwargs:
            file_path = kwargs['path']
        
        if file_path:
            if not security_manager.validate_file_access(file_path):
                raise PermissionError(f"文件访问被拒绝: {file_path}")
        
        return func(*args, **kwargs)
    
    return wrapper


def secure_sql_query(func):
    """SQL查询安全装饰器"""
    def wrapper(*args, **kwargs):
        # 尝试从参数中找到SQL查询
        query = None
        
        if args and isinstance(args[0], str):
            query = args[0]
        elif 'query' in kwargs:
            query = kwargs['query']
        elif 'sql' in kwargs:
            query = kwargs['sql']
        
        if query:
            if not security_manager.validate_sql_query(query):
                raise ValueError(f"SQL查询被拒绝: 检测到潜在注入风险")
        
        return func(*args, **kwargs)
    
    return wrapper


if __name__ == "__main__":
    import time
    import tempfile
    
    print("=== 安全工具测试 ===")
    
    # 创建安全管理器
    security = SecurityManager()
    
    # 测试路径验证
    print("\n1. 路径验证测试")
    
    test_paths = [
        "data/test.csv",  # 正常路径
        "../../../etc/passwd",  # 路径遍历
        "C:\\Windows\\System32\\cmd.exe",  # 系统文件
        "temp/safe_file.xlsx"  # 安全路径
    ]
    
    for path in test_paths:
        is_valid = security.validate_file_access(path)
        print(f"  {path}: {'✓' if is_valid else '✗'}")
    
    # 测试SQL注入检测
    print("\n2. SQL注入检测测试")
    
    test_queries = [
        "SELECT * FROM users WHERE id = 1",  # 正常查询
        "SELECT * FROM users WHERE id = 1 OR 1=1",  # SQL注入
        "DROP TABLE users",  # 危险操作
        "SELECT name FROM customers LIMIT 10"  # 正常查询
    ]
    
    for query in test_queries:
        is_safe = security.validate_sql_query(query)
        print(f"  {query}: {'✓' if is_safe else '✗'}")
    
    # 测试文件扫描
    print("\n3. 文件安全扫描测试")
    
    # 创建临时测试文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("id,name,value\n1,test,100\n2,sample,200")
        temp_file = f.name
    
    try:
        scan_result = security.scan_file_security(temp_file)
        print(f"  文件: {temp_file}")
        print(f"  安全: {'✓' if scan_result['is_safe'] else '✗'}")
        print(f"  问题: {scan_result['issues']}")
        print(f"  大小: {scan_result['file_info']['size']} bytes")
        
    finally:
        os.unlink(temp_file)
    
    # 显示安全报告
    print("\n4. 安全报告")
    report = security.get_security_report()
    print(f"  总事件数: {report['total_events']}")
    print(f"  事件类型: {report['event_types']}")
    
    print("\n安全工具测试完成")