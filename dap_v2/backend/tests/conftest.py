# -*- coding: utf-8 -*-
"""
DAP v2.0 - Test Configuration
测试配置和Fixtures
"""
import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from models.database import Base
from main import app
from config import settings


# 测试数据库
TEST_DATABASE_URL = "sqlite:///./test_dap_v2.db"


@pytest.fixture(scope="session")
def test_engine():
    """测试数据库引擎"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """测试数据库会话"""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def test_client():
    """测试客户端"""
    client = TestClient(app)
    return client


@pytest.fixture
def sample_evidence_data():
    """示例证据数据"""
    return {
        "evidence_name": "测试银行对账单",
        "evidence_type": "BANK_STATEMENT",
        "project_id": "test_project_001",
        "content_text": "测试内容:收款50000元,日期2024-01-15",
        "amount": 50000.0,
        "related_accounts": "1002-银行存款"
    }


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
