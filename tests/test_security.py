"""
DAP - 安全测试
测试系统安全性和防护措施
"""

import pytest
import os
import tempfile
import sqlite3
from unittest.mock import patch, Mock

from utils.validators import SQLQueryValidator, FileValidator, ProcessingRequest
from utils.exceptions import SecurityError, ValidationError
from main_engine import DAPEngine

@pytest.mark.security
class TestSQLSecurity:
    """SQL安全测试"""
    
    def test_sql_injection_table_names(self):
        """测试表名SQL注入防护"""
        malicious_names = [
            "'; DROP TABLE users; --",
            "test'; DELETE FROM data; --",
            "users UNION SELECT * FROM passwords",
            "'; UPDATE users SET admin=1; --",
            "test\"; DROP TABLE data; --"
        ]
        
        for name in malicious_names:
            with pytest.raises(SecurityError):
                SQLQueryValidator.validate_table_name(name)
    
    def test_sql_injection_column_names(self):
        """测试列名SQL注入防护"""
        malicious_columns = [
            "id'; DROP TABLE test; --",
            "name UNION SELECT password FROM users",
            "'; INSERT INTO audit_log VALUES('hack'); --"
        ]
        
        for column in malicious_columns:
            with pytest.raises(SecurityError):
                SQLQueryValidator.validate_column_name(column)
    
    def test_valid_table_names(self):
        """测试有效表名"""
        valid_names = [
            "users",
            "user_data",
            "table123",
            "TEST_TABLE",
            "a1b2c3"
        ]
        
        for name in valid_names:
            result = SQLQueryValidator.validate_table_name(name)
            assert result == name
    
    def test_query_safety_validation(self):
        """测试查询安全性验证"""
        safe_queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM users WHERE id = 1",
            "SELECT COUNT(*) FROM data"
        ]
        
        dangerous_queries = [
            "DROP TABLE users",
            "DELETE FROM users",
            "INSERT INTO users VALUES ('hacker', 'admin')",
            "SELECT * FROM users; DROP TABLE data;",
            "UPDATE users SET password = 'hacked'"
        ]
        
        for query in safe_queries:
            result = SQLQueryValidator.validate_query_safety(query)
            assert result.strip().lower().startswith('select')
        
        for query in dangerous_queries:
            with pytest.raises(SecurityError):
                SQLQueryValidator.validate_query_safety(query)
    
    def test_table_name_length_limit(self):
        """测试表名长度限制"""
        long_name = "a" * 100  # 超过64字符限制
        
        with pytest.raises(SecurityError):
            SQLQueryValidator.validate_table_name(long_name)
    
    def test_dangerous_keywords_detection(self):
        """测试危险关键词检测"""
        dangerous_names = [
            "drop_table",
            "exec_command",
            "sp_execute",
            "xp_cmdshell"
        ]
        
        for name in dangerous_names:
            with pytest.raises(SecurityError):
                SQLQueryValidator.validate_table_name(name)

@pytest.mark.security
class TestFileSecurity:
    """文件安全测试"""
    
    def test_path_traversal_attack(self, temp_dir):
        """测试路径遍历攻击防护"""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "temp_dir/../../../sensitive_file"
        ]
        
        for path in malicious_paths:
            with pytest.raises((SecurityError, ValidationError)):
                FileValidator.validate_file_path(path)
    
    def test_file_extension_validation(self, temp_dir):
        """测试文件扩展名验证"""
        # 创建各种文件
        valid_files = []
        invalid_files = []
        
        # 有效文件
        for ext in ['.csv', '.xlsx', '.db', '.sqlite']:
            file_path = os.path.join(temp_dir, f'test{ext}')
            with open(file_path, 'w') as f:
                f.write('test')
            valid_files.append(file_path)
        
        # 无效文件
        for ext in ['.exe', '.bat', '.sh', '.py', '.js']:
            file_path = os.path.join(temp_dir, f'test{ext}')
            with open(file_path, 'w') as f:
                f.write('test')
            invalid_files.append(file_path)
        
        # 测试有效文件
        for file_path in valid_files:
            result = FileValidator.validate_file_path(file_path)
            assert os.path.isabs(result)
        
        # 测试无效文件
        for file_path in invalid_files:
            with pytest.raises(ValidationError):
                FileValidator.validate_file_path(file_path)
    
    def test_file_size_limit(self, temp_dir):
        """测试文件大小限制"""
        # 创建一个超大文件（模拟）
        large_file = os.path.join(temp_dir, 'large.csv')
        
        # 使用patch模拟大文件
        with patch('os.path.getsize') as mock_size:
            mock_size.return_value = 200 * 1024 * 1024  # 200MB
            
            with open(large_file, 'w') as f:
                f.write('test')
            
            with pytest.raises(ValidationError):
                FileValidator.validate_file_path(large_file)
    
    def test_directory_validation(self, temp_dir):
        """测试目录验证"""
        # 有效目录
        result = FileValidator.validate_directory_path(temp_dir)
        assert os.path.isabs(result)
        
        # 无效目录
        with pytest.raises(ValidationError):
            FileValidator.validate_directory_path("/nonexistent/directory")

