"""Lightweight fallback implementations for core DAP components."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.exceptions import DataIngestionError

logger = logging.getLogger(__name__)


def _collect_warning(message: str, code: str) -> Dict[str, Any]:
    """Utility to construct a standardized fallback response."""
    return {"success": False, "error": message, "warnings": [code]}


def start_lightweight_api_server(*_args, **_kwargs) -> Dict[str, Any]:
    """Stub for API server when the real implementation is unavailable."""
    logger.warning("Lightweight API server invoked; HTTP endpoints are disabled.")
    return _collect_warning(
        "API server unavailable in lightweight mode", "API_SERVER_FALLBACK"
    )


class LightweightDataIngestor:
    """Fallback data ingestor that supports CSV and Excel sources."""

    SUPPORTED_EXTENSIONS = {".csv", ".txt", ".xlsx", ".xls", ".xlsm"}

    def ingest(self, file_path: str) -> Dict[str, pd.DataFrame]:
        if not file_path:
            raise DataIngestionError("数据源路径不能为空")

        if not os.path.exists(file_path):
            raise DataIngestionError("数据源不存在", file_path=file_path)

        if os.path.isdir(file_path):
            raise DataIngestionError("轻量模式暂不支持直接导入文件夹，请切换至完整模式。", file_path=file_path)

        suffix = Path(file_path).suffix.lower()

        if not suffix:
            raise DataIngestionError("无法识别文件类型，请补充扩展名或使用完整模式。", file_path=file_path)

        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise DataIngestionError(
                f"轻量模式不支持的文件类型: {suffix}，请切换至完整模式处理。",
                file_path=file_path,
            )

        try:
            if suffix in {".csv", ".txt"}:
                dataframe = pd.read_csv(file_path)
            else:
                dataframe = pd.read_excel(file_path)
        except Exception as exc:  # pragma: no cover - I/O 防御
            raise DataIngestionError(f"数据解析失败: {exc}", file_path=file_path) from exc

        if dataframe.empty:
            raise DataIngestionError("未解析到有效数据", file_path=file_path)

        return {"primary": dataframe}


class LightweightStorageManager:
    """In-memory storage manager used when the hybrid storage is unavailable."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._tables: Dict[str, pd.DataFrame] = {}

    def store_cleaned_data(
        self, cleaned_data: Dict[str, pd.DataFrame], schema: Dict[str, Any]
    ) -> bool:
        for name, frame in cleaned_data.items():
            self._tables[name] = frame.copy()
        return True

    def get_table_list(self) -> List[Dict[str, Any]]:
        return [
            {"table_name": name, "row_count": len(frame)}
            for name, frame in self._tables.items()
        ]

    def get_view_list(self) -> List[Dict[str, Any]]:
        return []


class LightweightAuditRulesEngine:
    """Simple audit rules engine producing deterministic statistics."""

    def apply_all_rules(self) -> Dict[str, Any]:
        return {
            "successful_rules": 0,
            "failed_rules": 0,
            "warnings": ["AUDIT_RULES_ENGINE_FALLBACK"],
            "details": [],
        }


class LightweightDimensionOrganizer:
    """Minimal dimension organizer that reports no generated views."""

    def organize_by_all_dimensions(self) -> Dict[str, Any]:
        return {
            "success": True,
            "stats": {"views_created": 0},
            "warnings": ["DIMENSION_ORGANIZER_FALLBACK"],
        }


