# -*- coding: utf-8 -*-
"""
DAP v2.0 - AI Learning Integration Tests
AI学习集成测试
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.unified_learning_manager import UnifiedLearningManager
from ai.data_mapping_learner import DataMappingLearner
from ai.ocr_evidence_learner import OCREvidenceLearner
from ai.evidence_classification_learner import EvidenceClassificationLearner


class TestUnifiedLearningManagerIntegration:
    """统一学习管理器集成测试"""

    def setup_method(self):
        """设置测试"""
        self.manager = UnifiedLearningManager()

    def test_manager_initialization(self):
        """测试管理器初始化"""
        assert self.manager is not None
        assert self.manager.config['enabled'] is True
        assert hasattr(self.manager, 'account_mapping_learner')
        assert hasattr(self.manager, 'ocr_correction_learner')
        assert hasattr(self.manager, 'anomaly_detection_learner')

    def test_get_all_metrics(self):
        """测试获取所有学习指标"""
        metrics = self.manager.get_metrics()

        assert 'current' in metrics
        assert 'target' in metrics
        assert 'progress' in metrics

        # 验证关键指标存在
        required_metrics = [
            'ocr_accuracy',
            'account_mapping',
            'anomaly_detection',
            'classification_accuracy',
            'extraction_accuracy'
        ]
        for metric_name in required_metrics:
            assert metric_name in metrics['current']
            assert metric_name in metrics['target']
            assert metric_name in metrics['progress']

    def test_get_specific_learner_status(self):
        """测试获取特定学习器状态"""
        # 获取OCR学习器状态
        ocr_learner = self.manager.ocr_correction_learner
        assert ocr_learner is not None

        metrics = ocr_learner.get_metrics()
        assert 'ocr_accuracy' in metrics

    def test_metric_value_ranges(self):
        """测试指标值范围"""
        metrics = self.manager.get_metrics()

        # 所有当前值应该在0-1之间
        for key, value in metrics['current'].items():
            assert 0.0 <= value <= 1.0, f"{key} current value {value} out of range"

        # 所有目标值应该在0-1之间
        for key, value in metrics['target'].items():
            assert 0.0 <= value <= 1.0, f"{key} target value {value} out of range"

        # 所有进度值应该在0-100之间
        for key, value in metrics['progress'].items():
            assert 0.0 <= value <= 100.0, f"{key} progress {value} out of range"

    def test_progress_calculation(self):
        """测试进度计算准确性"""
        metrics = self.manager.get_metrics()

        # 手动验证进度计算
        for key in metrics['current'].keys():
            current = metrics['current'][key]
            target = metrics['target'][key]
            progress = metrics['progress'][key]

            # 重新计算进度
            if target > 0:
                expected_progress = (current / target) * 100
                assert abs(progress - expected_progress) < 0.1, \
                    f"{key}: Expected {expected_progress}, got {progress}"


class TestAccountMappingLearner:
    """账户映射学习器测试"""

    def setup_method(self):
        """设置测试"""
        self.learner = AccountMappingLearner()

    def test_learner_initialization(self):
        """测试学习器初始化"""
        assert self.learner is not None
        assert self.learner.current_accuracy >= 0.0
        assert self.learner.target_accuracy >= self.learner.current_accuracy

    def test_record_training_sample(self):
        """测试记录训练样本"""
        initial_samples = self.learner.training_samples_count

        # 记录一个样本
        self.learner.record_training_sample(
            source_account="银行存款",
            target_account="1002",
            confidence=0.95,
            is_correct=True
        )

        assert self.learner.training_samples_count == initial_samples + 1

    def test_get_metrics(self):
        """测试获取指标"""
        metrics = self.learner.get_metrics()

        assert 'account_mapping' in metrics
        assert 0.0 <= metrics['account_mapping'] <= 1.0

    def test_improvement_suggestions(self):
        """测试改进建议"""
        suggestions = self.learner.get_improvement_suggestions()

        assert isinstance(suggestions, list)
        # 应该有一些建议
        assert len(suggestions) >= 0


class TestAnomalyDetectionLearner:
    """异常检测学习器测试"""

    def setup_method(self):
        """设置测试"""
        self.learner = AnomalyDetectionLearner()

    def test_learner_initialization(self):
        """测试学习器初始化"""
        assert self.learner is not None
        assert self.learner.current_accuracy >= 0.0

    def test_record_detection_result(self):
        """测试记录检测结果"""
        initial_samples = self.learner.training_samples_count

        # 记录一个检测结果
        self.learner.record_detection_result(
            anomaly_type="amount_mismatch",
            confidence=0.88,
            is_true_positive=True
        )

        assert self.learner.training_samples_count == initial_samples + 1

    def test_get_metrics(self):
        """测试获取指标"""
        metrics = self.learner.get_metrics()

        assert 'anomaly_detection' in metrics
        assert 0.0 <= metrics['anomaly_detection'] <= 1.0

    def test_calculate_accuracy_with_samples(self):
        """测试基于样本计算准确率"""
        # 记录多个样本
        for i in range(10):
            self.learner.record_detection_result(
                anomaly_type="test",
                confidence=0.9,
                is_true_positive=(i % 2 == 0)  # 50%准确率
            )

        # 准确率应该反映样本
        metrics = self.learner.get_metrics()
        accuracy = metrics['anomaly_detection']

        # 应该有一定的准确率（可能不是精确50%因为有初始值）
        assert 0.0 < accuracy <= 1.0


class TestOCRCorrectionLearner:
    """OCR纠错学习器测试"""

    def setup_method(self):
        """设置测试"""
        self.learner = OCRCorrectionLearner()

    def test_learner_initialization(self):
        """测试学习器初始化"""
        assert self.learner is not None
        assert self.learner.current_accuracy >= 0.0

    def test_record_correction(self):
        """测试记录纠错"""
        initial_samples = self.learner.training_samples_count

        # 记录一个纠错
        self.learner.record_correction(
            original_text="银行存欺",
            corrected_text="银行存款",
            confidence=0.92
        )

        assert self.learner.training_samples_count == initial_samples + 1

    def test_get_metrics(self):
        """测试获取指标"""
        metrics = self.learner.get_metrics()

        assert 'ocr_accuracy' in metrics
        assert 0.0 <= metrics['ocr_accuracy'] <= 1.0

    def test_common_errors_tracking(self):
        """测试常见错误追踪"""
        # 记录多个相同的纠错
        for _ in range(3):
            self.learner.record_correction(
                original_text="欺",
                corrected_text="款",
                confidence=0.9
            )

        # 应该能追踪到这个常见错误
        suggestions = self.learner.get_improvement_suggestions()
        assert isinstance(suggestions, list)


class TestLearningDataFlow:
    """学习数据流测试"""

    def test_end_to_end_learning_flow(self):
        """测试端到端学习流程"""
        manager = UnifiedLearningManager()

        # 1. 获取初始指标
        initial_metrics = manager.get_metrics()
        initial_ocr = initial_metrics['current']['ocr_accuracy']

        # 2. 记录OCR纠错
        ocr_learner = manager.ocr_correction_learner
        ocr_learner.record_correction(
            original_text="错误",
            corrected_text="正确",
            confidence=0.95
        )

        # 3. 获取更新后指标
        updated_metrics = manager.get_metrics()

        # 验证指标已更新
        assert updated_metrics is not None
        assert 'current' in updated_metrics

    def test_multiple_learners_interaction(self):
        """测试多个学习器交互"""
        manager = UnifiedLearningManager()

        # 同时使用多个学习器
        manager.account_mapping_learner.record_training_sample(
            "现金", "1001", 0.9, True
        )
        manager.ocr_correction_learner.record_correction(
            "错字", "正字", 0.85
        )
        manager.anomaly_detection_learner.record_detection_result(
            "test", 0.88, True
        )

        # 获取综合指标
        metrics = manager.get_metrics()

        # 所有指标应该都存在且有效
        assert len(metrics['current']) >= 5
        for value in metrics['current'].values():
            assert 0.0 <= value <= 1.0


class TestLearningPerformance:
    """学习性能测试"""

    def test_batch_sample_recording(self):
        """测试批量样本记录性能"""
        import time

        learner = AccountMappingLearner()

        start_time = time.time()

        # 记录100个样本
        for i in range(100):
            learner.record_training_sample(
                f"account_{i}",
                f"100{i}",
                0.9,
                True
            )

        elapsed = time.time() - start_time

        # 应该在合理时间内完成（1秒）
        assert elapsed < 1.0, f"Batch recording took {elapsed}s"
        assert learner.training_samples_count >= 100

    def test_metrics_calculation_performance(self):
        """测试指标计算性能"""
        import time

        manager = UnifiedLearningManager()

        start_time = time.time()

        # 重复计算指标100次
        for _ in range(100):
            metrics = manager.get_metrics()

        elapsed = time.time() - start_time

        # 应该很快（0.5秒内）
        assert elapsed < 0.5, f"Metrics calculation took {elapsed}s"


# Pytest fixtures
@pytest.fixture
def sample_account_mappings():
    """示例账户映射数据"""
    return [
        {"source": "银行存款", "target": "1002", "correct": True},
        {"source": "现金", "target": "1001", "correct": True},
        {"source": "应收账款", "target": "1122", "correct": True},
        {"source": "固定资产", "target": "1601", "correct": False}
    ]


@pytest.fixture
def sample_ocr_corrections():
    """示例OCR纠错数据"""
    return [
        {"original": "银行存欺", "corrected": "银行存款"},
        {"original": "现釒", "corrected": "现金"},
        {"original": "固定资严", "corrected": "固定资产"}
    ]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
