# -*- coding: utf-8 -*-
"""
DAP v2.0 - AI Services Tests
AI服务测试
"""
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.auto_linking_service import EvidenceAutoLinkingService


class TestAutoLinkingService:
    """智能关联服务测试"""

    def setup_method(self):
        """设置测试"""
        self.service = EvidenceAutoLinkingService()

    def test_keyword_similarity(self):
        """测试关键词相似度"""
        text1 = "银行收款50000元,日期2024-01-15"
        text2 = "销售商品收入50000元,2024-01-15"

        similarity = self.service._calculate_keyword_similarity(text1, text2)
        assert 0 <= similarity <= 1
        assert similarity > 0  # 应该有一定相似度

    def test_amount_match(self):
        """测试金额匹配"""
        # 完全匹配
        assert self.service._check_amount_match(50000.0, 50000.0) is True

        # 在容差范围内
        assert self.service._check_amount_match(50000.0, 50100.0) is True

        # 不匹配
        assert self.service._check_amount_match(50000.0, 60000.0) is False

        # None值
        assert self.service._check_amount_match(None, 50000.0) is False

    def test_time_proximity(self):
        """测试时间接近度"""
        time1 = "2024-01-15T10:00:00"
        time2 = "2024-01-15T11:00:00"
        time3 = "2024-02-15T10:00:00"

        # 同一天
        score1 = self.service._calculate_time_proximity(time1, time2)
        assert score1 > 0.9

        # 相差1个月
        score2 = self.service._calculate_time_proximity(time1, time3)
        assert score2 == 0.0  # 超出时间窗口

    def test_find_related_evidences(self, sample_evidence_list):
        """测试查找相关证据"""
        target = sample_evidence_list[0]
        others = sample_evidence_list[1:]

        related = self.service.find_related_evidences(target, others, max_results=5)

        assert isinstance(related, list)
        # 应该能找到至少1个相关证据(金额相同)
        assert len(related) >= 1

        # 检查返回结构
        if related:
            assert 'evidence_id' in related[0]
            assert 'relation_score' in related[0]
            assert 'relation_reasons' in related[0]

    def test_build_evidence_graph(self):
        """测试构建证据图谱"""
        relations = [
            {
                'evidence_id': 'ev001',
                'related_evidence_id': 'ev002',
                'relation_type': '金额关联',
                'confidence': 0.9
            },
            {
                'evidence_id': 'ev002',
                'related_evidence_id': 'ev003',
                'relation_type': '业务关联',
                'confidence': 0.8
            }
        ]

        graph = self.service.build_evidence_graph('ev001', relations, depth=2)

        assert 'nodes' in graph
        assert 'edges' in graph
        assert 'center' in graph
        assert graph['center'] == 'ev001'
        assert len(graph['nodes']) > 0
        assert len(graph['edges']) > 0


class TestPaddleOCRService:
    """OCR服务测试"""

    def test_ocr_service_init(self):
        """测试OCR服务初始化"""
        from ai.paddleocr_service import get_ocr_service

        service = get_ocr_service()
        assert service is not None
        # OCR可能未安装,只测试服务对象存在

    def test_extract_keywords(self):
        """测试关键词提取"""
        from ai.auto_linking_service import EvidenceAutoLinkingService

        service = EvidenceAutoLinkingService()
        text = "银行收款50000元,日期2024-01-15,合同编号HT001"

        keywords = service._extract_keywords(text)
        assert isinstance(keywords, set)
        assert len(keywords) > 0
        # 应该提取到数字
        assert any('50000' in kw or '2024' in kw for kw in keywords)


class TestUnifiedLearningManager:
    """统一学习管理器测试"""

    def test_learning_manager_init(self):
        """测试学习管理器初始化"""
        from ai.unified_learning_manager import UnifiedLearningManager

        manager = UnifiedLearningManager()
        assert manager is not None
        assert manager.config['enabled'] is True
        assert 'model_path' in manager.config

    def test_get_metrics(self):
        """测试获取指标"""
        from ai.unified_learning_manager import UnifiedLearningManager

        manager = UnifiedLearningManager()
        metrics = manager.get_metrics()

        assert 'current' in metrics
        assert 'target' in metrics
        assert 'progress' in metrics
        assert 'ocr_accuracy' in metrics['current']


# Pytest配置
@pytest.fixture
def sample_evidence_list():
    """示例证据列表"""
    return [
        {
            "id": "ev001",
            "evidence_name": "银行对账单01",
            "evidence_type": "BANK_STATEMENT",
            "content_text": "收款50000元,2024-01-15",
            "amount": 50000.0,
            "related_accounts": "1002-银行存款",
            "created_at": "2024-01-15T10:00:00"
        },
        {
            "id": "ev002",
            "evidence_name": "销售发票01",
            "evidence_type": "INVOICE",
            "content_text": "销售商品50000元,2024-01-15",
            "amount": 50000.0,
            "related_accounts": "4001-主营业务收入",
            "created_at": "2024-01-15T11:00:00"
        },
        {
            "id": "ev003",
            "evidence_name": "合同01",
            "evidence_type": "CONTRACT",
            "content_text": "销售合同,金额50000元",
            "amount": 50000.0,
            "related_accounts": "1122-应收账款",
            "created_at": "2024-01-10T09:00:00"
        }
    ]
