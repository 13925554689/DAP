"""
DAP - pytest 配置文件
提供测试夹具和配置
"""

import pytest
import tempfile
import os
import sqlite3
import pandas as pd
from pathlib import Path
import shutil
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main_engine import DAPEngine
from utils.exceptions import DAPException
from utils.logging_config import setup_logging

@pytest.fixture(scope="session")
def test_logging():
    """设置测试日志"""
    setup_logging(log_dir="tests/logs", log_level="DEBUG", console_output=False)

@pytest.fixture
def temp_db():
    """临时数据库夹具"""
    temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_file.close()
    
    yield temp_file.name
    
    # 清理
    try:
        os.unlink(temp_file.name)
    except OSError:
        pass

@pytest.fixture
def temp_dir():
    """临时目录夹具"""
    temp_dir = tempfile.mkdtemp()
    
    yield temp_dir
    
    # 清理
    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass

@pytest.fixture
def sample_data():
    """示例数据夹具"""
    return pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'name': ['张三', '李四', '王五', '赵六', '钱七'],
        'amount': [100.50, 200.75, 300.25, 400.00, 500.99],
        'date': pd.date_range('2024-01-01', periods=5),
        'category': ['A', 'B', 'A', 'C', 'B']
    })

@pytest.fixture
def sample_csv_file(temp_dir, sample_data):
    """示例CSV文件夹具"""
    csv_path = os.path.join(temp_dir, 'test_data.csv')
    sample_data.to_csv(csv_path, index=False, encoding='utf-8')
    
    return csv_path

@pytest.fixture
def sample_excel_file(temp_dir, sample_data):
    """示例Excel文件夹具"""
    excel_path = os.path.join(temp_dir, 'test_data.xlsx')
    sample_data.to_excel(excel_path, index=False)
    
    return excel_path

@pytest.fixture
def sample_db_file(temp_db, sample_data):
    """示例数据库文件夹具"""
    conn = sqlite3.connect(temp_db)
    sample_data.to_sql('test_table', conn, index=False, if_exists='replace')
    conn.close()
    
    return temp_db

@pytest.fixture
def dap_engine(temp_db):
    """DAP引擎夹具"""
    engine = DAPEngine(db_path=temp_db, export_dir=tempfile.mkdtemp())
    
    yield engine
    
    # 清理
    try:
        engine.close()
    except:
        pass

@pytest.fixture
def mock_config():
    """模拟配置夹具"""
    return {
        'database': {
            'path': ':memory:',
            'pool_size': 2,
            'timeout': 10
        },
        'processing': {
            'batch_size': 100,
            'max_workers': 2,
            'timeout': 30
        },
        'logging': {
            'level': 'DEBUG',
            'format': 'json'
        }
    }

class TestHelper:
    """测试辅助类"""
    
    @staticmethod
    def create_test_files(directory: str, file_types: list = None):
        """创建测试文件"""
        if file_types is None:
            file_types = ['csv', 'xlsx']
        
        files = {}
        test_data = pd.DataFrame({
            'id': range(1, 11),
            'value': range(10, 101, 10),
            'text': [f'text_{i}' for i in range(1, 11)]
        })
        
        for file_type in file_types:
            if file_type == 'csv':
                file_path = os.path.join(directory, 'test.csv')
                test_data.to_csv(file_path, index=False)
                files['csv'] = file_path
            elif file_type == 'xlsx':
                file_path = os.path.join(directory, 'test.xlsx')
                test_data.to_excel(file_path, index=False)
                files['xlsx'] = file_path
            elif file_type == 'db':
                file_path = os.path.join(directory, 'test.db')
                conn = sqlite3.connect(file_path)
                test_data.to_sql('test_table', conn, index=False)
                conn.close()
                files['db'] = file_path
        
        return files
    
    @staticmethod
    def assert_dataframe_equal(df1: pd.DataFrame, df2: pd.DataFrame, check_dtype=False):
        """比较DataFrame是否相等"""
        pd.testing.assert_frame_equal(df1, df2, check_dtype=check_dtype)
    
    @staticmethod
    def assert_exception_type(exception, expected_type):
        """断言异常类型"""
        assert isinstance(exception, expected_type), f"期望 {expected_type}, 得到 {type(exception)}"

@pytest.fixture
def test_helper():
    """测试辅助类夹具"""
    return TestHelper

# 自定义pytest标记
def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "slow: 慢速测试")
    config.addinivalue_line("markers", "security: 安全测试")
    config.addinivalue_line("markers", "performance: 性能测试")

# 测试数据生成器
@pytest.fixture
def test_data_generator():
    """测试数据生成器"""
    class TestDataGenerator:
        @staticmethod
        def generate_financial_data(rows=100):
            """生成财务数据"""
            import random
            from datetime import datetime, timedelta
            
            data = []
            start_date = datetime(2024, 1, 1)
            
            for i in range(rows):
                data.append({
                    'transaction_id': f'T{i:06d}',
                    'account_code': random.choice(['1001', '1002', '2001', '2002', '3001']),
                    'amount': round(random.uniform(100, 10000), 2),
                    'date': start_date + timedelta(days=random.randint(0, 365)),
                    'description': f'Transaction {i}',
                    'type': random.choice(['借', '贷'])
                })
            
            return pd.DataFrame(data)
        
        @staticmethod
        def generate_audit_data(rows=50):
            """生成审计数据"""
            import random
            
            data = []
            for i in range(rows):
                data.append({
                    'audit_id': f'A{i:04d}',
                    'risk_level': random.choice(['低', '中', '高']),
                    'finding': f'审计发现 {i}',
                    'status': random.choice(['待处理', '处理中', '已完成']),
                    'auditor': random.choice(['张三', '李四', '王五'])
                })
            
            return pd.DataFrame(data)
    
    return TestDataGenerator

# 性能测试装饰器
@pytest.fixture
def performance_test():
    """性能测试装饰器"""
    import time
    
    class PerformanceTest:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def end(self):
            self.end_time = time.time()
            return self.end_time - self.start_time
        
        def assert_duration(self, max_duration):
            duration = self.end()
            assert duration <= max_duration, f"操作耗时 {duration:.3f}s 超过限制 {max_duration}s"
    
    return PerformanceTest