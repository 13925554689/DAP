"""
DAP (Data Processing & Auditing Intelligence Agent) - Enhanced Main Engine
智能审计数据处理系统 - 增强版主引擎
基于第一性原理 + KISS + SOLID + AI增强的五层架构设计
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
import threading
import time
import json

from config.settings import get_config

# 添加项目路径到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# 导入增强的各层模块
try:
    # 第一层：智能数据接入与标准化
    from layer1.enhanced_data_ingestor import EnhancedDataIngestor
    from layer1.ai_schema_inferrer import AISchemaInferrer
    from layer1.intelligent_data_scrubber import IntelligentDataScrubber
    from layer1.hybrid_storage_manager import HybridStorageManager
except ImportError:
    # 向下兼容：使用现有模块
    from layer1.data_ingestor import DataIngestor as EnhancedDataIngestor
    from layer1.schema_inferrer import SchemaInferrer as AISchemaInferrer
    from layer1.data_scrubber import DataScrubber as IntelligentDataScrubber
    from layer1.storage_manager import StorageManager as HybridStorageManager
try:
    # 第二层：分层存储与数据管理
    from layer2.storage_optimizer import StorageOptimizer
    from layer2.data_lineage_tracker import DataLineageTracker
    from layer2.version_controller import VersionController
    from layer2.performance_optimizer import PerformanceOptimizer
except ImportError:
    # 向下兼容：使用现有模块
    from layer2.audit_rules_engine import AuditRulesEngine as StorageOptimizer
    from layer2.dimension_organizer import DimensionOrganizer as DataLineageTracker

    # 提供基础实现
    class VersionController:
        def __init__(self, db_path):
            pass

    class PerformanceOptimizer:
        def __init__(self, db_path):
            pass


try:
    from layer2.audit_rules_engine import AuditRulesEngine
except ImportError:
    AuditRulesEngine = None
try:
    from layer2.dimension_organizer import DimensionOrganizer
except ImportError:
    DimensionOrganizer = None
try:
    # 第三层：AI增强审计规则引擎
    from layer3.ai_audit_rules_engine import AIAuditRulesEngine
    from layer3.adaptive_account_mapper import AdaptiveAccountMapper
    from layer3.anomaly_detector import AnomalyDetector
    from layer3.audit_knowledge_base import AuditKnowledgeBase
except ImportError:
    # 提供基础实现
    class AIAuditRulesEngine:
        def __init__(self, db_path):
            pass

    class AdaptiveAccountMapper:
        def __init__(self, db_path):
            pass

    class AnomalyDetector:
        def __init__(self, db_path):
            pass

    class AuditKnowledgeBase:
        def __init__(self, db_path):
            pass


try:
    # 第四层：多模式分析与输出服务
    from layer4.standard_report_generator import StandardReportGenerator
    from layer4.interactive_analyzer import InteractiveAnalyzer
    from layer4.nl_audit_agent import NLAuditAgent
    from layer4.multi_format_exporter import MultiFormatExporter
except ImportError:
    # 提供基础实现
    class StandardReportGenerator:
        def __init__(self, db_path):
            pass

    class InteractiveAnalyzer:
        def __init__(self, db_path):
            pass

    class NLAuditAgent:
        def __init__(self, db_path):
            pass

    class MultiFormatExporter:
        def __init__(self, db_path):
            pass


try:
    from layer5.ai_agent_bridge import AIAgentBridge
except ImportError:
    try:
        from layer3.agent_bridge import AgentBridge as AIAgentBridge
    except ImportError:
        from utils.lightweight_components import (
            LightweightAIAgentBridge as AIAgentBridge,
        )

try:
    from layer5.third_party_integrator import ThirdPartyIntegrator
except ImportError:
    from utils.lightweight_components import (
        LightweightThirdPartyIntegrator as ThirdPartyIntegrator,
    )

try:
    from layer5.cloud_service_connector import CloudServiceConnector
except ImportError:
    from utils.lightweight_components import (
        LightweightCloudServiceConnector as CloudServiceConnector,
    )

try:
    from layer5.github_backup_manager import GitHubBackupManager
except ImportError:
    GitHubBackupManager = None

try:
    from layer5.enhanced_api_server import start_api_server
except ImportError:
    try:
        from layer3.api_server import start_api_server
    except ImportError:
        from utils.lightweight_components import (
            start_lightweight_api_server as start_api_server,
        )
# 导入安全验证和异常处理模块
from utils.exceptions import (
    DAPException,
    DataIngestionError,
    ProcessingError,
    StorageError,
    ValidationError,
    SecurityError,
)
from utils.validators import ProcessingRequest, FileValidator, SQLQueryValidator
from utils.connection_pool import get_connection_pool, close_all_pools
from utils.security import SecurityManager
from utils.lightweight_components import (
    LightweightAIAgentBridge,
    LightweightAuditRulesEngine,
    LightweightDataIngestor,
    LightweightDimensionOrganizer,
    LightweightOutputFormatter,
    LightweightStorageManager,
    LightweightThirdPartyIntegrator,
    LightweightCloudServiceConnector,
    start_lightweight_api_server,
)


def _env_flag(name: str, default: str = "1") -> bool:
    value = os.environ.get(name, default)
    if value is None:
        return True
    return value.lower() not in {"0", "false", "no", "off"}


PREFER_LIGHTWEIGHT_COMPONENTS = _env_flag("DAP_PREFER_LIGHTWEIGHT", "1")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("dap.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class EnhancedDAPEngine:
    """
    DAP增强版主引擎 - 基于五层架构的智能审计数据处理系统
    核心设计理念：
    - 第一性原理：从审计本质需求出发
    - KISS原则：一键操作，极简交互
    - SOLID原则：模块化，可扩展架构
    - AI增强：自学习，持续改进
    """

    def __init__(self, db_path: str = "data/dap_data.db", export_dir: str = "exports"):
        self.db_path = os.path.abspath(db_path)
        self.export_dir = os.path.abspath(export_dir)
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            os.makedirs(self.export_dir, exist_ok=True)
            os.makedirs("logs", exist_ok=True)
            os.makedirs("config", exist_ok=True)
        except Exception as exc:
            logger.error(f"Failed to prepare runtime directories: {exc}")
            raise
        self.processing = False
        self.current_step = ""
        self.progress = 0
        self.last_result = None
        self.api_server_thread = None
        self.api_server_last_error = None
        self.security_manager = SecurityManager()
        self.connection_pool = get_connection_pool(self.db_path)
        self.component_fallbacks = set()
        self.prefer_lightweight_components = PREFER_LIGHTWEIGHT_COMPONENTS
        self.config_manager = get_config()
        self.github_backup_manager = None
        self._init_components()
        self._log_component_status()
        logger.info("DAP main engine initialized")

    def _merge_project_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize project-related options from various input shapes."""
        project_spec = options.get("project")
        if project_spec:
            if isinstance(project_spec, str):
                options.setdefault("project_id", project_spec)
            elif isinstance(project_spec, dict):
                options.setdefault("project_id", project_spec.get("id"))
                options.setdefault("project_code", project_spec.get("code"))
                options.setdefault("project_name", project_spec.get("name"))
                client = project_spec.get("client") or project_spec.get("client_name")
                if client:
                    options.setdefault("project_client", client)
                if "create_if_missing" in project_spec:
                    options.setdefault(
                        "project_create_if_missing",
                        bool(project_spec["create_if_missing"]),
                    )
            options.pop("project", None)
        return options

    def _prepare_project_context(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure storage manager is scoped to the requested project."""
        storage_manager = getattr(self, "storage_manager", None)
        default_context = {
            "project_id": options.get("project_id")
            or options.get("project_code")
            or options.get("project_name")
            or "default_project",
            "project_code": options.get("project_code"),
            "project_name": options.get("project_name"),
            "client_name": options.get("project_client"),
        }
        if storage_manager is None:
            return default_context

        default_project_id = getattr(
            storage_manager, "DEFAULT_PROJECT_ID", default_context["project_id"]
        )
        identifiers = [
            options.get("project_id"),
            options.get("project_code"),
            options.get("project_name"),
        ]
        project = None
        for identifier in identifiers:
            if identifier:
                try:
                    project = storage_manager.get_project(identifier)
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning("Project lookup failed (%s): %s", identifier, exc)
                    project = None
                if project:
                    break

        if project:
            storage_manager.set_current_project(project["project_id"])
            options.setdefault("project_id", project["project_id"])
            options.setdefault("project_code", project.get("project_code"))
            options.setdefault("project_name", project.get("project_name"))
            return {
                "project_id": project["project_id"],
                "project_code": project.get("project_code"),
                "project_name": project.get("project_name"),
                "client_name": project.get("client_name"),
            }

        requested_name = options.get("project_name")
        auto_create = options.get("project_create_if_missing", True)
        if requested_name and auto_create:
            project_code = options.get("project_code") or options.get("project_id")
            client_name = options.get("project_client")
            try:
                project_id = storage_manager.create_project(
                    project_name=requested_name,
                    project_code=project_code,
                    client_name=client_name,
                )
                storage_manager.set_current_project(project_id)
                options["project_id"] = project_id
                if project_code:
                    options.setdefault("project_code", project_code)
                options.setdefault("project_name", requested_name)
                created = storage_manager.get_project(project_id) or {}
                logger.info("Created project %s (%s)", requested_name, project_id)
                return {
                    "project_id": project_id,
                    "project_code": created.get("project_code", project_code),
                    "project_name": created.get("project_name", requested_name),
                    "client_name": created.get("client_name", client_name),
                }
            except Exception as exc:
                logger.warning("Auto-create project failed (%s): %s", requested_name, exc)

        try:
            storage_manager.set_current_project(default_project_id)
            default_project = storage_manager.get_project(default_project_id) or {}
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to fallback to default project: %s", exc)
            default_project = {}

        return {
            "project_id": default_project.get("project_id", default_project_id),
            "project_code": default_project.get("project_code", default_project_id),
            "project_name": default_project.get("project_name", "默认项目"),
            "client_name": default_project.get("client_name"),
        }

    def _record_fallback(self, name: str) -> None:
        """Track components that required lightweight fallbacks."""
        self.component_fallbacks.add(name)

    def _safe_init_component(
        self,
        attribute: str,
        factory: Optional[Callable[[], Any]] = None,
        fallback_factory: Optional[Callable[[], Any]] = None,
        critical: bool = True,
    ):
        """
        Initialize a component with optional fallback handling.
        Args:
            attribute: Attribute name on the engine instance.
            factory: Callable returning the primary implementation.
            fallback_factory: Callable returning a lightweight implementation.
            critical: When True, re-raises errors if no implementation available.
        """
        component = None
        if factory is not None:
            try:
                component = factory()
            except Exception as exc:
                logger.warning("%s initialization failed: %s", attribute, exc)
        if component is None and fallback_factory is not None:
            try:
                generated = (
                    fallback_factory()
                    if callable(fallback_factory)
                    else fallback_factory
                )
                component = generated
                if component is not None:
                    self._record_fallback(attribute)
                    logger.info(
                        "%s fallback activated: %s",
                        attribute,
                        component.__class__.__name__,
                    )
            except Exception as exc:
                logger.error("%s fallback initialization failed: %s", attribute, exc)
                component = None
        if component is None and critical:
            raise RuntimeError(f"{attribute} component unavailable")
        setattr(self, attribute, component)
        return component

    def _pre_change_backup(self, reason: str) -> None:
        """Run a GitHub backup before mutating operations."""
        manager = getattr(self, "github_backup_manager", None)
        if manager is None:
            return
        try:
            manager.run_backup(triggered_by=f"pre-{reason}")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("预备 GitHub 备份失败(%s): %s", reason, exc)

    def _log_component_status(self) -> None:
        """Emit a summary of component initialisation status."""
        if self.component_fallbacks:
            logger.info(
                "Components using lightweight fallbacks: %s",
                ", ".join(sorted(self.component_fallbacks)),
            )
        else:
            logger.info("All components initialised with primary implementations")

    def _ensure_component(self, attribute: str, factory: Callable[[], Any]):
        """
        Lazily create a component when first requested outside __init__.

        Records the fallback usage if the factory is invoked.
        """
        component = getattr(self, attribute, None)
        if component is not None:
            return component

        try:
            component = factory()
        except Exception as exc:
            logger.error("%s runtime initialisation failed: %s", attribute, exc)
            component = None

        if component is not None:
            setattr(self, attribute, component)
            self._record_fallback(attribute)

        return component

    def _replace_with_fallback(self, attribute: str, factory: Callable[[], Any]):
        """Force replace a component with a lightweight fallback implementation."""
        try:
            component = factory()
        except Exception as exc:
            logger.error("%s fallback creation failed: %s", attribute, exc)
            return getattr(self, attribute, None)

        setattr(self, attribute, component)
        self._record_fallback(attribute)
        return component

    def _collect_warnings(self, *sources: Any) -> List[str]:
        """Aggregate warning messages coming from components and fallbacks."""

        warnings: List[str] = []

        def _add(item: Any) -> None:
            if not item:
                return
            if isinstance(item, str):
                if item not in warnings:
                    warnings.append(item)
                return
            if isinstance(item, dict):
                _add(item.get("warnings"))
                return
            try:
                for entry in item:
                    _add(entry)
            except TypeError:
                _add(str(item))

        for source in sources:
            _add(source)

        for name in sorted(self.component_fallbacks):
            message = f"{name} fallback active"
            if message not in warnings:
                warnings.append(message)

        return warnings

    def _init_components(self) -> None:
        """Initialize layered components with graceful fallbacks."""
        try:
            # Layer 1 components
            data_ingestor_factory = (
                None
                if self.prefer_lightweight_components
                else lambda: EnhancedDataIngestor()
            )
            self._safe_init_component(
                "data_ingestor",
                data_ingestor_factory,
                fallback_factory=LightweightDataIngestor,
            )
            self._safe_init_component("schema_inferrer", lambda: AISchemaInferrer())
            self._safe_init_component(
                "data_scrubber", lambda: IntelligentDataScrubber()
            )
            storage_manager_factory = (
                None
                if self.prefer_lightweight_components
                else lambda: HybridStorageManager(self.db_path)
            )
            self._safe_init_component(
                "storage_manager",
                storage_manager_factory,
                fallback_factory=lambda: LightweightStorageManager(self.db_path),
            )
            # Layer 2 orchestration
            storage_optimizer_factory = (
                None
                if self.prefer_lightweight_components
                else lambda: StorageOptimizer({"db_path": self.db_path})
            )
            self._safe_init_component(
                "storage_optimizer",
                storage_optimizer_factory,
                critical=False,
            )
            lineage_factory = (
                None
                if self.prefer_lightweight_components
                else lambda: DataLineageTracker({"db_path": self.db_path})
            )
            self._safe_init_component(
                "data_lineage_tracker",
                lineage_factory,
                critical=False,
            )
            version_factory = (
                None
                if self.prefer_lightweight_components
                else lambda: VersionController({"db_path": self.db_path})
            )
            self._safe_init_component(
                "version_controller",
                version_factory,
                critical=False,
            )
            performance_factory = (
                None
                if self.prefer_lightweight_components
                else lambda: PerformanceOptimizer({"db_path": self.db_path})
            )
            self._safe_init_component(
                "performance_optimizer",
                performance_factory,
                critical=False,
            )
            audit_rules_factory = (
                None
                if self.prefer_lightweight_components
                else (lambda: AuditRulesEngine(self.db_path))
                if AuditRulesEngine
                else None
            )
            self._safe_init_component(
                "audit_rules_engine",
                audit_rules_factory,
                fallback_factory=LightweightAuditRulesEngine,
                critical=False,
            )
            dimension_factory = (
                None
                if self.prefer_lightweight_components
                else (lambda: DimensionOrganizer(self.db_path))
                if DimensionOrganizer
                else None
            )
            self._safe_init_component(
                "dimension_organizer",
                dimension_factory,
                fallback_factory=LightweightDimensionOrganizer,
                critical=False,
            )
            # Layer 3 intelligence
            ai_config = {"db_path": self.db_path}
            self._safe_init_component(
                "ai_audit_rules_engine",
                lambda: AIAuditRulesEngine(ai_config),
                critical=False,
            )
            self._safe_init_component(
                "adaptive_account_mapper",
                lambda: AdaptiveAccountMapper(ai_config),
                critical=False,
            )
            self._safe_init_component(
                "anomaly_detector",
                lambda: AnomalyDetector(ai_config),
                critical=False,
            )
            self._safe_init_component(
                "audit_knowledge_base",
                lambda: AuditKnowledgeBase(ai_config),
                critical=False,
            )
            # Layer 4 reporting/export
            output_formatter_factory = (
                None
                if self.prefer_lightweight_components
                else lambda: MultiFormatExporter({"export_path": self.export_dir})
            )
            self._safe_init_component(
                "output_formatter",
                output_formatter_factory,
                fallback_factory=lambda: LightweightOutputFormatter(self.export_dir),
                critical=False,
            )
            # Layer 5 integrations
            agent_bridge_factory = (
                None if self.prefer_lightweight_components else lambda: AIAgentBridge()
            )
            self._safe_init_component(
                "agent_bridge",
                agent_bridge_factory,
                fallback_factory=LightweightAIAgentBridge,
                critical=False,
            )

            # GitHub backup manager (Layer 5 external service)
            backup_config = getattr(self.config_manager, "github_backup", None)
            if GitHubBackupManager and backup_config:
                if backup_config.enabled:
                    try:
                        self.github_backup_manager = GitHubBackupManager(backup_config)
                        self.github_backup_manager.start()
                        try:
                            self.github_backup_manager.run_backup(
                                triggered_by="startup"
                            )
                        except Exception as exc:  # pragma: no cover - defensive
                            logger.warning(
                                "GitHub startup backup failed: %s",
                                exc,
                            )
                    except Exception as exc:
                        self.github_backup_manager = None
                        logger.warning(
                            "GitHub backup manager initialization failed: %s", exc
                        )
                else:
                    logger.info("GitHub backup manager disabled in configuration")
            elif GitHubBackupManager is None:
                logger.debug("GitHubBackupManager component not available.")
        except Exception as exc:
            logger.error(f"Component initialization failed: {exc}")
            raise

    def process(
        self, data_source_path: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """一键处理主流程"""
        if self.processing:
            return {
                "success": False,
                "error": "系统正在处理其他任务，请稍后再试",
                "error_code": "SYSTEM_BUSY",
            }

        self.processing = True
        self.progress = 0
        start_time = datetime.now()

        project_context: Optional[Dict[str, Any]] = None
        try:
            logger.info("🚀 DAP 数据处理启动...")
            self.current_step = "正在启动"
            self._pre_change_backup("process")

            try:
                request = ProcessingRequest(
                    data_source_path=data_source_path, options=options or {}
                )
                validated_path = request.data_source_path
                validated_options = request.options
            except ValidationError as exc:
                error_msg = f"输入验证失败: {exc}"
                logger.error(error_msg)
                result = {
                    "success": False,
                    "error": error_msg,
                    "error_code": exc.error_code,
                    "current_step": self.current_step,
                    "progress": self.progress,
                    "details": getattr(exc, "details", {}),
                    "message": "输入验证失败，请检查路径或选项配置",
                }
                warnings = self._collect_warnings()
                if warnings:
                    result["warnings"] = warnings
                self.last_result = result
                return result

            validated_options.setdefault("start_api_server", True)
            validated_options.setdefault("auto_ai_analysis", False)
            self._merge_project_options(validated_options)
            project_context = self._prepare_project_context(validated_options)

            # 第一层：数据接入与清洗
            logger.info("📥 第一层：数据接入与清洗...")
            self.current_step = "数据接入"
            self.progress = 10

            try:
                raw_data = self.data_ingestor.ingest(validated_path)
            except DataIngestionError:
                raise
            except Exception as exc:
                raise DataIngestionError(f"数据接入失败: {exc}", file_path=validated_path)

            if not raw_data:
                raise DataIngestionError("没有获取到有效数据", file_path=validated_path)

            logger.info("✅ 数据接入完成，开始模式推断")
            self.progress = 25
            self.current_step = "模式推断"
            schema = self.schema_inferrer.infer_schema(raw_data)

            logger.info("✅ 数据模式推断完成，开始数据清洗")
            self.progress = 40
            self.current_step = "数据清洗"
            cleaned_data = self.data_scrubber.clean_data(raw_data, schema)

            logger.info("✅ 数据清洗完成，开始数据存储")
            self.progress = 55
            self.current_step = "数据存储"
            try:
                stored = self.storage_manager.store_cleaned_data(cleaned_data, schema)
            except StorageError:
                raise
            except Exception as exc:
                raise StorageError(f"数据存储失败: {exc}")

            if not stored:
                raise StorageError("数据存储失败")

            self.progress = 70

            # 第二层：规则与多维组织
            logger.info("🧠 第二层：智能分类与规则...")
            self.current_step = "智能分类"

            audit_engine = getattr(self, "audit_rules_engine", None)
            if audit_engine is None:
                audit_engine = self._ensure_component(
                    "audit_rules_engine", LightweightAuditRulesEngine
                )

            if audit_engine is None:
                rules_stats = {
                    "successful_rules": 0,
                    "failed_rules": 0,
                    "warnings": ["AUDIT_RULES_ENGINE_UNAVAILABLE"],
                }
            else:
                try:
                    rules_stats = audit_engine.apply_all_rules()
                except Exception as exc:
                    logger.warning("Audit rules execution failed: %s", exc)
                    fallback_engine = self._replace_with_fallback(
                        "audit_rules_engine", LightweightAuditRulesEngine
                    )
                    if fallback_engine is None:
                        rules_stats = {
                            "successful_rules": 0,
                            "failed_rules": 0,
                            "warnings": [f"AUDIT_RULES_ERROR: {exc}"],
                        }
                    else:
                        try:
                            rules_stats = fallback_engine.apply_all_rules()
                        except Exception as fallback_exc:
                            logger.error(
                                "Fallback audit rules engine failed: %s", fallback_exc
                            )
                            rules_stats = {
                                "successful_rules": 0,
                                "failed_rules": 0,
                                "warnings": [
                                    f"AUDIT_RULES_ERROR: {exc}",
                                    f"AUDIT_RULES_FALLBACK_ERROR: {fallback_exc}",
                                ],
                            }

            logger.info(f"✅ 审计规则应用完成，成功: {rules_stats['successful_rules']}")
            self.progress = 80

            self.current_step = "多维度组织"
            dimension_organizer = getattr(self, "dimension_organizer", None)
            if dimension_organizer is None:
                dimension_organizer = self._ensure_component(
                    "dimension_organizer", LightweightDimensionOrganizer
                )

            if dimension_organizer is None:
                org_result = {
                    "success": False,
                    "stats": {"views_created": 0},
                    "warnings": ["DIMENSION_ORGANIZER_UNAVAILABLE"],
                }
            else:
                try:
                    org_result = dimension_organizer.organize_by_all_dimensions()
                except Exception as exc:
                    logger.warning("Dimension organization failed: %s", exc)
                    fallback_organizer = self._replace_with_fallback(
                        "dimension_organizer", LightweightDimensionOrganizer
                    )
                    if fallback_organizer is None:
                        org_result = {
                            "success": False,
                            "stats": {"views_created": 0},
                            "warnings": [f"DIMENSION_ORGANIZER_ERROR: {exc}"],
                        }
                    else:
                        try:
                            org_result = fallback_organizer.organize_by_all_dimensions()
                        except Exception as fallback_exc:
                            logger.error(
                                "Fallback dimension organizer failed: %s", fallback_exc
                            )
                            org_result = {
                                "success": False,
                                "stats": {"views_created": 0},
                                "warnings": [
                                    f"DIMENSION_ORGANIZER_ERROR: {exc}",
                                    f"DIMENSION_ORGANIZER_FALLBACK_ERROR: {fallback_exc}",
                                ],
                            }

            logger.info(f"✅ 多维度数据组织完成，创建视图: {org_result['stats']['views_created']}")
            self.progress = 90

            # 第三层：启动服务
            logger.info("🤖 第三层：智能分析准备...")
            self.current_step = "启动服务"
            if validated_options.get("start_api_server", True):
                if self._start_api_server_background():
                    logger.info("✅ API服务启动完成")
                else:
                    logger.warning("⚠️ API服务启动未确认，请检查日志")

            self.progress = 100
            self.current_step = "处理完成"

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            warnings = self._collect_warnings(rules_stats, org_result)
            result = {
                "success": True,
                "data_path": self.db_path,
                "api_url": "http://localhost:8000",
                "processing_time": processing_time,
                "statistics": {
                    "tables_processed": len(cleaned_data),
                    "rules_applied": rules_stats.get("successful_rules", 0),
                    "views_created": org_result.get("stats", {}).get(
                        "views_created", 0
                    ),
                    "total_records": sum(len(df) for df in cleaned_data.values()),
                },
                "message": "DAP数据处理智能体已就绪，可通过API或直接查询SQLite数据库进行分析",
            }
            if project_context:
                result["project"] = project_context
            if warnings:
                result["warnings"] = warnings

            self.last_result = result
            logger.info("🎉 DAP 数据处理全部完成！")
            return result

        except DAPException as exc:
            error_msg = f"处理失败: {exc.message}"
            logger.error(
                error_msg,
                extra={
                    "error_code": exc.error_code,
                    "details": exc.details,
                    "stage": getattr(exc, "stage", None),
                },
            )
            result = {
                "success": False,
                "error": error_msg,
                "error_code": exc.error_code,
                "current_step": self.current_step,
                "progress": self.progress,
                "details": exc.details,
                "message": "处理失败，请查看错误信息和日志",
            }
            if project_context:
                result["project"] = project_context
            warnings = self._collect_warnings()
            if warnings:
                result["warnings"] = warnings
            self.last_result = result
            return result

        except Exception as exc:
            error_msg = f"未知错误: {exc}"
            logger.error(error_msg, exc_info=True)
            result = {
                "success": False,
                "error": error_msg,
                "error_code": "UNKNOWN_ERROR",
                "current_step": self.current_step,
                "progress": self.progress,
                "message": "处理失败，发生未知错误",
            }
            if project_context:
                result["project"] = project_context
            warnings = self._collect_warnings()
            if warnings:
                result["warnings"] = warnings
            self.last_result = result
            return result

        finally:
            self.processing = False

    def _start_api_server_background(self) -> bool:
        """在后台启动API服务"""
        if self.api_server_thread and self.api_server_thread.is_alive():
            logger.info("API服务器已在运行")
            return True

        self.api_server_last_error = None

        def run_server():
            start_kwargs = {
                "host": "127.0.0.1",
                "port": 8000,
                "reload": False,
                "log_level": "warning",
            }
            try:
                result = self._invoke_api_server(start_kwargs)
                if isinstance(result, dict) and result.get("warnings"):
                    logger.warning(
                        "API server fallback active: %s", ", ".join(result["warnings"])
                    )
            except Exception as exc:
                self.api_server_last_error = exc
                logger.error("API服务器启动失败: %s", exc, exc_info=True)

        self.api_server_thread = threading.Thread(target=run_server, daemon=True)
        self.api_server_thread.start()

        # 短暂等待以捕获同步启动错误
        time.sleep(1.0)
        if self.api_server_last_error is not None:
            return False

        if not self.api_server_thread.is_alive():
            logger.warning("API服务器线程已结束，可能未成功启动")
            return False

        return True

    def _invoke_api_server(self, start_kwargs: Dict[str, Any]):
        """启动API服务器，自动处理参数兼容性"""
        try:
            return start_api_server(**start_kwargs)
        except TypeError as exc:
            message = str(exc)
            if "unexpected keyword" in message or "got an unexpected keyword" in message:
                logger.warning(
                    "API服务器不支持高级启动参数，降级使用基础参数: %s", message
                )
                minimal_kwargs = {
                    key: start_kwargs[key] for key in ("host", "port") if key in start_kwargs
                }
                return start_api_server(**minimal_kwargs)
            raise

    def get_status(self) -> Dict[str, Any]:
        """获取当前处理状态"""
        return {
            "processing": self.processing,
            "current_step": self.current_step,
            "progress": self.progress,
            "last_result": self.last_result,
            "api_server_running": self.api_server_thread
            and self.api_server_thread.is_alive(),
            "api_server_last_error": (
                str(self.api_server_last_error) if self.api_server_last_error else None
            ),
        }

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            # 获取数据库统计
            tables = self.storage_manager.get_table_list()
            views = self.storage_manager.get_view_list()
            # 获取可用AI客户端
            available_ai_clients = self.agent_bridge.get_available_clients()
            return {
                "system": "DAP - 数据处理审计智能体",
                "version": "1.0.0",
                "database_path": self.db_path,
                "export_directory": self.export_dir,
                "statistics": {
                    "total_tables": len(tables),
                    "total_views": len(views),
                    "available_ai_clients": available_ai_clients,
                },
                "status": "ready" if not self.processing else "processing",
            }
        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {
                "system": "DAP - 数据处理审计智能体",
                "version": "1.0.0",
                "status": "error",
                "error": str(e),
            }

    def export_data(
        self, source: str, format: str, output_path: str = None
    ) -> Dict[str, Any]:
        """导出数据"""
        formatter = getattr(self, "output_formatter", None)
        if formatter is None:
            formatter = self._ensure_component(
                "output_formatter", lambda: LightweightOutputFormatter(self.export_dir)
            )

        if formatter is None:
            result: Dict[str, Any] = {
                "success": False,
                "error": "Output formatter unavailable",
                "error_code": "EXPORT_ERROR",
            }
        else:
            try:
                result = formatter.export_data(source, format, output_path)
            except Exception as exc:
                logger.error(f"数据导出失败: {exc}")
                fallback_formatter = self._replace_with_fallback(
                    "output_formatter",
                    lambda: LightweightOutputFormatter(self.export_dir),
                )
                if fallback_formatter is None:
                    result = {
                        "success": False,
                        "error": str(exc),
                        "error_code": "EXPORT_ERROR",
                    }
                else:
                    result = fallback_formatter.export_data(source, format, output_path)
                    result.setdefault("success", False)
                    result.setdefault("error", str(exc))
                    result.setdefault("error_code", "EXPORT_ERROR")

        if not isinstance(result, dict):
            result = {
                "success": False,
                "error": "Invalid export response",
                "error_code": "EXPORT_ERROR",
            }

        warnings = self._collect_warnings(result)
        if warnings:
            result["warnings"] = warnings

        if not result.get("success"):
            result.setdefault("error_code", "EXPORT_ERROR")

        return result

    def trigger_github_backup(self, reason: str = "manual") -> Dict[str, Any]:
        """手动触发 GitHub 自动备份"""
        manager = getattr(self, "github_backup_manager", None)
        if manager is None:
            message = "GitHub backup manager is not available"
            logger.warning(message)
            return {
                "success": False,
                "error": message,
                "error_code": "GITHUB_BACKUP_UNAVAILABLE",
            }

        success = manager.run_backup(triggered_by=reason)
        status = manager.get_status()
        if status.get("success") is None:
            status["success"] = success
        else:
            status["success"] = bool(status.get("success"))
        status["trigger"] = reason
        return status

    def generate_audit_report(
        self, company_name: str, period: str, format: str = "html"
    ) -> Dict[str, Any]:
        """生成审计报告"""
        formatter = getattr(self, "output_formatter", None)
        if formatter is None:
            formatter = self._ensure_component(
                "output_formatter", lambda: LightweightOutputFormatter(self.export_dir)
            )

        if formatter is None:
            result: Dict[str, Any] = {
                "success": False,
                "error": "Output formatter unavailable",
                "error_code": "REPORT_ERROR",
            }
        else:
            try:
                result = formatter.generate_audit_report(company_name, period, format)
            except Exception as exc:
                logger.error(f"审计报告生成失败: {exc}")
                fallback_formatter = self._replace_with_fallback(
                    "output_formatter",
                    lambda: LightweightOutputFormatter(self.export_dir),
                )
                if fallback_formatter is None:
                    result = {
                        "success": False,
                        "error": str(exc),
                        "error_code": "REPORT_ERROR",
                    }
                else:
                    result = fallback_formatter.generate_audit_report(
                        company_name, period, format
                    )
                    result.setdefault("success", False)
                    result.setdefault("error", str(exc))
                    result.setdefault("error_code", "REPORT_ERROR")

        if not isinstance(result, dict):
            result = {
                "success": False,
                "error": "Invalid report response",
                "error_code": "REPORT_ERROR",
            }

        warnings = self._collect_warnings(result)
        if warnings:
            result["warnings"] = warnings

        if not result.get("success"):
            result.setdefault("error_code", "REPORT_ERROR")

        return result

    def analyze_with_ai(self, prompt: str, data_source: str = None) -> Dict[str, Any]:
        """使用AI进行数据分析"""
        try:
            data = None
            if data_source:
                try:
                    safe_data_source = SQLQueryValidator.validate_table_name(
                        data_source
                    )
                except SecurityError as e:
                    raise SecurityError(
                        f"数据源名称安全验证失败: {e}", security_type="sql_injection"
                    )

                valid_sources = self._get_valid_data_sources()
                if safe_data_source not in valid_sources:
                    raise ValidationError(f"无效的数据源: {data_source}")

                import pandas as pd

                with self.connection_pool.get_connection() as db_conn:
                    with db_conn:
                        query = f"SELECT * FROM [{safe_data_source}] LIMIT 1000"
                        data = pd.read_sql_query(query, db_conn)

            agent_bridge = getattr(self, "agent_bridge", None)
            if agent_bridge is None:
                agent_bridge = self._ensure_component(
                    "agent_bridge", LightweightAIAgentBridge
                )

            if agent_bridge is None:
                response: Dict[str, Any] = {
                    "success": False,
                    "error": "AI agent bridge unavailable",
                    "error_code": "AI_ANALYSIS_ERROR",
                }
            else:
                try:
                    response = agent_bridge.call_ai_analysis(prompt, data)
                except Exception as exc:
                    logger.warning("Primary agent bridge failed: %s", exc)
                    fallback_bridge = self._replace_with_fallback(
                        "agent_bridge", LightweightAIAgentBridge
                    )
                    if fallback_bridge is None:
                        response = {
                            "success": False,
                            "error": str(exc),
                            "error_code": "AI_ANALYSIS_ERROR",
                        }
                    else:
                        response = fallback_bridge.call_ai_analysis(prompt, data)
                        response.setdefault("success", True)
                        response.setdefault(
                            "result", f"Fallback analysis for prompt: {prompt}"
                        )
                        response.setdefault("error_code", "AI_ANALYSIS_FALLBACK")

            if not isinstance(response, dict):
                response = {
                    "success": False,
                    "error": "Invalid response from agent bridge",
                    "error_code": "AI_ANALYSIS_ERROR",
                }

            warnings = self._collect_warnings(response)
            if warnings:
                response["warnings"] = warnings

            if not response.get("success") and "error_code" not in response:
                response["error_code"] = "AI_ANALYSIS_ERROR"

            return response

        except (SecurityError, ValidationError) as e:
            logger.error(f"AI分析安全验证失败: {e}")
            response = {
                "success": False,
                "error": str(e),
                "error_code": e.error_code
                if hasattr(e, "error_code")
                else "VALIDATION_ERROR",
            }
            warnings = self._collect_warnings(response)
            if warnings:
                response["warnings"] = warnings
            return response

        except Exception as e:
            logger.error(f"AI分析失败: {e}", exc_info=True)
            response = {
                "success": False,
                "error": str(e),
                "error_code": "AI_ANALYSIS_ERROR",
            }
            warnings = self._collect_warnings(response)
            if warnings:
                response["warnings"] = warnings
            return response

    def _get_valid_data_sources(self) -> list:
        """获取有效的数据源列表"""
        try:
            tables = self.storage_manager.get_table_list()
            views = self.storage_manager.get_view_list()
            imported_tables = self.output_formatter.get_imported_tables()
            sources = [f"raw_clean_{table['table_name']}" for table in tables]
            sources.extend([view["view_name"] for view in views])
            sources.extend([table["table_name"] for table in imported_tables])
            return sources
        except Exception:
            return []

    def import_data_file(
        self, file_path: str, table_name: str = None, options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """导入数据文件到系统"""
        formatter = getattr(self, "output_formatter", None)
        if formatter is None:
            formatter = self._ensure_component(
                "output_formatter", lambda: LightweightOutputFormatter(self.export_dir)
            )

        if formatter is None:
            result: Dict[str, Any] = {
                "success": False,
                "error": "Output formatter unavailable",
                "error_code": "IMPORT_ERROR",
            }
        else:
            try:
                self._pre_change_backup("import_data_file")
                result = formatter.import_data_from_file(file_path, table_name, options)
                if isinstance(result, dict) and result.get("success"):
                    logger.info(f"数据文件导入成功: {file_path} -> {result.get('table_name')}")
            except Exception as exc:
                logger.error(f"数据文件导入失败: {exc}")
                fallback_formatter = self._replace_with_fallback(
                    "output_formatter",
                    lambda: LightweightOutputFormatter(self.export_dir),
                )
                if fallback_formatter is None:
                    result = {
                        "success": False,
                        "error": str(exc),
                        "error_code": "IMPORT_ERROR",
                    }
                else:
                    result = fallback_formatter.import_data_from_file(
                        file_path, table_name, options
                    )
                    result.setdefault("success", False)
                    result.setdefault("error", str(exc))
                    result.setdefault("error_code", "IMPORT_ERROR")

        if not isinstance(result, dict):
            result = {
                "success": False,
                "error": "Invalid import response",
                "error_code": "IMPORT_ERROR",
            }

        warnings = self._collect_warnings(result)
        if warnings:
            result["warnings"] = warnings

        if not result.get("success"):
            result.setdefault("error_code", "IMPORT_ERROR")

        return result

    def get_import_history(self) -> List[Dict[str, Any]]:
        """获取数据导入历史"""
        formatter = getattr(self, "output_formatter", None)
        if formatter is None:
            formatter = self._ensure_component(
                "output_formatter", lambda: LightweightOutputFormatter(self.export_dir)
            )

        if formatter is None:
            return []

        try:
            return formatter.get_import_history()
        except Exception as exc:
            logger.error(f"获取导入历史失败: {exc}")
            fallback_formatter = self._replace_with_fallback(
                "output_formatter", lambda: LightweightOutputFormatter(self.export_dir)
            )
            if fallback_formatter is None:
                return []
            try:
                return fallback_formatter.get_import_history()
            except Exception as fallback_exc:
                logger.error(
                    f"Fallback import history retrieval failed: {fallback_exc}"
                )
                return []

    def get_imported_tables(self) -> List[Dict[str, Any]]:
        """获取已导入的表列表"""
        formatter = getattr(self, "output_formatter", None)
        if formatter is None:
            formatter = self._ensure_component(
                "output_formatter", lambda: LightweightOutputFormatter(self.export_dir)
            )

        if formatter is None:
            return []

        try:
            return formatter.get_imported_tables()
        except Exception as exc:
            logger.error(f"获取导入表列表失败: {exc}")
            fallback_formatter = self._replace_with_fallback(
                "output_formatter", lambda: LightweightOutputFormatter(self.export_dir)
            )
            if fallback_formatter is None:
                return []
            try:
                return fallback_formatter.get_imported_tables()
            except Exception as fallback_exc:
                logger.error(
                    f"Fallback imported tables retrieval failed: {fallback_exc}"
                )
                return []

    def close(self):
        """关闭系统"""
        try:
            # 关闭连接池
            if hasattr(self, "connection_pool"):
                self.connection_pool.close_all()
            # 关闭各层组件
            components = [
                ("storage_manager", "存储管理器"),
                ("audit_rules_engine", "审计规则引擎"),
                ("dimension_organizer", "维度组织器"),
                ("output_formatter", "输出格式化器"),
                ("agent_bridge", "AI代理桥接"),
                ("github_backup_manager", "GitHub自动备份管理器"),
            ]
            for component_name, display_name in components:
                if hasattr(self, component_name):
                    try:
                        component = getattr(self, component_name)
                        if hasattr(component, "close"):
                            component.close()
                        elif hasattr(component, "stop"):
                            component.stop()
                        logger.info(f"{display_name}已关闭")
                    except Exception as e:
                        logger.error(f"关闭{display_name}时出错: {e}")
            # 关闭全局连接池
            from utils.connection_pool import close_all_pools

            close_all_pools()
            logger.info("DAP主引擎已安全关闭")
        except Exception as e:
            logger.error(f"关闭系统时出错: {e}")
            # 确保关键资源被释放
            try:
                from utils.connection_pool import close_all_pools

                close_all_pools()
            except:
                pass


class DAPEngine(EnhancedDAPEngine):
    """
    Backwards-compatible alias maintained for legacy integrations and tests.
    """

    pass


# 全局引擎实例
dap_engine = None


def get_dap_engine() -> EnhancedDAPEngine:
    """获取DAP引擎实例（单例模式）"""
    global dap_engine
    if dap_engine is None:
        dap_engine = EnhancedDAPEngine()
    return dap_engine


if __name__ == "__main__":
    # For testing purposes, you can import and use the DAPEngine class
    # Example: engine = DAPEngine(); result = engine.process('your_file.xlsx')
    pass
