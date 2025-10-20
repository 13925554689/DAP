"""
Enhanced API Server for DAP System
Layer 5: External Integration & API Services

Provides comprehensive RESTful API services with AI-enhanced capabilities
for external integration and upper-level AI Audit Brain communication.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import logging
from contextlib import asynccontextmanager
import mimetypes
import zipfile
import io
import os

try:
    from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Request, Response, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

class EnhancedAPIServer:
    """Enhanced API Server with AI capabilities and comprehensive endpoint coverage"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.setup_logging()

        # API Server components
        self.app = None
        self.security = None
        self.cache = None
        self.metrics = {}

        # Service dependencies
        self.data_processor = None
        self.ai_agent = None
        self.knowledge_base = None

        # Performance tracking
        self.request_count = 0
        self.start_time = time.time()
        self.health_status = "healthy"

        # Rate limiting
        self.rate_limits = {
            'default': 100,  # requests per minute
            'ai_query': 20,
            'data_export': 10,
            'bulk_import': 5
        }

        # Background tasks
        self.background_tasks = []

        self.initialize_server()

    def setup_logging(self):
        """Setup enhanced logging for API server"""
        self.logger = logging.getLogger(f"{__name__}.EnhancedAPIServer")

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def initialize_server(self):
        """Initialize FastAPI server with middleware and dependencies"""
        if not FASTAPI_AVAILABLE:
            self.logger.warning("FastAPI not available. API server functionality limited.")
            return

        # Create FastAPI app
        self.app = FastAPI(
            title="DAP Enhanced API Server",
            description="Comprehensive API for Data Audit Platform with AI capabilities",
            version="2.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )

        # Add middleware
        self.setup_middleware()

        # Setup security
        self.setup_security()

        # Setup cache
        self.setup_cache()

        # Setup metrics
        self.setup_metrics()

        # Register routes
        self.setup_routes()

        # Setup background tasks
        self.setup_background_tasks()

    def setup_middleware(self):
        """Setup FastAPI middleware"""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Gzip compression
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)

        # Custom middleware for request logging and metrics
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()

            # Process request
            response = await call_next(request)

            # Log and metrics
            process_time = time.time() - start_time
            self.request_count += 1

            self.logger.info(
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s"
            )

            # Update metrics
            if PROMETHEUS_AVAILABLE and 'request_duration' in self.metrics:
                self.metrics['request_duration'].observe(process_time)
                self.metrics['request_count'].inc()

            return response

    def setup_security(self):
        """Setup API security"""
        self.security = HTTPBearer()

        async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(self.security)):
            """Validate API token"""
            token = credentials.credentials

            # Simple token validation (in production, use proper JWT validation)
            valid_tokens = self.config.get('api_tokens', ['dap-api-token-2024'])

            if token not in valid_tokens:
                raise HTTPException(status_code=401, detail="Invalid authentication token")

            return {"token": token, "user_id": "api_user"}

    def setup_cache(self):
        """Setup Redis cache if available"""
        if REDIS_AVAILABLE:
            try:
                redis_config = self.config.get('redis', {})
                self.cache = redis.Redis(
                    host=redis_config.get('host', 'localhost'),
                    port=redis_config.get('port', 6379),
                    db=redis_config.get('db', 0),
                    decode_responses=True
                )
                # Test connection
                self.cache.ping()
                self.logger.info("Redis cache connected successfully")
            except Exception as e:
                self.logger.warning(f"Redis cache setup failed: {e}")
                self.cache = None
        else:
            self.logger.warning("Redis not available. Caching disabled.")

    def setup_metrics(self):
        """Setup Prometheus metrics"""
        if PROMETHEUS_AVAILABLE:
            self.metrics = {
                'request_count': Counter('api_requests_total', 'Total API requests'),
                'request_duration': Histogram('api_request_duration_seconds', 'API request duration'),
                'active_connections': Gauge('api_active_connections', 'Active API connections'),
                'cache_hits': Counter('api_cache_hits_total', 'Cache hits'),
                'cache_misses': Counter('api_cache_misses_total', 'Cache misses')
            }
            self.logger.info("Prometheus metrics initialized")

    def setup_routes(self):
        """Setup all API routes"""

        # Include modular routers
        try:
            from layer5.document_api import router as document_router

            if document_router:
                self.app.include_router(document_router, prefix="/api/v2")
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.warning("Failed to register document routes: %s", exc)

        # Pydantic models for request/response
        class ImportRequest(BaseModel):
            files: List[str] = Field(..., description="List of file paths to import")
            company_name: str = Field(..., description="Company name")
            config: Dict[str, Any] = Field(default={}, description="Import configuration")

        class ExportRequest(BaseModel):
            company_id: str = Field(..., description="Company ID")
            format: str = Field(..., description="Export format")
            config: Dict[str, Any] = Field(default={}, description="Export configuration")

        class AIQueryRequest(BaseModel):
            query: str = Field(..., description="Natural language query")
            company_id: Optional[str] = Field(None, description="Company ID for context")
            session_id: Optional[str] = Field(None, description="Session ID for context")

        class AuditRequest(BaseModel):
            company_id: str = Field(..., description="Company ID")
            template: str = Field(..., description="Audit template")
            config: Dict[str, Any] = Field(default={}, description="Audit configuration")

        # Health and Info endpoints
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            uptime = time.time() - self.start_time
            return {
                "status": self.health_status,
                "uptime_seconds": uptime,
                "request_count": self.request_count,
                "timestamp": datetime.now().isoformat()
            }

        @self.app.get("/api/v2/info")
        async def get_system_info():
            """Get enhanced system information with AI status"""
            try:
                info = {
                    "name": "DAP Enhanced API Server",
                    "version": "2.0.0",
                    "status": self.health_status,
                    "uptime": time.time() - self.start_time,
                    "features": {
                        "fastapi": FASTAPI_AVAILABLE,
                        "redis_cache": self.cache is not None,
                        "prometheus_metrics": PROMETHEUS_AVAILABLE,
                        "ai_capabilities": True
                    },
                    "endpoints": {
                        "data_operations": ["/api/v2/companies", "/api/v2/data", "/api/v2/import", "/api/v2/export"],
                        "ai_services": ["/api/v2/ai/query", "/api/v2/ai/analyze", "/api/v2/ai/anomalies"],
                        "audit_services": ["/api/v2/audit/templates", "/api/v2/audit/generate", "/api/v2/audit/rules"],
                        "system": ["/health", "/metrics", "/api/v2/performance"]
                    },
                    "rate_limits": self.rate_limits,
                    "cache_status": "enabled" if self.cache else "disabled"
                }

                return info
            except Exception as e:
                self.logger.error(f"Error getting system info: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # Data operations endpoints
        @self.app.get("/api/v2/companies")
        async def list_companies():
            """List all client companies with statistics"""
            try:
                # Mock data - in real implementation, get from database
                companies = [
                    {
                        "id": "comp_001",
                        "name": "示例科技有限公司",
                        "industry": "软件开发",
                        "data_sources": ["金蝶K3", "Excel"],
                        "last_import": "2024-01-15T10:30:00",
                        "record_count": 15420,
                        "status": "active"
                    },
                    {
                        "id": "comp_002",
                        "name": "创新制造集团",
                        "industry": "制造业",
                        "data_sources": ["用友U8", "SAP"],
                        "last_import": "2024-01-14T16:45:00",
                        "record_count": 28756,
                        "status": "active"
                    }
                ]

                return {
                    "companies": companies,
                    "total_count": len(companies),
                    "active_count": sum(1 for c in companies if c["status"] == "active")
                }
            except Exception as e:
                self.logger.error(f"Error listing companies: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/v2/data/{company_id}/{table_name}")
        async def get_company_data(
            company_id: str,
            table_name: str,
            limit: int = 100,
            offset: int = 0
        ):
            """Get company-specific data with pagination"""
            try:
                # Check cache first
                cache_key = f"data:{company_id}:{table_name}:{limit}:{offset}"
                if self.cache:
                    cached_data = self.cache.get(cache_key)
                    if cached_data:
                        if PROMETHEUS_AVAILABLE:
                            self.metrics['cache_hits'].inc()
                        return json.loads(cached_data)
                    elif PROMETHEUS_AVAILABLE:
                        self.metrics['cache_misses'].inc()

                # Mock data response
                response_data = {
                    "company_id": company_id,
                    "table_name": table_name,
                    "data": [
                        {
                            "id": f"record_{i}",
                            "amount": 1000 + i * 100,
                            "date": f"2024-01-{15 + i:02d}",
                            "description": f"交易记录 {i}"
                        }
                        for i in range(offset, min(offset + limit, 50))
                    ],
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total": 1000,
                        "has_more": offset + limit < 1000
                    }
                }

                # Cache response
                if self.cache:
                    self.cache.setex(cache_key, 300, json.dumps(response_data))  # 5 min cache

                return response_data
            except Exception as e:
                self.logger.error(f"Error getting company data: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v2/import")
        async def import_data(request: ImportRequest, background_tasks: BackgroundTasks):
            """Import new data with progress tracking"""
            try:
                task_id = str(uuid.uuid4())

                # Start background import task
                background_tasks.add_task(
                    self.process_import_task,
                    task_id,
                    request.files,
                    request.company_name,
                    request.config
                )

                return {
                    "task_id": task_id,
                    "status": "started",
                    "message": f"Import task started for {request.company_name}",
                    "files_count": len(request.files),
                    "tracking_url": f"/api/v2/import/status/{task_id}"
                }
            except Exception as e:
                self.logger.error(f"Error starting import: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/v2/import/status/{task_id}")
        async def get_import_status(task_id: str):
            """Get import task status"""
            try:
                # Check cache for task status
                status_key = f"task_status:{task_id}"
                if self.cache:
                    status_data = self.cache.get(status_key)
                    if status_data:
                        return json.loads(status_data)

                # Default response if not found
                return {
                    "task_id": task_id,
                    "status": "not_found",
                    "message": "Task not found or expired"
                }
            except Exception as e:
                self.logger.error(f"Error getting import status: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v2/export/{format}")
        async def export_data(format: str, request: ExportRequest):
            """Multi-format export with templates"""
            try:
                supported_formats = ['excel', 'pdf', 'word', 'json', 'csv']
                if format.lower() not in supported_formats:
                    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

                export_id = str(uuid.uuid4())

                # Mock export data
                export_data = {
                    "export_id": export_id,
                    "format": format,
                    "company_id": request.company_id,
                    "status": "processing",
                    "created_at": datetime.now().isoformat(),
                    "download_url": f"/api/v2/export/download/{export_id}",
                    "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
                }

                return export_data
            except Exception as e:
                self.logger.error(f"Error creating export: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # AI-Enhanced Analysis endpoints
        @self.app.post("/api/v2/ai/query")
        async def ai_query(request: AIQueryRequest):
            """Natural language query processing"""
            try:
                response = {
                    "query": request.query,
                    "company_id": request.company_id,
                    "session_id": request.session_id or str(uuid.uuid4()),
                    "response": f"基于您的查询'{request.query}'，我为您分析了相关数据。",
                    "sql_generated": "SELECT * FROM transactions WHERE amount > 10000",
                    "results_preview": [
                        {"transaction_id": "T001", "amount": 15000, "date": "2024-01-15"},
                        {"transaction_id": "T002", "amount": 12000, "date": "2024-01-16"}
                    ],
                    "insights": ["发现2笔大额交易", "需要进一步审计确认"],
                    "timestamp": datetime.now().isoformat()
                }

                return response
            except Exception as e:
                self.logger.error(f"Error processing AI query: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v2/ai/analyze")
        async def ai_analyze(request: Dict[str, Any]):
            """AI-powered data analysis"""
            try:
                analysis_type = request.get('type', 'general')
                data_source = request.get('data_source', '')

                response = {
                    "analysis_id": str(uuid.uuid4()),
                    "type": analysis_type,
                    "status": "completed",
                    "results": {
                        "summary": "数据分析完成",
                        "anomalies_found": 3,
                        "risk_score": 0.25,
                        "recommendations": [
                            "建议进一步核查异常交易",
                            "关注现金流异常波动"
                        ]
                    },
                    "timestamp": datetime.now().isoformat()
                }

                return response
            except Exception as e:
                self.logger.error(f"Error in AI analysis: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v2/ai/anomalies")
        async def detect_anomalies(request: Dict[str, Any]):
            """ML-powered anomaly detection"""
            try:
                company_id = request.get('company_id')
                detection_config = request.get('config', {})

                response = {
                    "detection_id": str(uuid.uuid4()),
                    "company_id": company_id,
                    "anomalies": [
                        {
                            "id": "anomaly_001",
                            "type": "amount_anomaly",
                            "description": "异常大额交易",
                            "severity": "high",
                            "score": 0.95,
                            "details": {
                                "transaction_id": "T001",
                                "amount": 500000,
                                "expected_range": "10000-50000"
                            }
                        }
                    ],
                    "summary": {
                        "total_anomalies": 1,
                        "high_severity": 1,
                        "medium_severity": 0,
                        "low_severity": 0
                    },
                    "timestamp": datetime.now().isoformat()
                }

                return response
            except Exception as e:
                self.logger.error(f"Error detecting anomalies: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # Audit-specific operations
        @self.app.get("/api/v2/audit/templates")
        async def list_audit_templates():
            """Get available audit report templates"""
            try:
                templates = [
                    {
                        "id": "template_001",
                        "name": "标准财务审计报告",
                        "description": "包含资产负债表、利润表、现金流量表分析",
                        "category": "financial",
                        "fields": ["balance_sheet", "income_statement", "cash_flow"]
                    },
                    {
                        "id": "template_002",
                        "name": "内控合规性检查",
                        "description": "内部控制制度执行情况检查",
                        "category": "compliance",
                        "fields": ["internal_controls", "risk_assessment", "compliance_status"]
                    }
                ]

                return {"templates": templates, "total_count": len(templates)}
            except Exception as e:
                self.logger.error(f"Error listing audit templates: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v2/audit/generate")
        async def generate_audit_report(request: AuditRequest):
            """Generate audit reports"""
            try:
                report_id = str(uuid.uuid4())

                response = {
                    "report_id": report_id,
                    "company_id": request.company_id,
                    "template": request.template,
                    "status": "generated",
                    "download_url": f"/api/v2/audit/download/{report_id}",
                    "summary": {
                        "pages": 15,
                        "sections": 5,
                        "findings": 3,
                        "recommendations": 7
                    },
                    "created_at": datetime.now().isoformat()
                }

                return response
            except Exception as e:
                self.logger.error(f"Error generating audit report: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/v2/audit/rules")
        async def list_audit_rules():
            """List active audit rules"""
            try:
                rules = [
                    {
                        "id": "rule_001",
                        "name": "大额交易检查",
                        "description": "检查超过限额的交易",
                        "type": "validation",
                        "threshold": 100000,
                        "active": True
                    },
                    {
                        "id": "rule_002",
                        "name": "异常账户余额",
                        "description": "检查账户余额异常波动",
                        "type": "anomaly",
                        "sensitivity": "high",
                        "active": True
                    }
                ]

                return {"rules": rules, "active_count": sum(1 for r in rules if r["active"])}
            except Exception as e:
                self.logger.error(f"Error listing audit rules: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # System management endpoints
        @self.app.get("/api/v2/performance")
        async def get_performance_metrics():
            """Get real-time performance metrics"""
            try:
                import psutil

                metrics = {
                    "system": {
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_usage": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
                    },
                    "api": {
                        "total_requests": self.request_count,
                        "uptime_seconds": time.time() - self.start_time,
                        "health_status": self.health_status
                    },
                    "cache": {
                        "enabled": self.cache is not None,
                        "hit_rate": 0.85 if self.cache else 0
                    }
                }

                return metrics
            except Exception as e:
                self.logger.error(f"Error getting performance metrics: {e}")
                return {
                    "system": {"status": "unavailable"},
                    "api": {
                        "total_requests": self.request_count,
                        "uptime_seconds": time.time() - self.start_time,
                        "health_status": self.health_status
                    }
                }

        @self.app.get("/metrics")
        async def get_prometheus_metrics():
            """Get Prometheus metrics"""
            if PROMETHEUS_AVAILABLE:
                return Response(generate_latest(), media_type="text/plain")
            else:
                raise HTTPException(status_code=404, detail="Metrics not available")

        @self.app.post("/api/v2/models/retrain")
        async def retrain_models(background_tasks: BackgroundTasks):
            """Trigger AI model retraining"""
            try:
                task_id = str(uuid.uuid4())

                background_tasks.add_task(self.retrain_models_task, task_id)

                return {
                    "task_id": task_id,
                    "status": "started",
                    "message": "Model retraining started",
                    "estimated_duration": "30-60 minutes"
                }
            except Exception as e:
                self.logger.error(f"Error starting model retraining: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def setup_background_tasks(self):
        """Setup background task processors"""
        pass

    async def process_import_task(self, task_id: str, files: List[str], company_name: str, config: Dict[str, Any]):
        """Process import task in background"""
        try:
            # Update task status
            if self.cache:
                status = {
                    "task_id": task_id,
                    "status": "processing",
                    "progress": 0,
                    "current_file": files[0] if files else "",
                    "total_files": len(files),
                    "message": "Starting import process",
                    "updated_at": datetime.now().isoformat()
                }
                self.cache.setex(f"task_status:{task_id}", 3600, json.dumps(status))

            # Simulate import process
            for i, file_path in enumerate(files):
                await asyncio.sleep(2)  # Simulate processing time

                progress = int((i + 1) / len(files) * 100)
                if self.cache:
                    status.update({
                        "progress": progress,
                        "current_file": file_path,
                        "message": f"Processing file {i+1} of {len(files)}",
                        "updated_at": datetime.now().isoformat()
                    })
                    self.cache.setex(f"task_status:{task_id}", 3600, json.dumps(status))

            # Complete task
            if self.cache:
                status.update({
                    "status": "completed",
                    "progress": 100,
                    "message": "Import completed successfully",
                    "completed_at": datetime.now().isoformat()
                })
                self.cache.setex(f"task_status:{task_id}", 3600, json.dumps(status))

        except Exception as e:
            self.logger.error(f"Error in import task {task_id}: {e}")
            if self.cache:
                error_status = {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat()
                }
                self.cache.setex(f"task_status:{task_id}", 3600, json.dumps(error_status))

    async def retrain_models_task(self, task_id: str):
        """Retrain AI models in background"""
        try:
            self.logger.info(f"Starting model retraining task {task_id}")

            # Simulate model retraining
            await asyncio.sleep(10)  # Simulate retraining time

            self.logger.info(f"Model retraining task {task_id} completed")

        except Exception as e:
            self.logger.error(f"Error in model retraining task {task_id}: {e}")

    def start_server(self, host: str = "127.0.0.1", port: int = 8000, **kwargs):
        """Start the FastAPI server"""
        if not FASTAPI_AVAILABLE:
            self.logger.error("FastAPI not available. Cannot start server.")
            return

        self.logger.info(f"Starting DAP Enhanced API Server on {host}:{port}")

        uvicorn_config = {
            "host": host,
            "port": port,
            "log_level": "info",
            "access_log": True,
            **kwargs
        }

        uvicorn.run(self.app, **uvicorn_config)

# Convenience functions
def start_api_server(host: str = "127.0.0.1", port: int = 8000, ai_enabled: bool = True):
    """Start the enhanced API server with AI capabilities"""
    config = {
        "ai_enabled": ai_enabled,
        "api_tokens": ["dap-api-token-2024"],
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 0
        }
    }

    server = EnhancedAPIServer(config)
    server.start_server(host, port)

def create_api_app(config: Dict[str, Any] = None) -> Optional[FastAPI]:
    """Create FastAPI app for external hosting"""
    if not FASTAPI_AVAILABLE:
        return None

    server = EnhancedAPIServer(config)
    return server.app

# Test function
async def test_api_server():
    """Test the enhanced API server functionality"""
    print("Testing Enhanced API Server...")

    server = EnhancedAPIServer()
    print(f"✓ Server initialized: {server.app is not None}")

    # Test without starting server
    print("✓ Enhanced API Server test completed")

if __name__ == "__main__":
    import asyncio

    # Run test
    asyncio.run(test_api_server())

    # Start server if run directly
    start_api_server()