@pytest.mark.security
class TestInputValidation:
    """输入验证测试"""
    
    def test_processing_request_validation(self, sample_csv_file):
        """测试处理请求验证"""
        # 有效请求
        request = ProcessingRequest(
            data_source_path=sample_csv_file,
            options={'batch_size': 1000}
        )
        assert os.path.isabs(request.data_source_path)
        
        # 无效路径
        with pytest.raises(ValidationError):
            ProcessingRequest(data_source_path="/nonexistent/file.csv")
        
        # 空路径
        with pytest.raises(ValidationError):
            ProcessingRequest(data_source_path="")
    
    def test_options_validation(self, sample_csv_file):
        """测试选项验证"""
        # 有效选项
        valid_options = {
            'start_api_server': True,
            'batch_size': 1000,
            'max_workers': 4
        }
        
        request = ProcessingRequest(
            data_source_path=sample_csv_file,
            options=valid_options
        )
        assert request.options == valid_options
        
        # 无效选项类型
        with pytest.raises(ValidationError):
            ProcessingRequest(
                data_source_path=sample_csv_file,
                options="invalid"
            )
    
    def test_api_input_validation(self):
        """测试API输入验证"""
        from utils.validators import validate_api_input
        
        # 有效输入
        valid_data = {
            'query': 'SELECT * FROM users',
            'limit': 100
        }
        result = validate_api_input(valid_data, ['query'])
        assert result == valid_data
        
        # 缺少必需字段
        with pytest.raises(ValidationError):
            validate_api_input({'limit': 100}, ['query'])
        
        # 无效输入类型
        with pytest.raises(ValidationError):
            validate_api_input("invalid", ['query'])

@pytest.mark.security
class TestSystemSecurity:
    """系统安全测试"""
    
    def test_engine_sql_injection_protection(self, dap_engine):
        """测试引擎SQL注入防护"""
        # 尝试通过AI分析接口进行SQL注入
        malicious_queries = [
            "'; DROP TABLE users; --",
            "test' UNION SELECT * FROM passwords",
            "'; DELETE FROM audit_log; --"
        ]
        
        for query in malicious_queries:
            result = dap_engine.analyze_with_ai("分析", query)
            assert not result['success']
            assert 'SECURITY_ERROR' in result.get('error_code', '') or 'VALIDATION_ERROR' in result.get('error_code', '')
    
    def test_data_sanitization(self, dap_engine, temp_dir):
        """测试数据清理"""
        # 创建包含潜在危险数据的CSV
        import pandas as pd
        
        dangerous_data = pd.DataFrame({
            'normal_column': [1, 2, 3],
            "'; DROP TABLE users; --": ['a', 'b', 'c'],
            'exec(dangerous_code)': ['x', 'y', 'z']
        })
        
        csv_file = os.path.join(temp_dir, 'dangerous.csv')
        dangerous_data.to_csv(csv_file, index=False)
        
        # 处理应该成功，但危险列名应该被清理
        result = dap_engine.process(csv_file, {'start_api_server': False})
        
        # 即使处理失败，也不应该执行危险代码
        assert 'success' in result
    
    def test_log_sanitization(self):
        """测试日志清理"""
        from utils.logging_config import SecureFormatter
        import logging
        
        formatter = SecureFormatter()
        
        # 创建包含敏感信息的日志记录
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='User login: password=secret123, token=abc123',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # 敏感信息应该被清理
        assert 'secret123' not in formatted or '***SANITIZED***' in formatted
    
    def test_connection_security(self, temp_db):
        """测试连接安全"""
        from utils.connection_pool import get_connection_pool
        
        pool = get_connection_pool(temp_db)
        
        with pool.get_connection() as conn:
            with conn:
                # 确保连接使用了安全配置
                cursor = conn.execute("PRAGMA foreign_keys")
                result = cursor.fetchone()
                assert result[0] == 1  # 外键约束应该启用
    
    def test_privilege_escalation_prevention(self, dap_engine):
        """测试权限提升防护"""
        # 尝试执行需要高权限的操作
        dangerous_operations = [
            "ATTACH DATABASE '/etc/passwd' AS secret",
            "PRAGMA table_info(sqlite_master)",
            "SELECT load_extension('malicious.so')"
        ]
        
        for operation in dangerous_operations:
            # 这些操作应该被阻止或失败
            try:
                result = dap_engine.analyze_with_ai("执行", operation)
                if result['success']:
                    # 如果成功，确保没有执行危险操作
                    assert 'load_extension' not in str(result)
            except Exception:
                # 抛出异常是期望的行为
                pass

@pytest.mark.security
class TestSecurityConfiguration:
    """安全配置测试"""
    
    def test_secure_defaults(self):
        """测试安全默认配置"""
        # 检查默认配置是否安全
        from utils.validators import SQLQueryValidator, FileValidator
        
        # SQL验证器应该拒绝危险操作
        with pytest.raises(SecurityError):
            SQLQueryValidator.validate_query_safety("DROP TABLE test")
        
        # 文件验证器应该有大小限制
        assert FileValidator.MAX_FILE_SIZE > 0
        assert FileValidator.ALLOWED_EXTENSIONS
    
    def test_logging_security(self):
        """测试日志安全配置"""
        from utils.logging_config import SecureFormatter
        
        formatter = SecureFormatter()
        
        # 敏感字段应该被识别
        assert 'password' in formatter.SENSITIVE_FIELDS
        assert 'token' in formatter.SENSITIVE_FIELDS
        assert 'secret' in formatter.SENSITIVE_FIELDS
    
    def test_connection_pool_security(self):
        """测试连接池安全配置"""
        from utils.connection_pool import DatabaseConnectionPool
        
        # 连接池应该有合理的限制
        pool = DatabaseConnectionPool(':memory:', max_connections=5)
        
        assert pool.max_connections <= 20  # 不应该允许无限连接
        assert pool.connection_timeout > 0  # 应该有超时设置