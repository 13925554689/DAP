"""
DAP - 工具模块测试
测试各种工具函数和类
"""

import pytest
import time
import threading
import tempfile
import os
from unittest.mock import patch, Mock

from utils.exceptions import DAPException, ValidationError, SecurityError
from utils.validators import SQLQueryValidator, FileValidator
from utils.retry import retry, smart_retry, RetryManager
from utils.monitoring import performance_monitor, global_monitor, SystemMonitor
from utils.async_processing import AsyncTaskManager, BatchProcessor, ProgressTracker

class TestExceptions:
    """异常处理测试"""
    
    def test_dap_exception_creation(self):
        """测试DAP异常创建"""
        exc = DAPException("测试错误", "TEST_ERROR", {"key": "value"})
        
        assert exc.message == "测试错误"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {"key": "value"}
    
    def test_validation_error(self):
        """测试验证错误"""
        exc = ValidationError("字段无效", field_name="test_field")
        
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.field_name == "test_field"
    
    def test_security_error(self):
        """测试安全错误"""
        exc = SecurityError("安全违规", security_type="sql_injection")
        
        assert exc.error_code == "SECURITY_ERROR"
        assert exc.security_type == "sql_injection"

class TestValidators:
    """验证器测试"""
    
    def test_sql_query_validator(self):
        """测试SQL查询验证器"""
        # 有效查询
        valid_query = "SELECT * FROM users WHERE id = 1"
        result = SQLQueryValidator.validate_query_safety(valid_query)
        assert result == valid_query
        
        # 无效查询
        with pytest.raises(SecurityError):
            SQLQueryValidator.validate_query_safety("DROP TABLE users")
    
    def test_file_validator(self, temp_dir):
        """测试文件验证器"""
        # 创建测试文件
        test_file = os.path.join(temp_dir, "test.csv")
        with open(test_file, 'w') as f:
            f.write("test,data\n1,2\n")
        
        result = FileValidator.validate_file_path(test_file)
        assert os.path.isabs(result)
        
        # 测试不存在的文件
        with pytest.raises(ValidationError):
            FileValidator.validate_file_path("/nonexistent/file.csv")

class TestRetryMechanism:
    """重试机制测试"""
    
    def test_retry_decorator_success(self):
        """测试重试装饰器成功情况"""
        call_count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = test_function()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_decorator_failure_then_success(self):
        """测试重试装饰器失败后成功"""
        call_count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("临时失败")
            return "success"
        
        result = test_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_all_failures(self):
        """测试重试装饰器全部失败"""
        call_count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise Exception("持续失败")
        
        with pytest.raises(Exception):
            test_function()
        
        assert call_count == 3
    
    def test_retry_manager(self):
        """测试重试管理器"""
        manager = RetryManager(max_attempts=2, base_delay=0.1)
        
        call_count = 0
        
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("第一次失败")
            return "成功"
        
        result = manager.execute_with_retry(test_func)
        assert result == "成功"
        assert call_count == 2
        
        stats = manager.get_stats()
        assert stats['total_retries'] == 1
        assert stats['successful_retries'] == 1

@pytest.mark.performance
class TestPerformanceMonitoring:
    """性能监控测试"""
    
    def test_performance_monitor_context(self):
        """测试性能监控上下文管理器"""
        with performance_monitor("test_operation"):
            time.sleep(0.1)
        
        metrics = global_monitor.get_metrics("test_operation")
        assert len(metrics) > 0
        
        latest_metric = metrics[-1]
        assert latest_metric.operation_name == "test_operation"
        assert latest_metric.duration >= 0.1
        assert latest_metric.success
    
    def test_performance_monitor_exception(self):
        """测试性能监控异常处理"""
        try:
            with performance_monitor("test_error"):
                raise ValueError("测试错误")
        except ValueError:
            pass
        
        metrics = global_monitor.get_metrics("test_error")
        assert len(metrics) > 0
        
        latest_metric = metrics[-1]
        assert not latest_metric.success
        assert latest_metric.error_message == "测试错误"
    
    def test_performance_summary(self):
        """测试性能摘要"""
        # 执行多次操作
        for i in range(3):
            with performance_monitor("summary_test"):
                time.sleep(0.05)
        
        summary = global_monitor.get_summary("summary_test")
        assert summary['total_calls'] == 3
        assert summary['success_rate'] == 100.0
        assert summary['duration']['avg'] >= 0.05
    
    def test_system_monitor(self):
        """测试系统监控"""
        monitor = SystemMonitor(check_interval=0.1)
        monitor.start()
        
        time.sleep(0.2)
        
        current_stats = monitor.get_current_stats()
        assert 'cpu_percent' in current_stats
        assert 'memory_percent' in current_stats
        assert 'process_memory_mb' in current_stats
        
        health_report = monitor.get_health_report()
        assert 'health_score' in health_report
        assert 'status' in health_report
        
        monitor.stop()

