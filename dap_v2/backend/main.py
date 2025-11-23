"""
DAP v2.0 Backend - Main Application Entry Point
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import logging
import sys

# 修复中文编码问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from config import settings
from models.database import get_db, init_db
from api import projects, users
from routers import evidence_router

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Application metadata
APP_NAME = settings.APP_NAME
APP_VERSION = settings.APP_VERSION
APP_DESCRIPTION = """
DAP (Data Processing & Auditing Intelligence Agent) v2.0
智能审计数据平台 - 审计底稿与合并报表系统

核心功能:
- 用户认证与权限管理 (JWT + RBAC)
- 项目管理系统 (IPO/年报/财务/税务审计)
- 审计底稿编制与管理
- 合并报表与抵消引擎
- 三级复核流程
- AI辅助审计分析

安全特性:
- JWT Token认证
- 密码强度验证
- 角色级别权限控制
- 完整操作审计追踪
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("=" * 60)
    logger.info(f"{APP_NAME} v{APP_VERSION} starting...")
    logger.info("=" * 60)

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    logger.info("Application ready!")

    yield

    # Shutdown
    logger.info("Shutting down...")
    logger.info("Cleanup completed!")


# Create FastAPI application
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    default_response_class=ORJSONResponse,  # 使用ORJSON支持中文
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check Endpoint
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "app_name": APP_NAME,
            "version": APP_VERSION,
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "app_name": APP_NAME,
            "version": APP_VERSION,
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {APP_NAME}",
        "version": APP_VERSION,
        "docs": "/api/docs",
    }


# API Routes
app.include_router(
    users.router,
    prefix="/api",
    tags=["Users & Authentication"]
)

app.include_router(
    projects.router,
    prefix="/api/projects",
    tags=["Projects"]
)

# Evidence Management API
app.include_router(
    evidence_router,
    prefix="/api",
    tags=["Evidence Management"]
)

# TODO: 添加其他路由
# from api import clients, workpapers, consolidation, review
# app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
# app.include_router(workpapers.router, prefix="/api/workpapers", tags=["Workpapers"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
