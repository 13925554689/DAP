"""
DAP v2.0 Backend - Main Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Application metadata
APP_NAME = "DAP Audit System v2.0"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = """
DAP (Data Processing & Auditing Intelligence Agent) v2.0
智能审计数据平台 - 审计底稿与合并报表系统

核心功能:
- 项目管理系统 (IPO/年报/财务/税务审计)
- 审计底稿编制与管理
- 合并报表与抵消引擎
- 三级复核流程
- AI辅助审计分析
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    print(f"[STARTUP] {APP_NAME} v{APP_VERSION} starting...")
    print("[STARTUP] Initializing database connections...")
    print("[STARTUP] Application ready!")

    yield

    # Shutdown
    print("[SHUTDOWN] Shutting down...")
    print("[SHUTDOWN] Cleanup completed!")


# Create FastAPI application
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check Endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app_name": APP_NAME,
        "version": APP_VERSION,
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {APP_NAME}",
        "version": APP_VERSION,
        "docs": "/api/docs",
    }


# API Routes (will be added incrementally)
# from api.routes import project, workpaper, consolidation, review


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