class TestAsyncProcessing:
    """异步处理测试"""
    
    def test_async_task_manager(self):
        """测试异步任务管理器"""
        manager = AsyncTaskManager(max_workers=2)
        
        def test_task(x, y):
            time.sleep(0.1)
            return x + y
        
        # 创建任务
        task_id = manager.create_task(test_task, 1, 2, name="add_task")
        assert task_id in manager.tasks
        
        # 提交任务
        future = manager.submit_task(task_id)
        result = future.result(timeout=5)
        
        assert result == 3
        
        # 检查任务状态
        task_status = manager.get_task_status(task_id)
        assert task_status['status'] == 'completed'
        assert task_status['progress'] == 1.0
    
    def test_batch_processor(self):
        """测试批量处理器"""
        processor = BatchProcessor(batch_size=2, max_workers=2)
        
        items = list(range(5))
        results = []
        
        def process_item(item):
            return item * 2
        
        def callback(batch_results):
            results.extend(batch_results)
        
        futures = processor.process_batch(items, process_item, callback)
        all_results = processor.wait_for_completion(futures, timeout=10)
        
        assert len(all_results) == 5
        assert all_results == [0, 2, 4, 6, 8]
    
    def test_progress_tracker(self):
        """测试进度跟踪器"""
        tracker = ProgressTracker()
        
        operation_id = "test_operation"
        tracker.create_progress(operation_id, 5, "测试操作")
        
        # 更新进度
        for i in range(1, 6):
            tracker.update_progress(operation_id, i, f"步骤 {i}")
            time.sleep(0.01)
        
        progress = tracker.get_progress(operation_id)
        assert progress['progress_percent'] == 100
        assert progress['current_step'] == 5
        
        # 完成进度
        tracker.complete_progress(operation_id, "操作完成")
        
        final_progress = tracker.get_progress(operation_id)
        assert final_progress['status'] == 'completed'
        assert final_progress['message'] == "操作完成"

class TestConnectionPool:
    """连接池测试"""
    
    def test_connection_pool_basic(self):
        """测试连接池基本功能"""
        from utils.connection_pool import get_connection_pool
        
        pool = get_connection_pool(':memory:', pool_size=2, max_connections=5)
        
        # 获取连接
        with pool.get_connection() as conn:
            with conn:
                conn.execute("CREATE TABLE test (id INTEGER)")
                conn.execute("INSERT INTO test VALUES (1)")
                
                cursor = conn.execute("SELECT * FROM test")
                result = cursor.fetchone()
                assert result[0] == 1
        
        # 检查统计信息
        stats = pool.get_stats()
        assert stats['total_connections'] >= 2
        assert stats['total_requests'] >= 1
    
    def test_connection_pool_concurrency(self):
        """测试连接池并发"""
        from utils.connection_pool import get_connection_pool
        import concurrent.futures
        
        pool = get_connection_pool(':memory:', pool_size=2, max_connections=4)
        
        def worker(worker_id):
            with pool.get_connection() as conn:
                with conn:
                    conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER, worker_id INTEGER)")
                    conn.execute("INSERT INTO test VALUES (?, ?)", (worker_id, worker_id))
                    time.sleep(0.1)
                    return worker_id
        
        # 并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker, i) for i in range(3)]
            results = [f.result() for f in futures]
        
        assert len(results) == 3
        assert set(results) == {0, 1, 2}

class TestLoggingConfiguration:
    """日志配置测试"""
    
    def test_secure_formatter(self):
        """测试安全格式化器"""
        from utils.logging_config import SecureFormatter
        import logging
        
        formatter = SecureFormatter()
        
        # 创建包含敏感信息的记录
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Password: secret123, Token: abc456',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # 敏感信息应该被处理
        assert 'secret123' not in formatted or '***SANITIZED***' in formatted
    
    def test_json_formatter(self):
        """测试JSON格式化器"""
        from utils.logging_config import JSONFormatter
        import logging
        import json
        
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # 应该是有效的JSON
        log_data = json.loads(formatted)
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Test message'
        assert log_data['module'] == 'test'
    
    def test_logging_config_setup(self, temp_dir):
        """测试日志配置设置"""
        from utils.logging_config import LoggingConfig
        
        config = LoggingConfig(
            log_dir=temp_dir,
            log_level="DEBUG",
            console_output=False,
            json_format=True
        )
        
        logger = config.get_logger("test")
        logger.info("测试消息")
        
        # 检查日志文件是否创建
        log_files = os.listdir(temp_dir)
        assert any(f.endswith('.log') for f in log_files)

@pytest.mark.integration
class TestIntegrationUtils:
    """工具集成测试"""
    
    def test_monitoring_with_retry(self):
        """测试监控与重试集成"""
        call_count = 0
        
        @retry(max_attempts=2, delay=0.1)
        def monitored_function():
            nonlocal call_count
            call_count += 1
            
            with performance_monitor("retry_test"):
                if call_count == 1:
                    raise Exception("第一次失败")
                return "成功"
        
        result = monitored_function()
        assert result == "成功"
        assert call_count == 2
        
        # 检查监控记录
        metrics = global_monitor.get_metrics("retry_test")
        assert len(metrics) == 2  # 一次失败，一次成功
    
    def test_async_with_monitoring(self):
        """测试异步处理与监控集成"""
        manager = AsyncTaskManager(max_workers=1)
        
        def monitored_task():
            with performance_monitor("async_task"):
                time.sleep(0.1)
                return "完成"
        
        task_id = manager.create_task(monitored_task, name="monitored_async")
        future = manager.submit_task(task_id)
        result = future.result(timeout=5)
        
        assert result == "完成"
        
        # 检查监控记录
        metrics = global_monitor.get_metrics("async_task")
        assert len(metrics) > 0