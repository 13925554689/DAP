"""
ASKS Client - 会计准则知识库客户端
AI Smart Audit Brain Knowledge System Client
"""

from typing import Dict, Any, List, Optional
import logging
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class ASKSClient(BaseServiceClient):
    """会计准则知识库客户端"""
    
    DEFAULT_PORT = 8001
    
    def __init__(self, host: str = "localhost", port: Optional[int] = None):
        """
        初始化ASKS客户端
        
        Args:
            host: 服务主机地址
            port: 服务端口(默认8001)
        """
        port = port or self.DEFAULT_PORT
        base_url = f"http://{host}:{port}"
        super().__init__("ASKS", base_url)
    
    def health_check(self) -> bool:
        """
        ASKS服务健康检查
        重写基类方法以正确处理ASKS服务的健康检查响应格式
        
        Returns:
            服务是否可用
        """
        try:
            response = self._request("GET", "/health")
            # ASKS服务使用status字段而不是success字段
            status = response.get("status")
            return status == "healthy"
        except Exception as e:
            logger.warning(f"ASKS 健康检查失败: {e}")
            return False
    
    def search(self, query: str, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        搜索会计准则
        
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
    
    def get_standard(self, standard_id: str) -> Dict[str, Any]:
        """
        获取指定会计准则详情
        
        Args:
            standard_id: 准则ID
            
        Returns:
            准则详细信息
        """
        return self._request("GET", f"/api/standards/{standard_id}")
    
    def search_by_category(self, category: str, **kwargs) -> Dict[str, Any]:
        """
        按分类搜索
        
        Args:
            category: 分类名称
            **kwargs: 其他参数
            
        Returns:
            搜索结果
        """
        return self._request(
            "GET",
            "/api/categories",
            params={"category": category, **kwargs}
        )
    
    def analyze_accounting_treatment(
        self, 
        scenario: str,
        amount: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        分析会计处理方案
        
        Args:
            scenario: 业务场景描述
            amount: 金额
            **kwargs: 其他参数
            
        Returns:
            分析结果,包含适用准则和处理建议
        """
        return self._request(
            "POST",
            "/api/analyze",
            data={
                "scenario": scenario,
                "amount": amount,
                **kwargs
            }
        )
    
    def get_latest_updates(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取最新准则更新
        
        Args:
            limit: 返回数量
            
        Returns:
            最新更新列表
        """
        return self._request(
            "GET",
            "/api/updates",
            params={"limit": limit}
        )
