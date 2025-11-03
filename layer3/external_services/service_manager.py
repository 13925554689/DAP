"""
External Service Manager - 外部服务统一管理器
Unified manager for all external intelligent agents
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import concurrent.futures

from .asks_client import ASKSClient
from .taxkb_client import TAXKBClient  
from .regkb_client import REGKBClient
from .internal_control_client import InternalControlClient
from .ipo_client import IPOClient

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """服务配置"""
    enabled: bool = True
    host: str = "localhost"
    port: Optional[int] = None
    timeout: int = 30


class ExternalServiceManager:
    """
    外部服务管理器
    
    统一管理所有外部智能体服务的调用、健康检查、降级策略
    """
    
    def __init__(self, configs: Optional[Dict[str, ServiceConfig]] = None):
        """
        初始化服务管理器
        
        Args:
            configs: 服务配置字典,键为服务名,值为ServiceConfig
        """
        self.configs = configs or {}
        self.clients: Dict[str, Any] = {}
        self._service_status: Dict[str, bool] = {}
        
        # 初始化所有客户端
        self._init_clients()
        
        logger.info("外部服务管理器初始化完成")
    
    def _init_clients(self):
        """初始化所有服务客户端"""
        # ASKS - 会计准则知识库
        asks_config = self.configs.get("asks", ServiceConfig())
        if asks_config.enabled:
            try:
                self.clients["asks"] = ASKSClient(
                    host=asks_config.host,
                    port=asks_config.port
                )
                logger.info("✅ ASKS客户端初始化成功")
            except Exception as e:
                logger.error(f"❌ ASKS客户端初始化失败: {e}")
        
        # TAXKB - 税务知识库
        taxkb_config = self.configs.get("taxkb", ServiceConfig())
        if taxkb_config.enabled:
            try:
                self.clients["taxkb"] = TAXKBClient(
                    host=taxkb_config.host,
                    port=taxkb_config.port
                )
                logger.info("✅ TAXKB客户端初始化成功")
            except Exception as e:
                logger.error(f"❌ TAXKB客户端初始化失败: {e}")
        
        # REGKB - 证监会监管规则
        regkb_config = self.configs.get("regkb", ServiceConfig())
        if regkb_config.enabled:
            try:
                self.clients["regkb"] = REGKBClient(
                    host=regkb_config.host,
                    port=regkb_config.port
                )
                logger.info("✅ REGKB客户端初始化成功")
            except Exception as e:
                logger.error(f"❌ REGKB客户端初始化失败: {e}")
        
        # Internal Control - 内控智能体
        ic_config = self.configs.get("internal_control", ServiceConfig())
        if ic_config.enabled:
            try:
                self.clients["internal_control"] = InternalControlClient(
                    host=ic_config.host,
                    port=ic_config.port
                )
                logger.info("✅ 内控智能体客户端初始化成功")
            except Exception as e:
                logger.error(f"❌ 内控智能体客户端初始化失败: {e}")
        
        # IPO - IPO智能体
        ipo_config = self.configs.get("ipo", ServiceConfig())
        if ipo_config.enabled:
            try:
                self.clients["ipo"] = IPOClient(
                    host=ipo_config.host,
                    port=ipo_config.port
                )
                logger.info("✅ IPO智能体客户端初始化成功")
            except Exception as e:
                logger.error(f"❌ IPO智能体客户端初始化失败: {e}")
    
    def health_check_all(self) -> Dict[str, bool]:
        """
        检查所有服务健康状态
        
        Returns:
            服务名到健康状态的映射
        """
        status = {}
        for name, client in self.clients.items():
            try:
                is_healthy = client.health_check()
                status[name] = is_healthy
                self._service_status[name] = is_healthy
                
                if is_healthy:
                    logger.info(f"✅ {name} 服务健康")
                else:
                    logger.warning(f"⚠️ {name} 服务不健康")
            except Exception as e:
                logger.error(f"❌ {name} 健康检查失败: {e}")
                status[name] = False
                self._service_status[name] = False
        
        return status
    
    def query_accounting_standard(
        self,
        query: str,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        查询会计准则
        
        Args:
            query: 查询关键词
            fallback: 是否启用降级策略
            
        Returns:
            查询结果
        """
        client = self.clients.get("asks")
        if not client:
            return {
                "success": False,
                "error": "ASKS服务未启用",
                "fallback_used": False
            }
        
        try:
            result = client.search(query)
            if result.get("success"):
                return result
            elif fallback:
                logger.warning("ASKS查询失败,尝试降级策略")
                return self._fallback_accounting_query(query)
            else:
                return result
        except Exception as e:
            logger.error(f"ASKS查询异常: {e}")
            if fallback:
                return self._fallback_accounting_query(query)
            return {"success": False, "error": str(e)}
    
    def query_tax_regulation(
        self,
        query: str,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        查询税务规则
        
        Args:
            query: 查询关键词
            fallback: 是否启用降级策略
            
        Returns:
            查询结果
        """
        client = self.clients.get("taxkb")
        if not client:
            return {
                "success": False,
                "error": "TAXKB服务未启用",
                "fallback_used": False
            }
        
        try:
            result = client.search(query)
            if result.get("success"):
                return result
            elif fallback:
                logger.warning("TAXKB查询失败,尝试降级策略")
                return self._fallback_tax_query(query)
            else:
                return result
        except Exception as e:
            logger.error(f"TAXKB查询异常: {e}")
            if fallback:
                return self._fallback_tax_query(query)
            return {"success": False, "error": str(e)}
    
    def query_regulatory_rule(
        self,
        query: str,
        source: Optional[str] = None,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        查询监管规则
        
        Args:
            query: 查询关键词
            source: 来源(csrc/sse/szse)
            fallback: 是否启用降级策略
            
        Returns:
            查询结果
        """
        client = self.clients.get("regkb")
        if not client:
            return {
                "success": False,
                "error": "REGKB服务未启用",
                "fallback_used": False
            }
        
        try:
            if source:
                result = client.search_by_source(source, query=query)
            else:
                result = client.search(query)
                
            if result.get("success"):
                return result
            elif fallback:
                logger.warning("REGKB查询失败,尝试降级策略")
                return self._fallback_regulatory_query(query)
            else:
                return result
        except Exception as e:
            logger.error(f"REGKB查询异常: {e}")
            if fallback:
                return self._fallback_regulatory_query(query)
            return {"success": False, "error": str(e)}
    
    def assess_internal_control_risk(
        self,
        business_scenario: str,
        risk_factors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        内控风险评估
        
        Args:
            business_scenario: 业务场景
            risk_factors: 风险因素
            
        Returns:
            评估结果
        """
        client = self.clients.get("internal_control")
        if not client:
            return {
                "success": False,
                "error": "内控智能体服务未启用"
            }
        
        try:
            return client.assess_risk(business_scenario, risk_factors)
        except Exception as e:
            logger.error(f"内控风险评估异常: {e}")
            return {"success": False, "error": str(e)}
    
    def assess_ipo_readiness(
        self,
        company_info: Dict[str, Any],
        financial_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        IPO准备度评估
        
        Args:
            company_info: 公司信息
            financial_data: 财务数据
            
        Returns:
            评估结果
        """
        client = self.clients.get("ipo")
        if not client:
            return {
                "success": False,
                "error": "IPO智能体服务未启用"
            }
        
        try:
            return client.assess_ipo_readiness(company_info, financial_data)
        except Exception as e:
            logger.error(f"IPO准备度评估异常: {e}")
            return {"success": False, "error": str(e)}
    
    def comprehensive_query(
        self,
        query: str,
        services: Optional[List[str]] = None,
        parallel: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        跨服务综合查询
        
        Args:
            query: 查询关键词
            services: 要查询的服务列表,None表示查询所有
            parallel: 是否并行查询
            
        Returns:
            各服务查询结果的字典
        """
        if services is None:
            services = list(self.clients.keys())
        
        results = {}
        
        if parallel:
            # 并行查询
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for service in services:
                    client = self.clients.get(service)
                    if client and hasattr(client, 'search'):
                        future = executor.submit(client.search, query)
                        futures[future] = service
                
                for future in concurrent.futures.as_completed(futures):
                    service = futures[future]
                    try:
                        results[service] = future.result()
                    except Exception as e:
                        logger.error(f"{service}并行查询失败: {e}")
                        results[service] = {"success": False, "error": str(e)}
        else:
            # 串行查询
            for service in services:
                client = self.clients.get(service)
                if client and hasattr(client, 'search'):
                    try:
                        results[service] = client.search(query)
                    except Exception as e:
                        logger.error(f"{service}查询失败: {e}")
                        results[service] = {"success": False, "error": str(e)}
        
        return results
    
    # 降级策略方法
    def _fallback_accounting_query(self, query: str) -> Dict[str, Any]:
        """会计准则查询降级策略"""
        return {
            "success": True,
            "fallback_used": True,
            "message": "ASKS服务暂时不可用,建议手动查询会计准则",
            "query": query,
            "data": []
        }
    
    def _fallback_tax_query(self, query: str) -> Dict[str, Any]:
        """税务规则查询降级策略"""
        return {
            "success": True,
            "fallback_used": True,
            "message": "TAXKB服务暂时不可用,建议手动查询税务法规",
            "query": query,
            "data": []
        }
    
    def _fallback_regulatory_query(self, query: str) -> Dict[str, Any]:
        """监管规则查询降级策略"""
        return {
            "success": True,
            "fallback_used": True,
            "message": "REGKB服务暂时不可用,建议手动查询监管文件",
            "query": query,
            "data": []
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        获取所有服务状态
        
        Returns:
            服务状态汇总
        """
        return {
            "total_services": len(self.clients),
            "enabled_services": list(self.clients.keys()),
            "status": self._service_status,
            "health_check_time": None  # 可添加时间戳
        }
