"""
DAP v2.0 - Configuration Management
Application settings and environment variables
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "DAP Audit System v2.0"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./dap_v2.db"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)  # 生成默认密钥，生产环境必须覆盖
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password Policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:3000"
    ]

    # Email (for password reset)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: Optional[str] = "DAP Audit System"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [
        ".xlsx", ".xls", ".csv", ".pdf", ".doc", ".docx"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Helper functions
def get_database_url() -> str:
    """Get database URL"""
    return settings.DATABASE_URL


def is_production() -> bool:
    """Check if running in production"""
    return settings.ENVIRONMENT == "production"


def is_development() -> bool:
    """Check if running in development"""
    return settings.ENVIRONMENT == "development"
