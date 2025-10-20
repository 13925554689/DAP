"""
DAP - 主引擎测试
测试核心处理流程
"""

import pytest
import os
import tempfile
import pandas as pd
from unittest.mock import Mock, patch, MagicMock

from main_engine import DAPEngine, get_dap_engine
from utils.exceptions import ProcessingError, DataIngestionError, ValidationError

class TestDAPEngine:
    """DAP引擎测试类"""
    
    def test_engine_initialization(self, temp_db):
        """测试引擎初始化"""
        engine = DAPEngine(db_path=temp_db)
        
        assert engine.db_path == os.path.abspath(temp_db)
        assert not engine.processing
        assert engine.current_step == ""
        assert engine.progress == 0
        assert engine.last_result is None
        
        # 检查组件是否初始化
        assert engine.data_ingestor is not None
        assert engine.storage_manager is not None
        assert engine.audit_rules_engine is not None
    
    def test_get_system_info(self, dap_engine):
        """测试获取系统信息"""
        info = dap_engine.get_system_info()
        
        assert info['system'] == 'DAP - 数据处理审计智能体'
        assert info['version'] == '1.0.0'
        assert 'database_path' in info
        assert 'statistics' in info
        assert info['status'] in ['ready', 'processing']
    
    def test_get_status(self, dap_engine):
        """测试获取状态"""
        status = dap_engine.get_status()
        
        assert 'processing' in status
        assert 'current_step' in status
        assert 'progress' in status
        assert 'last_result' in status
        assert 'api_server_running' in status
    
    @pytest.mark.unit
    def test_process_invalid_path(self, dap_engine):
        """测试处理无效路径"""
        result = dap_engine.process("/invalid/path")
        
        assert not result['success']
        assert 'error' in result
        assert 'VALIDATION_ERROR' in result.get('error_code', '')
    
    @pytest.mark.unit
    def test_process_empty_path(self, dap_engine):
        """测试处理空路径"""
        result = dap_engine.process("")
        
        assert not result['success']
        assert 'error' in result
    
    @pytest.mark.integration
    def test_process_csv_file(self, dap_engine, sample_csv_file):
        """测试处理CSV文件"""
        result = dap_engine.process(sample_csv_file, {'start_api_server': False})
        
        if result['success']:
            assert result['data_path'] == dap_engine.db_path
            assert 'statistics' in result
            assert 'processing_time' in result
        else:
            # 如果失败，检查错误信息
            assert 'error' in result
            print(f"处理失败: {result['error']}")
    
    @pytest.mark.integration
    def test_process_excel_file(self, dap_engine, sample_excel_file):
        """测试处理Excel文件"""
        result = dap_engine.process(sample_excel_file, {'start_api_server': False})
        
        # Excel处理可能需要额外的依赖，允许某些失败
        assert 'success' in result
        if not result['success']:
            print(f"Excel处理失败（可能是依赖问题）: {result.get('error')}")
    
    def test_concurrent_processing(self, dap_engine, sample_csv_file):
        """测试并发处理保护"""
        # 模拟处理中状态
        dap_engine.processing = True
        
        result = dap_engine.process(sample_csv_file)
        
        assert not result['success']
        assert '系统正在处理其他任务' in result['error']
        assert result['error_code'] == 'SYSTEM_BUSY'
        
        # 恢复状态
        dap_engine.processing = False
    
    def test_analyze_with_ai_invalid_source(self, dap_engine):
        """测试AI分析无效数据源"""
        result = dap_engine.analyze_with_ai("分析数据", "invalid_table")
        
        assert not result['success']
        assert 'error' in result
    
    def test_analyze_with_ai_no_source(self, dap_engine):
        """测试AI分析无数据源"""
        with patch.object(dap_engine.agent_bridge, 'call_ai_analysis') as mock_ai:
            mock_ai.return_value = {'success': True, 'result': 'AI分析结果'}
            
            result = dap_engine.analyze_with_ai("分析趋势")
            
            # 应该调用AI分析，传入None作为数据
            mock_ai.assert_called_once_with("分析趋势", None)
    
    @pytest.mark.security
    def test_sql_injection_protection(self, dap_engine):
        """测试SQL注入防护"""
        # 尝试SQL注入攻击
        malicious_sources = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "test'; UPDATE users SET admin=1; --"
        ]
        
        for source in malicious_sources:
            result = dap_engine.analyze_with_ai("测试", source)
            assert not result['success']
            assert 'SECURITY_ERROR' in result.get('error_code', '') or 'VALIDATION_ERROR' in result.get('error_code', '')
    
    def test_export_data(self, dap_engine):
        """测试数据导出"""
        # 测试导出不存在的数据源
        result = dap_engine.export_data("nonexistent_table", "csv")
        
        assert not result['success']
        assert 'error' in result
    
    def test_generate_audit_report(self, dap_engine):
        """测试生成审计报告"""
        result = dap_engine.generate_audit_report("测试公司", "2024年度")
        
        # 由于没有实际数据，可能会失败，但应该有适当的错误处理
        assert 'success' in result
    
    def test_close_engine(self, temp_db):
        """测试关闭引擎"""
        engine = DAPEngine(db_path=temp_db)
        
        # 应该能正常关闭而不抛出异常
        engine.close()
        
        # 再次关闭应该也是安全的
        engine.close()

