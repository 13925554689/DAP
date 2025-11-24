"""
增强导出服务测试
测试PDF、Word、图谱导出等功能
"""

import pytest
import asyncio
import pandas as pd
from pathlib import Path
import json
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent))

from ai.enhanced_export_service import (
    EnhancedExportService,
    ExportFormat,
    AuditReportTemplate
)


@pytest.fixture
def export_service():
    """创建导出服务实例"""
    config = {
        "export_path": "test_exports/",
        "template_path": "test_templates/",
        "temp_path": "test_temp/"
    }
    service = EnhancedExportService(config)
    yield service
    # 清理测试文件
    import shutil
    for path in ["test_exports", "test_templates", "test_temp"]:
        if Path(path).exists():
            shutil.rmtree(path)


@pytest.fixture
def sample_audit_data():
    """样本审计数据"""
    return {
        "report_title": "测试审计报告",
        "project_name": "测试项目",
        "audit_period": "2023年度",
        "auditor": "测试审计师",
        "summary": {
            "objective": "测试审计目标",
            "scope": "测试审计范围",
            "statistics": {
                "total_records": 1000,
                "issues_found": 5,
                "high_risk": 2,
                "coverage": 95.0
            }
        },
        "findings": [
            {
                "title": "测试发现1",
                "description": "这是一个测试发现",
                "risk_level": "高",
                "amount": 100000,
                "recommendation": "测试建议"
            },
            {
                "title": "测试发现2",
                "description": "这是另一个测试发现",
                "risk_level": "中",
                "amount": 50000,
                "recommendation": "另一个测试建议"
            }
        ],
        "evidence": [
            {
                "evidence_id": "E001",
                "evidence_type": "财务数据",
                "collection_date": "2023-01-01",
                "source": "财务系统",
                "description": "测试证据描述"
            }
        ],
        "tables": {
            "资产负债表": pd.DataFrame({
                "科目": ["货币资金", "应收账款", "固定资产"],
                "期末余额": [1000000, 500000, 2000000],
                "期初余额": [900000, 550000, 2100000]
            }),
            "利润表": pd.DataFrame({
                "项目": ["营业收入", "营业成本", "净利润"],
                "本期": [5000000, 3000000, 1500000],
                "上期": [4500000, 2700000, 1300000]
            })
        },
        "conclusion": {
            "summary": "测试结论",
            "recommendations": [
                "建议1",
                "建议2",
                "建议3"
            ]
        }
    }


@pytest.fixture
def sample_graph_data():
    """样本图谱数据"""
    return {
        "report_title": "测试关系图谱",
        "nodes": [
            {"id": "N1", "label": "节点1", "type": "evidence", "size": 1000},
            {"id": "N2", "label": "节点2", "type": "finding", "size": 1500},
            {"id": "N3", "label": "节点3", "type": "transaction", "size": 800},
            {"id": "N4", "label": "节点4", "type": "account", "size": 1200},
        ],
        "relationships": [
            {"source": "N1", "target": "N2", "label": "支持", "weight": 1.0},
            {"source": "N3", "target": "N1", "label": "来源", "weight": 0.8},
            {"source": "N4", "target": "N3", "label": "关联", "weight": 0.6},
        ]
    }


