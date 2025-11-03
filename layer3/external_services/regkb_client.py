"""
REGKB Client - 证监会监管规则知识库客户端
Securities Regulatory Commission Knowledge Base Client
"""

from typing import Dict, Any, List, Optional
import logging
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class REGKBClient(BaseServiceClient):
    """证监会监管规则知识库客户端"""
    
    DEFAULT_PORT = 8003
    
    def __init__(self, host: str = "localhost", port: Optional[int] = None):
        """
        初始化REGKB客户端
        
        Args:
            host: 服务主机地址
            port: 服务端口(默认8003)
        """
        port = port or self.DEFAULT_PORT
        base_url = f"http://{host}:{port}"
        super().__init__("REGKB", base_url)
    
    def search(self, query: str, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        搜索监管规则
        
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
    
    def get_regulation(self, regulation_id: str) -> Dict[str, Any]:
        """
        获取指定监管规则详情
        
        Args:
            regulation_id: 规则ID
            
        Returns:
            规则详细信息
        """
        return self._request("GET", f"/api/regulations/{regulation_id}")
    
    def search_by_source(
        self,
        source: str,
        category: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        按来源搜索监管规则
        
        Args:
            source: 来源(csrc/sse/szse)
            category: 分类
            **kwargs: 其他参数
            
        Returns:
            搜索结果
        """
        params = {"source": source}
        if category:
            params["category"] = category
        params.update(kwargs)
        
        return self._request(
            "GET",
            "/api/regulations",
            params=params
        )
    
    def check_compliance(
        self,
        company_info: Dict[str, Any],
        check_type: str = "ipo",
        **kwargs
    ) -> Dict[str, Any]:
        """
        合规性检查
        
        Args:
            company_info: 公司信息
            check_type: 检查类型(ipo/listing/annual_report等)
            **kwargs: 其他参数
            
        Returns:
            合规检查结果
        """
        return self._request(
            "POST",
            "/api/compliance/check",
            data={
                "company_info": company_info,
                "check_type": check_type,
                **kwargs
            }
        )