class LightweightOutputFormatter:
    """Provides safe placeholders for export- and report-related operations."""

    def __init__(self, export_dir: str):
        self.export_dir = export_dir
        self._history: List[Dict[str, Any]] = []
        self._imported_tables: List[Dict[str, Any]] = []

    def export_data(
        self, source: str, format: str, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "EXPORTER_UNAVAILABLE",
            "source": source,
            "format": format,
            "warnings": ["OUTPUT_FORMATTER_FALLBACK"],
        }

    def generate_audit_report(
        self, company_name: str, period: str, format: str = "html"
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "REPORTING_UNAVAILABLE",
            "company": company_name,
            "period": period,
            "format": format,
            "warnings": ["OUTPUT_FORMATTER_FALLBACK"],
        }

    def import_data_from_file(
        self,
        file_path: str,
        table_name: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        options = options or {}
        try:
            ingestor = LightweightDataIngestor()
            data = ingestor.ingest(file_path)
            primary_name, primary_frame = next(iter(data.items()))
            target_table = table_name or primary_name

            record = {
                "table_name": target_table,
                "source_file": file_path,
                "rows": len(primary_frame),
                "options": options,
            }
            self._history.append(record)
            self._imported_tables.append(
                {"table_name": target_table, "rows": len(primary_frame)}
            )

            return {
                "success": True,
                "table_name": target_table,
                "rows": len(primary_frame),
                "warnings": ["OUTPUT_FORMATTER_FALLBACK"],
            }
        except DataIngestionError as exc:
            return {
                "success": False,
                "error": str(exc),
                "error_code": exc.error_code,
                "warnings": ["OUTPUT_FORMATTER_FALLBACK"],
            }

    def get_import_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def get_imported_tables(self) -> List[Dict[str, Any]]:
        return list(self._imported_tables)


class LightweightAIAgentBridge:
    """Minimal AI agent bridge used when external services are unavailable."""

    def __init__(self):
        self._clients = ["stub-ai"]

    def get_available_clients(self) -> List[str]:
        return list(self._clients)

    def call_ai_analysis(
        self, prompt: str, data: Optional[Any] = None
    ) -> Dict[str, Any]:
        summary: Optional[Dict[str, Any]] = None

        if data is not None:
            if isinstance(data, pd.DataFrame):
                summary = {"rows": len(data), "columns": list(data.columns)}
            elif isinstance(data, dict):
                summary = {
                    key: getattr(value, "__len__", lambda: 1)()
                    for key, value in data.items()
                }

        return {
            "success": True,
            "mode": "LIGHTWEIGHT",
            "result": f"Stub analysis for prompt: {prompt}",
            "data_summary": summary,
            "warnings": ["AI_AGENT_BRIDGE_FALLBACK"],
        }


class LightweightThirdPartyIntegrator:
    """Stub for the third-party integrator."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

    async def start_integrator(self) -> Dict[str, Any]:
        self.logger.warning(
            "Third-party integrator is unavailable in lightweight mode."
        )
        return _collect_warning(
            "Third-party integrator disabled in lightweight mode",
            "THIRD_PARTY_INTEGRATOR_FALLBACK",
        )

    async def stop_integrator(self) -> None:
        self.logger.info("Third-party integrator fallback stopped.")

    async def sync_integration(self, *_args, **_kwargs) -> Dict[str, Any]:
        self.logger.warning("Sync integration skipped in lightweight mode.")
        return _collect_warning(
            "Sync integration skipped", "THIRD_PARTY_INTEGRATOR_FALLBACK"
        )


class LightweightCloudServiceConnector:
    """Stub for cloud deployment workflows."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

    async def deploy_to_cloud(
        self, provider: str, deployment_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.logger.warning(
            "Cloud deployment to %s skipped in lightweight mode.", provider
        )
        return _collect_warning(
            f"Cloud deployment to {provider} unavailable", "CLOUD_CONNECTOR_FALLBACK"
        )

    async def monitor_deployment(self, *_args, **_kwargs) -> Dict[str, Any]:
        self.logger.info("Cloud deployment monitoring skipped in lightweight mode.")
        return {
            "success": False,
            "warnings": ["CLOUD_CONNECTOR_FALLBACK"],
            "status": "not_monitored",
        }


class LightweightAPIServer:
    """Callable stub mimicking a FastAPI application."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def __call__(self, *_args, **_kwargs):
        self.logger.warning(
            "Incoming API request handled by lightweight fallback; returning 503."
        )
        return {
            "success": False,
            "error": "API server disabled in lightweight mode",
            "status_code": 503,
            "warnings": ["API_SERVER_FALLBACK"],
        }
