"""
Internal Control Client - 内控智能体客户端 (CIRA Lite)
Corporate Internal Risk Assessment Lite
"""

from typing import Dict, Any, List, Optional
import logging
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class InternalControlClient(BaseServiceClient):
    """内控智能体客户端 - CIRA Lite"""
    
    DEFAULT_PORT = 8004
    
    def __init__(self, host: str = "localhost", port: Optional[int] = None):
        """
        初始化内控智能体客户端
        
        Args:
            host: 服务主机地址
            port: 服务端口(默认8004)
        """
        port = port or self.DEFAULT_PORT
        base_url = f"http://{host}:{port}"
        super().__init__("InternalControl", base_url)
    
    def search(self, query: str, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        搜索内控指引
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            **kwargs: 其他搜索参数
            
        Returns:
            搜索结果
        """
        return self._request(
            "POST",
            "/api/search",
            data={
                "query": query,
                "limit": limit,
                **kwargs
            }
        )
    
    def assess_risk(
        self,
        business_scenario: str,
        risk_factors: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        内控风险评估
        
        Args:
            business_scenario: 业务场景描述
            risk_factors: 风险因素列表
            **kwargs: 其他参数
            
        Returns:
            风险评估结果
        """
        return self._request(
            "POST",
            "/api/assess/risk",
            data={
                "business_scenario": business_scenario,
                "risk_factors": risk_factors or [],
                **kwargs
            }
        )
    
    def get_control_recommendations(
        self,
        risk_level: str,
        department: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取内控建议
        
        Args:
            risk_level: 风险等级(high/medium/low)
            department: 部门
            **kwargs: 其他参数
            
        Returns:
            内控措施建议
        """
        return self._request(
            "POST",
            "/api/recommendations",
            data={
                "risk_level": risk_level,
                "department": department,
                **kwargs
            }
        )
    
    def check_internal_control_compliance(
        self,
        control_points: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        内控合规性检查
        
        Args:
            control_points: 控制点列表
            **kwargs: 其他参数
            
        Returns:
            合规检查结果
        """
        return self._request(
            "POST",
            "/api/compliance/check",
            data={
                "control_points": control_points,
                **kwargs
            }
        )