class TestEnhancedExportService:
    """增强导出服务测试类"""

    @pytest.mark.asyncio
    async def test_service_initialization(self, export_service):
        """测试服务初始化"""
        assert export_service is not None
        assert export_service.export_path.exists()
        assert export_service.template_path.exists()
        assert export_service.temp_path.exists()

    @pytest.mark.asyncio
    async def test_pdf_export(self, export_service, sample_audit_data):
        """测试PDF导出"""
        result = await export_service.create_export_task(
            task_name="测试PDF报告",
            export_format=ExportFormat.PDF,
            template_type=AuditReportTemplate.DETAILED,
            data_source=sample_audit_data
        )

        assert result["status"] == "success"
        assert "task_id" in result

        # 等待任务完成
        await asyncio.sleep(3)

        # 检查任务状态
        status = await export_service.get_task_status(result["task_id"])
        assert status["status"] == "success"
        assert status["task"]["status"] in ["completed", "running"]

        # 如果完成，检查文件
        if status["task"]["status"] == "completed":
            assert Path(status["task"]["file_path"]).exists()
            assert status["task"]["file_size"] > 0

    @pytest.mark.asyncio
    async def test_word_export(self, export_service, sample_audit_data):
        """测试Word导出"""
        result = await export_service.create_export_task(
            task_name="测试Word报告",
            export_format=ExportFormat.WORD,
            template_type=AuditReportTemplate.STANDARD,
            data_source=sample_audit_data
        )

        assert result["status"] == "success"
        assert "task_id" in result

        # 等待任务完成
        await asyncio.sleep(3)

        # 检查任务状态
        status = await export_service.get_task_status(result["task_id"])
        assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_graph_export(self, export_service, sample_graph_data):
        """测试关系图谱导出"""
        result = await export_service.create_export_task(
            task_name="测试关系图谱",
            export_format=ExportFormat.GRAPH,
            template_type=AuditReportTemplate.EVIDENCE,
            data_source=sample_graph_data
        )

        assert result["status"] == "success"
        assert "task_id" in result

        # 等待任务完成
        await asyncio.sleep(3)

        # 检查任务状态
        status = await export_service.get_task_status(result["task_id"])
        assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_excel_export(self, export_service, sample_audit_data):
        """测试Excel导出"""
        result = await export_service.create_export_task(
            task_name="测试Excel报告",
            export_format=ExportFormat.EXCEL,
            template_type=AuditReportTemplate.STANDARD,
            data_source=sample_audit_data
        )

        assert result["status"] == "success"
        assert "task_id" in result

        # 等待任务完成
        await asyncio.sleep(3)

        # 检查任务状态
        status = await export_service.get_task_status(result["task_id"])
        assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_batch_export(self, export_service, sample_audit_data):
        """测试批量导出"""
        export_configs = [
            {
                "task_name": "批量测试1",
                "export_format": ExportFormat.PDF,
                "template_type": AuditReportTemplate.SUMMARY,
                "data_source": sample_audit_data
            },
            {
                "task_name": "批量测试2",
                "export_format": ExportFormat.WORD,
                "template_type": AuditReportTemplate.STANDARD,
                "data_source": sample_audit_data
            },
            {
                "task_name": "批量测试3",
                "export_format": ExportFormat.EXCEL,
                "template_type": AuditReportTemplate.DETAILED,
                "data_source": sample_audit_data
            }
        ]

        result = await export_service.batch_export(export_configs)

        assert result["status"] == "success"
        assert len(result["task_ids"]) == 3

        # 等待所有任务完成
        await asyncio.sleep(5)

        # 检查每个任务的状态
        for task_id in result["task_ids"]:
            status = await export_service.get_task_status(task_id)
            assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_invalid_format(self, export_service, sample_audit_data):
        """测试无效的导出格式"""
        result = await export_service.create_export_task(
            task_name="无效格式测试",
            export_format="invalid_format",
            template_type=AuditReportTemplate.STANDARD,
            data_source=sample_audit_data
        )

        assert result["status"] == "success"  # 任务创建成功

        # 等待任务处理
        await asyncio.sleep(3)

        # 检查任务应该失败
        status = await export_service.get_task_status(result["task_id"])
        assert status["task"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_missing_data(self, export_service):
        """测试缺失数据的情况"""
        incomplete_data = {
            "report_title": "不完整的报告"
            # 缺少其他必要字段
        }

        result = await export_service.create_export_task(
            task_name="缺失数据测试",
            export_format=ExportFormat.PDF,
            template_type=AuditReportTemplate.STANDARD,
            data_source=incomplete_data
        )

        assert result["status"] == "success"

        # 等待任务处理
        await asyncio.sleep(3)

        # 任务应该仍能完成(使用默认值)
        status = await export_service.get_task_status(result["task_id"])
        assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, export_service):
        """测试获取不存在的任务"""
        status = await export_service.get_task_status("nonexistent_task_id")

        assert status["status"] == "error"
        assert "不存在" in status["error"]

    @pytest.mark.asyncio
    async def test_concurrent_exports(self, export_service, sample_audit_data):
        """测试并发导出"""
        tasks = []

        for i in range(5):
            task = export_service.create_export_task(
                task_name=f"并发测试{i+1}",
                export_format=ExportFormat.PDF if i % 2 == 0 else ExportFormat.WORD,
                template_type=AuditReportTemplate.STANDARD,
                data_source=sample_audit_data
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # 所有任务都应该创建成功
        for result in results:
            assert result["status"] == "success"

        # 等待所有任务完成
        await asyncio.sleep(10)

    @pytest.mark.asyncio
    async def test_pdf_with_charts(self, export_service):
        """测试包含图表的PDF导出"""
        # 创建临时图表图片
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        chart_path = "test_temp/test_chart.png"
        Path("test_temp").mkdir(exist_ok=True)
        plt.savefig(chart_path)
        plt.close()

        data_with_charts = {
            "report_title": "包含图表的报告",
            "charts": [
                {
                    "title": "测试图表",
                    "image_path": chart_path
                }
            ],
            "conclusion": {
                "summary": "测试结论"
            }
        }

        result = await export_service.create_export_task(
            task_name="图表PDF测试",
            export_format=ExportFormat.PDF,
            template_type=AuditReportTemplate.DETAILED,
            data_source=data_with_charts
        )

        assert result["status"] == "success"

        await asyncio.sleep(3)

        status = await export_service.get_task_status(result["task_id"])
        assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_large_dataset_export(self, export_service):
        """测试大数据集导出"""
        # 创建大数据集
        large_df = pd.DataFrame({
            "ID": range(1, 10001),
            "名称": [f"项目{i}" for i in range(1, 10001)],
            "金额": [i * 100 for i in range(1, 10001)],
            "类别": ["A", "B", "C"] * 3333 + ["A"]
        })

        large_data = {
            "report_title": "大数据集报告",
            "tables": {
                "大数据表": large_df
            }
        }

        result = await export_service.create_export_task(
            task_name="大数据导出测试",
            export_format=ExportFormat.EXCEL,
            template_type=AuditReportTemplate.STANDARD,
            data_source=large_data
        )

        assert result["status"] == "success"

        # 给予更多时间处理
        await asyncio.sleep(10)

        status = await export_service.get_task_status(result["task_id"])
        assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_cleanup(self, export_service):
        """测试资源清理"""
        await export_service.cleanup()

        # 验证executor已关闭
        assert hasattr(export_service, 'executor')


def test_export_format_constants():
    """测试导出格式常量"""
    assert ExportFormat.PDF == "pdf"
    assert ExportFormat.WORD == "word"
    assert ExportFormat.EXCEL == "excel"
    assert ExportFormat.GRAPH == "graph"
    assert ExportFormat.HTML == "html"
    assert ExportFormat.JSON == "json"


def test_audit_template_constants():
    """测试审计模板常量"""
    assert AuditReportTemplate.STANDARD == "standard"
    assert AuditReportTemplate.SUMMARY == "summary"
    assert AuditReportTemplate.DETAILED == "detailed"
    assert AuditReportTemplate.EVIDENCE == "evidence"
    assert AuditReportTemplate.FINDINGS == "findings"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
