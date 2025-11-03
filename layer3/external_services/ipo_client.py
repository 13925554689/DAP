"""
IPO Client - IPO智能体客户端 (CIRA Lite for IPO)
Initial Public Offering Intelligence Agent
"""

from typing import Dict, Any, List, Optional
import logging
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class IPOClient(BaseServiceClient):
    """IPO智能体客户端 - CIRA Lite for IPO"""
    
    DEFAULT_PORT = 8005
    
    def __init__(self, host: str = "localhost", port: Optional[int] = None):
        """
        初始化IPO智能体客户端
        
        Args:
            host: 服务主机地址
            port: 服务端口(默认8005)
        """
        port = port or self.DEFAULT_PORT
        base_url = f"http://{host}:{port}"
        super().__init__("IPO", base_url)
    
    def search(self, query: str, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        搜索IPO相关规则
        
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
    
    def assess_ipo_readiness(
        self,
        company_info: Dict[str, Any],
        financial_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        IPO准备度评估
        
        Args:
            company_info: 公司基本信息
            financial_data: 财务数据
            **kwargs: 其他参数
            
        Returns:
            IPO准备度评估结果
        """
        return self._request(
            "POST",
            "/api/assess/readiness",
            data={
                "company_info": company_info,
                "financial_data": financial_data,
                **kwargs
            }
        )
    
    def check_ipo_barriers(
        self,
        company_profile: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        IPO障碍检查
        
        Args:
            company_profile: 公司档案
            **kwargs: 其他参数
            
        Returns:
            潜在障碍列表和解决建议
        """
        return self._request(
            "POST",
            "/api/check/barriers",
            data={
                "company_profile": company_profile,
                **kwargs
            }
        )
    
    def get_ipo_checklist(
        self,
        board: str = "main",
        industry: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取IPO检查清单
        
        Args:
            board: 板块(main/gem/sci-tech)
            industry: 行业
            **kwargs: 其他参数
            
        Returns:
            IPO检查清单
        """
        return self._request(
            "GET",
            "/api/checklist",
            params={
                "board": board,
                "industry": industry,
                **kwargs
            }
        )
    
    def analyze_financials_for_ipo(
        self,
        financial_statements: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        IPO财务分析
        
        Args:
            financial_statements: 财务报表数据(多期)
            **kwargs: 其他参数
            
        Returns:
            财务分析结果和改进建议
        """
        return self._request(
            "POST",
            "/api/analyze/financials",
            data={
                "financial_statements": financial_statements,
                **kwargs
            }
        )