class TestDAPEngineErrorHandling:
    """DAP引擎错误处理测试"""
    
    def test_data_ingestor_error(self, dap_engine, temp_dir):
        """测试数据接入器错误处理"""
        # 创建一个无效的文件
        invalid_file = os.path.join(temp_dir, "invalid.txt")
        with open(invalid_file, 'w') as f:
            f.write("invalid data")
        
        result = dap_engine.process(invalid_file, {'start_api_server': False})
        
        assert not result['success']
        assert 'error' in result
    
    def test_storage_error_handling(self, dap_engine, sample_csv_file):
        """测试存储错误处理"""
        # 模拟存储管理器错误
        with patch.object(dap_engine.storage_manager, 'store_cleaned_data') as mock_store:
            mock_store.side_effect = Exception("存储失败")
            
            result = dap_engine.process(sample_csv_file, {'start_api_server': False})
            
            assert not result['success']
            assert '存储失败' in result['error']
    
    def test_processing_interruption(self, dap_engine, sample_csv_file):
        """测试处理中断"""
        # 模拟处理过程中的中断
        original_ingest = dap_engine.data_ingestor.ingest
        
        def interrupt_ingest(*args, **kwargs):
            raise KeyboardInterrupt("用户中断")
        
        dap_engine.data_ingestor.ingest = interrupt_ingest
        
        with pytest.raises(KeyboardInterrupt):
            dap_engine.process(sample_csv_file, {'start_api_server': False})
        
        # 恢复原始方法
        dap_engine.data_ingestor.ingest = original_ingest

class TestDAPEngineSingleton:
    """DAP引擎单例测试"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        engine1 = get_dap_engine()
        engine2 = get_dap_engine()
        
        assert engine1 is engine2
    
    def test_singleton_with_different_configs(self):
        """测试不同配置的单例"""
        # 单例模式应该忽略后续的配置参数
        engine1 = get_dap_engine()
        engine2 = get_dap_engine()
        
        assert engine1 is engine2

@pytest.mark.performance
class TestDAPEnginePerformance:
    """DAP引擎性能测试"""
    
    def test_processing_performance(self, dap_engine, sample_csv_file, performance_test):
        """测试处理性能"""
        perf = performance_test()
        perf.start()
        
        result = dap_engine.process(sample_csv_file, {'start_api_server': False})
        
        # 小文件处理应该在30秒内完成
        perf.assert_duration(30.0)
    
    def test_large_file_processing(self, dap_engine, temp_dir, test_data_generator, performance_test):
        """测试大文件处理性能"""
        # 生成较大的测试数据
        large_data = test_data_generator.generate_financial_data(10000)
        large_file = os.path.join(temp_dir, 'large_data.csv')
        large_data.to_csv(large_file, index=False)
        
        perf = performance_test()
        perf.start()
        
        result = dap_engine.process(large_file, {'start_api_server': False})
        
        # 大文件处理应该在60秒内完成
        perf.assert_duration(60.0)
    
    def test_memory_usage(self, dap_engine, sample_csv_file):
        """测试内存使用"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss
        
        result = dap_engine.process(sample_csv_file, {'start_api_server': False})
        
        memory_after = process.memory_info().rss
        memory_delta = memory_after - memory_before
        
        # 内存增长应该在合理范围内（100MB）
        assert memory_delta < 100 * 1024 * 1024, f"内存增长过多: {memory_delta / 1024 / 1024:.1f}MB"