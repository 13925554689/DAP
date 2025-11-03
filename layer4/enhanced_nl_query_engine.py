"""Enhanced Natural Language Query Engine with External Services Integration

This module extends the base NL query engine with:
1. Knowledge base integration (ASKS, TAXKB, REGKB)
2. Intelligent agent integration (Internal Control, IPO)
3. Hybrid query processing (database + external knowledge)
4. Smart recommendations based on external services
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from layer4.nl_query_engine import NLQueryEngine
from layer3.external_services import ExternalServiceManager
from layer3.external_services.service_manager import ServiceConfig

logger = logging.getLogger(__name__)


class EnhancedNLQueryEngine(NLQueryEngine):
    """Enhanced NL query engine with external services integration"""
    
    def __init__(
        self,
        db_path: str,
        enable_external_services: bool = True,
        external_services_config: Optional[Dict[str, ServiceConfig]] = None
    ):
        """Initialize enhanced NL query engine
        
        Args:
            db_path: Path to SQLite database
            enable_external_services: Whether to enable external services
            external_services_config: Configuration for external services
        """
        super().__init__(db_path)
        
        self.enable_external_services = enable_external_services
        self.external_manager: Optional[ExternalServiceManager] = None
        
        # Extended intent keywords for external services
        self._intent_keywords.update({
            "查询准则": ["准则", "会计准则", "审计准则", "规范", "标准"],
            "查询税务": ["税", "税务", "税收", "纳税", "税法"],
            "查询法规": ["法规", "规定", "监管", "证监会", "上交所", "深交所"],
            "内控评估": ["内控", "内部控制", "风险", "控制点"],
            "IPO评估": ["IPO", "上市", "发行", "准备"],
            "合规检查": ["合规", "符合", "是否符合", "要求"]
        })
        
        # Initialize external services manager
        if enable_external_services:
            self._init_external_services(external_services_config)
    
    def _init_external_services(self, configs: Optional[Dict[str, ServiceConfig]]):
        """Initialize external services manager"""
        try:
            if configs is None:
                # Default configuration
                configs = {
                    "asks": ServiceConfig(enabled=True, port=8001),
                    "taxkb": ServiceConfig(enabled=True, port=8002),
                    "regkb": ServiceConfig(enabled=True, port=8003),
                    "internal_control": ServiceConfig(enabled=True, port=8004),
                    "ipo": ServiceConfig(enabled=True, port=8005)
                }
            
            self.external_manager = ExternalServiceManager(configs)
            logger.info("External services manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize external services: {e}")
            self.external_manager = None
    
    def process_query(
        self,
        query_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enhanced query processing with external services
        
        Args:
            query_text: Natural language query
            context: Query context
            
        Returns:
            Enhanced query results with external knowledge
        """
        context = context or {}
        
        logger.info(f"Processing enhanced NL query: {query_text}")
        
        # Detect if query needs external services
        intent = self._identify_intent(query_text)
        
        # Route to appropriate handler
        if intent in ["查询准则", "查询税务", "查询法规", "内控评估", "IPO评估", "合规检查"]:
            return self._process_external_query(query_text, intent, context)
        else:
            # Standard database query
            result = super().process_query(query_text, context)
            
            # Enhance with external recommendations if applicable
            if result.get("success") and self.enable_external_services:
                result = self._enhance_with_recommendations(result, query_text, intent)
            
            return result
    
    def _process_external_query(
        self,
        query: str,
        intent: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process queries that require external services
        
        Args:
            query: Query text
            intent: Detected intent
            context: Query context
            
        Returns:
            Results from external services
        """
        if not self.external_manager:
            return {
                "success": False,
                "error": "外部服务未启用",
                "query": query,
                "intent": intent
            }
        
        try:
            if intent == "查询准则":
                return self._query_accounting_standards(query, context)
            
            elif intent == "查询税务":
                return self._query_tax_regulations(query, context)
            
            elif intent == "查询法规":
                return self._query_regulatory_rules(query, context)
            
            elif intent == "内控评估":
                return self._assess_internal_control(query, context)
            
            elif intent == "IPO评估":
                return self._assess_ipo_readiness(query, context)
            
            elif intent == "合规检查":
                return self._check_compliance(query, context)
            
            else:
                return {
                    "success": False,
                    "error": f"不支持的意图: {intent}",
                    "query": query
                }
                
        except Exception as e:
            logger.error(f"External query processing failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "intent": intent
            }
    
    def _query_accounting_standards(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Query accounting standards from ASKS
        
        Args:
            query: Query text
            context: Context
            
        Returns:
            Accounting standards search results
        """
        logger.info(f"Querying accounting standards: {query}")
        
        result = self.external_manager.query_accounting_standard(query, fallback=True)
        
        return {
            "success": result.get("success", False),
            "query": query,
            "intent": "查询准则",
            "source": "ASKS - 会计准则知识库",
            "results": result.get("data", []),
            "fallback_used": result.get("fallback_used", False),
            "message": result.get("message"),
            "executed_at": datetime.now().isoformat()
        }
    
    def _query_tax_regulations(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Query tax regulations from TAXKB"""
        logger.info(f"Querying tax regulations: {query}")
        
        result = self.external_manager.query_tax_regulation(query, fallback=True)
        
        return {
            "success": result.get("success", False),
            "query": query,
            "intent": "查询税务",
            "source": "TAXKB - 税务知识库",
            "results": result.get("data", []),
            "fallback_used": result.get("fallback_used", False),
            "message": result.get("message"),
            "executed_at": datetime.now().isoformat()
        }
    
    def _query_regulatory_rules(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Query regulatory rules from REGKB"""
        logger.info(f"Querying regulatory rules: {query}")
        
        # Extract source if mentioned
        source = None
        if "证监会" in query or "csrc" in query.lower():
            source = "csrc"
        elif "上交所" in query or "sse" in query.lower():
            source = "sse"
        elif "深交所" in query or "szse" in query.lower():
            source = "szse"
        
        result = self.external_manager.query_regulatory_rule(
            query,
            source=source,
            fallback=True
        )
        
        return {
            "success": result.get("success", False),
            "query": query,
            "intent": "查询法规",
            "source": "REGKB - 证监会监管规则库",
            "regulatory_source": source,
            "results": result.get("data", []),
            "fallback_used": result.get("fallback_used", False),
            "message": result.get("message"),
            "executed_at": datetime.now().isoformat()
        }
    
    def _assess_internal_control(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess internal control risk"""
        logger.info(f"Assessing internal control: {query}")
        
        # Extract business scenario from query
        business_scenario = query
        
        # Try to extract risk factors
        risk_factors = []
        risk_keywords = ["缺少", "未", "没有", "不", "弱", "差"]
        for keyword in risk_keywords:
            if keyword in query:
                # Simple extraction, can be enhanced
                risk_factors.append(f"提及了'{keyword}'相关的风险")
        
        result = self.external_manager.assess_internal_control_risk(
            business_scenario,
            risk_factors if risk_factors else None
        )
        
        return {
            "success": result.get("success", False),
            "query": query,
            "intent": "内控评估",
            "source": "Internal Control Agent - CIRA Lite",
            "business_scenario": business_scenario,
            "risk_factors": risk_factors,
            "assessment": result.get("data", {}),
            "recommendations": result.get("recommendations", []),
            "executed_at": datetime.now().isoformat()
        }
    
    def _assess_ipo_readiness(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess IPO readiness"""
        logger.info(f"Assessing IPO readiness: {query}")
        
        # Build company info from context or query
        company_info = context.get("company_info", {})
        if not company_info:
            company_info = {
                "name": context.get("entity_name", "未指定公司"),
                "query": query
            }
        
        financial_data = context.get("financial_data")
        
        result = self.external_manager.assess_ipo_readiness(
            company_info,
            financial_data
        )
        
        return {
            "success": result.get("success", False),
            "query": query,
            "intent": "IPO评估",
            "source": "IPO Agent - CIRA Lite for IPO",
            "company_info": company_info,
            "readiness_score": result.get("readiness_score"),
            "barriers": result.get("barriers", []),
            "recommendations": result.get("recommendations", []),
            "executed_at": datetime.now().isoformat()
        }
    
    def _check_compliance(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check compliance using multiple sources"""
        logger.info(f"Checking compliance: {query}")
        
        # Comprehensive query across services
        results = self.external_manager.comprehensive_query(
            query,
            services=["asks", "taxkb", "regkb"],
            parallel=True
        )
        
        # Aggregate results
        compliance_summary = {
            "会计准则": results.get("asks", {}).get("success", False),
            "税务合规": results.get("taxkb", {}).get("success", False),
            "监管合规": results.get("regkb", {}).get("success", False)
        }
        
        return {
            "success": any(compliance_summary.values()),
            "query": query,
            "intent": "合规检查",
            "source": "综合查询 - 多个知识库",
            "compliance_summary": compliance_summary,
            "details": results,
            "executed_at": datetime.now().isoformat()
        }
    
    def _enhance_with_recommendations(
        self,
        db_result: Dict[str, Any],
        query: str,
        intent: str
    ) -> Dict[str, Any]:
        """Enhance database query results with external recommendations
        
        Args:
            db_result: Database query result
            query: Original query
            intent: Query intent
            
        Returns:
            Enhanced results with recommendations
        """
        if not self.external_manager:
            return db_result
        
        try:
            # Add relevant recommendations based on query
            recommendations = []
            
            # If querying accounts, add accounting standard references
            if intent == "查询科目" or intent == "查询余额":
                entities = db_result.get("entities", {})
                accounts = entities.get("accounts", [])
                
                if accounts:
                    for account in accounts[:2]:  # Limit to first 2
                        try:
                            ref = self.external_manager.query_accounting_standard(
                                account,
                                fallback=False
                            )
                            if ref.get("success") and ref.get("data"):
                                recommendations.append({
                                    "type": "accounting_standard",
                                    "account": account,
                                    "reference": ref["data"][0] if ref["data"] else None
                                })
                        except Exception as e:
                            logger.debug(f"Failed to get standard for {account}: {e}")
            
            # If querying amounts, add tax implications
            if intent in ["查询凭证", "查询汇总"]:
                entities = db_result.get("entities", {})
                amounts = entities.get("amounts", [])
                
                if amounts and len(amounts) > 0:
                    large_amount = any(amt.get("value", 0) > 100000 for amt in amounts)
                    if large_amount:
                        try:
                            tax_ref = self.external_manager.query_tax_regulation(
                                "大额交易税务处理",
                                fallback=False
                            )
                            if tax_ref.get("success"):
                                recommendations.append({
                                    "type": "tax_reference",
                                    "reason": "检测到大额交易",
                                    "reference": tax_ref.get("data")
                                })
                        except Exception as e:
                            logger.debug(f"Failed to get tax reference: {e}")
            
            # Add recommendations to result
            if recommendations:
                db_result["external_recommendations"] = recommendations
                db_result["enhanced"] = True
            
        except Exception as e:
            logger.warning(f"Failed to enhance with recommendations: {e}")
        
        return db_result
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all external services
        
        Returns:
            Service status information
        """
        if not self.external_manager:
            return {
                "enabled": False,
                "message": "外部服务未启用"
            }
        
        return {
            "enabled": True,
            **self.external_manager.get_service_status()
        }
    
    def health_check_external_services(self) -> Dict[str, bool]:
        """Check health of all external services
        
        Returns:
            Service health status
        """
        if not self.external_manager:
            return {}
        
        return self.external_manager.health_check_all()
