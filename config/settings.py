#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP 系统配置管理模块
集中管理所有配置项，提供类型检查和验证
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """数据库配置"""

    path: str = "data/dap_data.db"
    connection_pool_size: int = 10
    enable_wal_mode: bool = True
    cache_size: int = 10000
    foreign_keys: bool = True
    timeout: float = 30.0

    def __post_init__(self):
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.path), exist_ok=True)


@dataclass
class DataIngestionConfig:
    """数据接入配置"""

    max_files_per_batch: int = 100
    supported_db_extensions: List[str] = None
    parallel_processing: bool = True
    max_workers: int = 4
    chunk_size: int = 10000
    encoding_detection_sample_size: int = 1000

    def __post_init__(self):
        if self.supported_db_extensions is None:
            self.supported_db_extensions = [".db", ".sqlite", ".mdb", ".accdb", ".ais"]


@dataclass
class ProcessingConfig:
    """数据处理配置"""

    memory_threshold: float = 0.8  # 内存使用阈值
    enable_caching: bool = True
    cache_ttl: int = 3600  # 缓存过期时间（秒）
    max_cache_size: int = 1000  # 最大缓存条目数
    temp_dir: str = "temp"

    def __post_init__(self):
        if self.temp_dir and not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)


@dataclass
class SecurityConfig:
    """安全配置"""

    enable_path_validation: bool = True
    allowed_base_paths: List[str] = None
    max_file_size: int = 1024 * 1024 * 1024  # 1GB
    enable_sql_injection_protection: bool = True
    log_security_events: bool = True

    def __post_init__(self):
        if self.allowed_base_paths is None:
            # 默认允许的基础路径
            current_dir = os.path.abspath(os.getcwd())
            self.allowed_base_paths = [
                current_dir,
                os.path.join(current_dir, "data"),
                os.path.join(current_dir, "temp"),
                os.path.join(current_dir, "exports"),
            ]


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/dap.log"
    max_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console: bool = True

    def __post_init__(self):
        # 确保日志目录存在
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)


@dataclass
class RuntimeConfig:
    """运行时配置"""

    prefer_lightweight_components: bool = True

    @classmethod
    def from_env(cls):
        value = os.getenv("DAP_PREFER_LIGHTWEIGHT", "1")
        prefer = str(value).lower() not in {"0", "false", "no", "off"}
        return cls(prefer_lightweight_components=prefer)


@dataclass
class APIConfig:
    """API配置"""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    max_request_size: int = 100 * 1024 * 1024  # 100MB
    cors_enabled: bool = True
    cors_origins: List[str] = None

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["*"]


