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
    """Fallback data ingestor that supports CSV and Excel sources with auto-upgrade hint."""

    SUPPORTED_EXTENSIONS = {".csv", ".txt", ".xlsx", ".xls", ".xlsm"}

    def ingest(self, file_path: str) -> Dict[str, pd.DataFrame]:
        if not file_path:
            raise DataIngestionError("数据源路径不能为空")

        if not os.path.exists(file_path):
            raise DataIngestionError("数据源不存在", file_path=file_path)

        # 检测是否需要完整模式
        if os.path.isdir(file_path):
            self._suggest_upgrade("文件夹批量导入")
            raise DataIngestionError(
                "检测到文件夹导入需求。\n\n"
                "💡 系统正在尝试自动切换到完整模式...\n"
                "如自动切换失败,请手动安装完整依赖:\n"
                "  pip install rarfile py7zr",
                file_path=file_path
            )

        suffix = Path(file_path).suffix.lower()

        if not suffix:
            raise DataIngestionError("无法识别文件类型,请补充扩展名", file_path=file_path)

        # 检测不支持的文件类型并提示升级
        if suffix not in self.SUPPORTED_EXTENSIONS:
            self._suggest_upgrade(f"文件类型 {suffix}")
            raise DataIngestionError(
                f"检测到高级文件类型: {suffix}\n\n"
                f"💡 系统正在尝试自动切换到完整模式...\n"
                f"如自动切换失败,请手动安装完整依赖:\n"
                f"  pip install rarfile py7zr",
                file_path=file_path,
            )

        try:
            if suffix in {".csv", ".txt"}:
                dataframe = pd.read_csv(file_path)
            else:
                dataframe = pd.read_excel(file_path)
        except Exception as exc:
            raise DataIngestionError(f"数据解析失败: {exc}", file_path=file_path) from exc

        if dataframe.empty:
            raise DataIngestionError("未解析到有效数据", file_path=file_path)

        return {"primary": dataframe}

    def _suggest_upgrade(self, feature: str):
        """Suggest upgrading to full mode"""
        logger.info(
            f"✨ 检测到需要完整模式功能: {feature}\n"
            f"   推荐安装: pip install rarfile py7zr\n"
            f"   或运行: fix_dependencies.bat"
        )


class LightweightStorageManager:
    """In-memory storage manager used when the hybrid storage is unavailable."""

    DEFAULT_PROJECT_ID = "default_project"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._tables: Dict[str, pd.DataFrame] = {}
        self._current_project_id = self.DEFAULT_PROJECT_ID
        self._projects = {
            self.DEFAULT_PROJECT_ID: {
                "project_id": self.DEFAULT_PROJECT_ID,
                "project_code": "DEFAULT",
                "project_name": "默认项目",
                "client_name": None,
                "fiscal_year": None,
                "fiscal_period": None,
            }
        }

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

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects"""
        return list(self._projects.values())

    def get_project(self, project_identifier: str) -> Optional[Dict[str, Any]]:
        """Get project by ID, code, or name"""
        # Try direct ID match
        if project_identifier in self._projects:
            return self._projects[project_identifier].copy()

        # Try matching by code or name
        for project in self._projects.values():
            if (project.get("project_code") == project_identifier or
                project.get("project_name") == project_identifier):
                return project.copy()

        return None

    def create_project(
        self,
        project_name: str,
        project_code: Optional[str] = None,
        client_name: Optional[str] = None,
        fiscal_year: Optional[str] = None,
        fiscal_period: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> str:
        """Create a new project"""
        project_id = project_code or f"proj_{len(self._projects) + 1}"

        self._projects[project_id] = {
            "project_id": project_id,
            "project_code": project_code or project_id,
            "project_name": project_name,
            "client_name": client_name,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "created_by": created_by or "系统",
        }

        return project_id

    def set_current_project(self, project_id: str) -> bool:
        """Set the current project"""
        if project_id in self._projects:
            self._current_project_id = project_id
            return True
        return False

    def get_current_project(self) -> Optional[Dict[str, Any]]:
        """Get the current project"""
        return self._projects.get(self._current_project_id)

    def list_entities_summary(self) -> List[Dict[str, Any]]:
        """List entities summary (stub implementation)"""
        return []

    # ==================== Entity Management Methods ====================

    def create_entity(
        self,
        project_id: str,
        entity_code: str,
        entity_name: str,
        entity_type: str = "子公司",
        parent_entity_id: Optional[int] = None,
        ownership_percentage: float = 100.0,
        **kwargs
    ) -> int:
        """Create a new entity (company) in a project.

        Note: This is a lightweight stub. Full implementation requires database.
        """
        logger.warning("Entity management requires database upgrade. Returning stub entity ID.")
        return -1

    def list_entities(self, project_id: str) -> List[Dict[str, Any]]:
        """List all entities in a project.

        Note: This is a lightweight stub. Full implementation requires database.
        """
        logger.warning("Entity management requires database upgrade. Returning empty list.")
        return []

    def get_entity(self, entity_id: int) -> Optional[Dict[str, Any]]:
        """Get entity by ID.

        Note: This is a lightweight stub. Full implementation requires database.
        """
        logger.warning("Entity management requires database upgrade. Returning None.")
        return None

    def update_entity(self, entity_id: int, **kwargs) -> bool:
        """Update entity information.

        Note: This is a lightweight stub. Full implementation requires database.
        """
        logger.warning("Entity management requires database upgrade. Returning False.")
        return False

    def delete_entity(self, entity_id: int) -> bool:
        """Delete an entity.

        Note: This is a lightweight stub. Full implementation requires database.
        """
        logger.warning("Entity management requires database upgrade. Returning False.")
        return False

    def get_entity_hierarchy(self, parent_entity_id: int) -> List[Dict[str, Any]]:
        """Get entity hierarchy tree starting from parent.

        Note: This is a lightweight stub. Full implementation requires database.
        """
        logger.warning("Entity hierarchy requires database upgrade. Returning empty list.")
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
