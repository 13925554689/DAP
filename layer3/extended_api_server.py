"""Extended API Server with External Services Integration

This module extends the base API server with endpoints for:
1. External knowledge base queries (ASKS, TAXKB, REGKB)
2. Intelligent agent services (Internal Control, IPO)
3. Enhanced natural language query with external recommendations
4. Service health monitoring
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from layer3.external_services import ExternalServiceManager
from layer3.external_services.service_manager import ServiceConfig
from layer4.enhanced_nl_query_engine import EnhancedNLQueryEngine

logger = logging.getLogger(__name__)

# Pydantic Models
class ExternalQueryRequest(BaseModel):
    """External service query request"""
    query: str
    service: Optional[str] = None  # asks/taxkb/regkb/internal_control/ipo
    limit: Optional[int] = 10
    context: Optional[Dict[str, Any]] = None


class ComplianceCheckRequest(BaseModel):
    """Compliance check request"""
    scenario: str
    company_info: Optional[Dict[str, Any]] = None
    check_types: Optional[List[str]] = None  # accounting/tax/regulatory/internal_control


class RiskAssessmentRequest(BaseModel):
    """Risk assessment request"""
    business_scenario: str
    risk_factors: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None


class IPOAssessmentRequest(BaseModel):
    """IPO assessment request"""
    company_info: Dict[str, Any]
    financial_data: Optional[Dict[str, Any]] = None
    assessment_type: Optional[str] = "readiness"  # readiness/barriers/checklist


class EnhancedNLQueryRequest(BaseModel):
    """Enhanced natural language query request"""
    query: str
    enable_external: Optional[bool] = True
    context: Optional[Dict[str, Any]] = None


# Create router
external_router = APIRouter(prefix="/api/external", tags=["external_services"])


class ExternalServicesAPI:
    """External services API handler"""
    
    def __init__(self, db_path: str):
        """Initialize external services API
        
        Args:
            db_path: Path to database
        """
        self.db_path = db_path
        self.service_manager: Optional[ExternalServiceManager] = None
        self.nl_engine: Optional[EnhancedNLQueryEngine] = None
        
        # Initialize managers
        self._init_managers()
    
    def _init_managers(self):
        """Initialize service managers"""
        try:
            # Initialize external service manager
            configs = {
                "asks": ServiceConfig(enabled=True, port=8001),
                "taxkb": ServiceConfig(enabled=True, port=8002),
                "regkb": ServiceConfig(enabled=True, port=8003),
                "internal_control": ServiceConfig(enabled=True, port=8004),
                "ipo": ServiceConfig(enabled=True, port=8005)
            }
            self.service_manager = ExternalServiceManager(configs)
            logger.info("External service manager initialized")
            
            # Initialize enhanced NL query engine
            self.nl_engine = EnhancedNLQueryEngine(
                self.db_path,
                enable_external_services=True,
                external_services_config=configs
            )
            logger.info("Enhanced NL query engine initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize external services API: {e}")


# Create API instance
_external_api: Optional[ExternalServicesAPI] = None


def get_external_api(db_path: str = "data/dap_data.db") -> ExternalServicesAPI:
    """Get or create external services API instance"""
    global _external_api
    if _external_api is None:
        _external_api = ExternalServicesAPI(db_path)
    return _external_api


# API Endpoints

@external_router.get("/health")
async def check_external_services_health():
    """Check health of all external services
    
    Returns:
        Service health status for each service
    """
    api = get_external_api()
    
    if not api.service_manager:
        raise HTTPException(status_code=503, detail="External services not initialized")
    
    try:
        health_status = api.service_manager.health_check_all()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "services": health_status,
            "healthy_count": sum(1 for v in health_status.values() if v),
            "total_count": len(health_status)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@external_router.post("/query")
async def query_external_service(request: ExternalQueryRequest):
    """Query external knowledge base or agent
    
    Args:
        request: Query request
        
    Returns:
        Query results from external service
    """
    api = get_external_api()
    
    if not api.service_manager:
        raise HTTPException(status_code=503, detail="External services not initialized")
    
    try:
        service = request.service
        
        # Route to appropriate service
        if service == "asks" or not service:
            result = api.service_manager.query_accounting_standard(
                request.query,
                fallback=True
            )
        elif service == "taxkb":
            result = api.service_manager.query_tax_regulation(
                request.query,
                fallback=True
            )
        elif service == "regkb":
            result = api.service_manager.query_regulatory_rule(
                request.query,
                fallback=True
            )
        else:
            # Comprehensive query across all services
            result = api.service_manager.comprehensive_query(
                request.query,
                parallel=True
            )
        
        return {
            "query": request.query,
            "service": service or "all",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@external_router.post("/compliance/check")
async def check_compliance(request: ComplianceCheckRequest):
    """Comprehensive compliance check
    
    Args:
        request: Compliance check request
        
    Returns:
        Compliance check results from multiple sources
    """
    api = get_external_api()
    
    if not api.service_manager:
        raise HTTPException(status_code=503, detail="External services not initialized")
    
    try:
        # Perform comprehensive compliance query
        results = api.service_manager.comprehensive_query(
            request.scenario,
            services=["asks", "taxkb", "regkb"],
            parallel=True
        )
        
        # Aggregate compliance status
        compliance_summary = {
            "accounting_compliance": results.get("asks", {}).get("success", False),
            "tax_compliance": results.get("taxkb", {}).get("success", False),
            "regulatory_compliance": results.get("regkb", {}).get("success", False)
        }
        
        overall_compliant = all(compliance_summary.values())
        
        return {
            "scenario": request.scenario,
            "overall_compliant": overall_compliant,
            "compliance_summary": compliance_summary,
            "detailed_results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance check failed: {str(e)}")


@external_router.post("/risk/assess")
async def assess_risk(request: RiskAssessmentRequest):
    """Assess internal control risk
    
    Args:
        request: Risk assessment request
        
    Returns:
        Risk assessment results
    """
    api = get_external_api()
    
    if not api.service_manager:
        raise HTTPException(status_code=503, detail="External services not initialized")
    
    try:
        result = api.service_manager.assess_internal_control_risk(
            request.business_scenario,
            request.risk_factors
        )
        
        return {
            "business_scenario": request.business_scenario,
            "risk_factors": request.risk_factors,
            "assessment": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk assessment failed: {str(e)}")


@external_router.post("/ipo/assess")
async def assess_ipo(request: IPOAssessmentRequest):
    """Assess IPO readiness
    
    Args:
        request: IPO assessment request
        
    Returns:
        IPO assessment results
    """
    api = get_external_api()
    
    if not api.service_manager:
        raise HTTPException(status_code=503, detail="External services not initialized")
    
    try:
        result = api.service_manager.assess_ipo_readiness(
            request.company_info,
            request.financial_data
        )
        
        return {
            "company_info": request.company_info,
            "assessment_type": request.assessment_type,
            "assessment": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"IPO assessment failed: {str(e)}")


@external_router.post("/nl/query")
async def enhanced_nl_query(request: EnhancedNLQueryRequest):
    """Enhanced natural language query with external services
    
    Args:
        request: NL query request
        
    Returns:
        Enhanced query results
    """
    api = get_external_api()
    
    if not api.nl_engine:
        raise HTTPException(status_code=503, detail="NL query engine not initialized")
    
    try:
        result = api.nl_engine.process_query(
            request.query,
            context=request.context or {}
        )
        
        return {
            "query": request.query,
            "external_enabled": request.enable_external,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NL query failed: {str(e)}")


@external_router.get("/services/status")
async def get_services_status():
    """Get status of all external services
    
    Returns:
        Detailed status information
    """
    api = get_external_api()
    
    if not api.service_manager:
        return {
            "enabled": False,
            "message": "External services not initialized"
        }
    
    try:
        status = api.service_manager.get_service_status()
        return {
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


# Export router for integration with main API server
__all__ = ['external_router', 'ExternalServicesAPI', 'get_external_api']