@dataclass
class GitHubBackupConfig:
    """GitHub 自动备份配置"""

    enabled: bool = False
    repository: Optional[str] = None  # e.g. "owner/repo"
    branch: str = "main"
    token_env_var: str = "DAP_GITHUB_TOKEN"
    backup_paths: List[str] = field(default_factory=lambda: ["data", "exports"])
    remote_path: str = "backups"
    backup_temp_dir: str = "data/github_backups"
    interval_minutes: int = 120
    commit_message_template: str = "Automated backup: {timestamp}"
    retention_count: int = 5
    author_name: str = "DAP Backup Bot"
    author_email: str = "backup-bot@example.com"
    verify_ssl: bool = True

    def __post_init__(self):
        temp_dir = Path(self.backup_temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        if not self.backup_paths:
            self.backup_paths = ["data", "exports"]


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._load_config()

    def _load_config(self):
        """加载配置"""
        # 从环境变量和配置文件加载
        self.database = self._load_database_config()
        self.data_ingestion = self._load_data_ingestion_config()
        self.processing = self._load_processing_config()
        self.security = self._load_security_config()
        self.logging = self._load_logging_config()
        self.api = self._load_api_config()
        self.runtime = self._load_runtime_config()
        self.github_backup = self._load_github_backup_config()

        logger.info("配置加载完成")

    def _load_database_config(self) -> DatabaseConfig:
        """加载数据库配置"""
        return DatabaseConfig(
            path=os.getenv("DAP_DB_PATH", "data/dap_data.db"),
            connection_pool_size=int(os.getenv("DAP_DB_POOL_SIZE", "10")),
            enable_wal_mode=os.getenv("DAP_DB_WAL_MODE", "true").lower() == "true",
            cache_size=int(os.getenv("DAP_DB_CACHE_SIZE", "10000")),
            timeout=float(os.getenv("DAP_DB_TIMEOUT", "30.0")),
        )

    def _load_data_ingestion_config(self) -> DataIngestionConfig:
        """加载数据接入配置"""
        return DataIngestionConfig(
            max_files_per_batch=int(os.getenv("DAP_MAX_FILES_BATCH", "100")),
            parallel_processing=os.getenv("DAP_PARALLEL_PROCESSING", "true").lower()
            == "true",
            max_workers=int(os.getenv("DAP_MAX_WORKERS", "4")),
            chunk_size=int(os.getenv("DAP_CHUNK_SIZE", "10000")),
        )

    def _load_processing_config(self) -> ProcessingConfig:
        """加载处理配置"""
        return ProcessingConfig(
            memory_threshold=float(os.getenv("DAP_MEMORY_THRESHOLD", "0.8")),
            enable_caching=os.getenv("DAP_ENABLE_CACHING", "true").lower() == "true",
            cache_ttl=int(os.getenv("DAP_CACHE_TTL", "3600")),
            temp_dir=os.getenv("DAP_TEMP_DIR", "temp"),
        )

    def _load_security_config(self) -> SecurityConfig:
        """加载安全配置"""
        return SecurityConfig(
            enable_path_validation=os.getenv("DAP_PATH_VALIDATION", "true").lower()
            == "true",
            max_file_size=int(os.getenv("DAP_MAX_FILE_SIZE", str(1024 * 1024 * 1024))),
            enable_sql_injection_protection=os.getenv(
                "DAP_SQL_PROTECTION", "true"
            ).lower()
            == "true",
        )

    def _load_logging_config(self) -> LoggingConfig:
        """加载日志配置"""
        return LoggingConfig(
            level=os.getenv("DAP_LOG_LEVEL", "INFO"),
            file_path=os.getenv("DAP_LOG_FILE", "logs/dap.log"),
            enable_console=os.getenv("DAP_LOG_CONSOLE", "true").lower() == "true",
        )

    def _load_api_config(self) -> APIConfig:
        """加载API配置"""
        return APIConfig(
            host=os.getenv("DAP_API_HOST", "127.0.0.1"),
            port=int(os.getenv("DAP_API_PORT", "8000")),
            debug=os.getenv("DAP_API_DEBUG", "false").lower() == "true",
        )

    def _load_runtime_config(self) -> RuntimeConfig:
        """加载运行时配置"""
        return RuntimeConfig.from_env()

    def _load_github_backup_config(self) -> GitHubBackupConfig:
        """加载GitHub自动备份配置"""
        enabled = os.getenv("DAP_GITHUB_BACKUP_ENABLED", "false").lower() == "true"
        repository = os.getenv("DAP_GITHUB_BACKUP_REPO")
        branch = os.getenv("DAP_GITHUB_BACKUP_BRANCH", "main")
        token_env_var = os.getenv("DAP_GITHUB_BACKUP_TOKEN_ENV", "DAP_GITHUB_TOKEN")
        remote_path = os.getenv("DAP_GITHUB_BACKUP_REMOTE_PATH", "backups").strip("/")
        temp_dir = os.getenv("DAP_GITHUB_BACKUP_TEMP_DIR", "data/github_backups")
        commit_template = os.getenv(
            "DAP_GITHUB_BACKUP_COMMIT_MESSAGE", "Automated backup: {timestamp}"
        )
        author_name = os.getenv("DAP_GITHUB_BACKUP_AUTHOR_NAME", "DAP Backup Bot")
        author_email = os.getenv(
            "DAP_GITHUB_BACKUP_AUTHOR_EMAIL", "backup-bot@example.com"
        )
        interval_minutes = int(os.getenv("DAP_GITHUB_BACKUP_INTERVAL_MINUTES", "120"))
        retention_count = int(os.getenv("DAP_GITHUB_BACKUP_RETENTION", "5"))
        verify_ssl = (
            os.getenv("DAP_GITHUB_BACKUP_VERIFY_SSL", "true").lower() != "false"
        )

        raw_paths = os.getenv("DAP_GITHUB_BACKUP_PATHS", "")
        backup_paths: Optional[List[str]] = None
        if raw_paths:
            normalized = raw_paths.replace(";", ",")
            backup_paths = [
                path.strip() for path in normalized.split(",") if path.strip()
            ]

        config = GitHubBackupConfig(
            enabled=enabled,
            repository=repository,
            branch=branch,
            token_env_var=token_env_var,
            backup_paths=backup_paths or None,
            remote_path=remote_path,
            backup_temp_dir=temp_dir,
            interval_minutes=max(1, interval_minutes),
            commit_message_template=commit_template,
            retention_count=max(1, retention_count),
            author_name=author_name,
            author_email=author_email,
            verify_ssl=verify_ssl,
        )
        return config

    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return {
            "database": self.database.__dict__,
            "data_ingestion": self.data_ingestion.__dict__,
            "processing": self.processing.__dict__,
            "security": self.security.__dict__,
            "logging": self.logging.__dict__,
            "api": self.api.__dict__,
            "runtime": self.runtime.__dict__,
            "github_backup": self.github_backup.__dict__,
        }

    def validate_config(self) -> List[str]:
        """验证配置"""
        errors = []

        # 验证数据库配置
        if not self.database.path:
            errors.append("数据库路径不能为空")

        if self.database.connection_pool_size <= 0:
            errors.append("连接池大小必须大于0")

        # 验证数据接入配置
        if self.data_ingestion.max_files_per_batch <= 0:
            errors.append("批量文件数量必须大于0")

        if self.data_ingestion.max_workers <= 0:
            errors.append("工作线程数必须大于0")

        # 验证安全配置
        if self.security.max_file_size <= 0:
            errors.append("最大文件大小必须大于0")

        # 验证API配置
        if not (1 <= self.api.port <= 65535):
            errors.append("API端口必须在1-65535范围内")

        if self.github_backup.enabled:
            if not self.github_backup.repository:
                errors.append("启用GitHub自动备份时必须配置仓库地址")
            token_available = os.getenv(self.github_backup.token_env_var)
            if not token_available:
                errors.append(
                    f"GitHub自动备份需要在环境变量 {self.github_backup.token_env_var} 中提供访问令牌"
                )

        return errors


# 全局配置实例
config = ConfigManager()


def get_config() -> ConfigManager:
    """获取全局配置实例"""
    return config


def reload_config():
    """重新加载配置"""
    global config
    config = ConfigManager()
    logger.info("配置已重新加载")


if __name__ == "__main__":
    # 测试配置
    cfg = get_config()

    print("=== DAP 配置信息 ===")
    for section, values in cfg.get_all_config().items():
        print(f"\n[{section.upper()}]")
        for key, value in values.items():
            print(f"  {key}: {value}")

    # 验证配置
    errors = cfg.validate_config()
    if errors:
        print(f"\n配置验证错误:")
        for error in errors:
            print(f"  - {error}")
    else:
        print(f"\n配置验证通过")
