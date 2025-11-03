"""
TAXKB Client - 税务知识库客户端
Tax Knowledge Base Client
"""

from typing import Dict, Any, List, Optional
import logging
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class TAXKBClient(BaseServiceClient):
    """税务知识库客户端"""
    
    DEFAULT_PORT = 8002
    
    def __init__(self, host: str = "localhost", port: Optional[int] = None):
        """
        初始化TAXKB客户端
        
        Args:
            host: 服务主机地址
            port: 服务端口(默认8002)
        """
        port = port or self.DEFAULT_PORT
        base_url = f"http://{host}:{port}"
        super().__init__("TAXKB", base_url)
    
    def search(self, query: str, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        搜索税务规则
        
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
    
    def get_tax_regulation(self, regulation_id: str) -> Dict[str, Any]:
        """
        获取指定税务法规详情
        
        Args:
            regulation_id: 法规ID
            
        Returns:
            法规详细信息
        """
        return self._request("GET", f"/api/regulations/{regulation_id}")
    
    def calculate_tax(
        self, 
        income: float,
        tax_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        计算税额
        
        Args:
            income: 应税收入
            tax_type: 税种(如:增值税、企业所得税等)
            **kwargs: 其他参数
            
        Returns:
            计算结果
        """
        return self._request(
            "POST",
            "/api/calculate",
            data={
                "income": income,
                "tax_type": tax_type,
                **kwargs
            }
        )
    
    def search_preferential_policies(
        self,
        industry: Optional[str] = None,
        region: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        搜索税收优惠政策
        
        Args:
            industry: 行业
            region: 地区
            **kwargs: 其他筛选条件
            
        Returns:
            优惠政策列表
        """
        params = {}
        if industry:
            params["industry"] = industry
        if region:
            params["region"] = region
        params.update(kwargs)
        
        return self._request(
            "GET",
            "/api/policies",
            params=params
        )
