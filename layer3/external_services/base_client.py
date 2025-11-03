"""
Base Client for External Services
外部服务基础客户端
"""

import requests
import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseServiceClient(ABC):
    """外部服务基础客户端"""
    
    def __init__(self, service_name: str, base_url: str, timeout: int = 30):
        """
        初始化客户端
        
        Args:
            service_name: 服务名称
            base_url: 服务基础URL
            timeout: 请求超时时间(秒)
        """
        self.service_name = service_name
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        logger.info(f"初始化 {service_name} 客户端: {base_url}")
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一的HTTP请求方法
        
        Args:
            method: HTTP方法(GET/POST/PUT/DELETE)
            endpoint: API端点
            data: 请求体数据
            params: URL参数
            **kwargs: 其他requests参数
            
        Returns:
            响应数据字典
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"{method} {url}")
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            
            # 尝试解析JSON
            try:
                return response.json()
            except ValueError:
                return {"success": True, "data": response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"{self.service_name} 请求失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "service": self.service_name
            }
    
    def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            服务是否可用
        """
        try:
            response = self._request("GET", "/health")
            return response.get("success", False)
        except Exception as e:
            logger.warning(f"{self.service_name} 健康检查失败: {e}")
            return False
    
    @abstractmethod
    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        搜索方法(子类必须实现)
        
        Args:
            query: 搜索关键词
            **kwargs: 其他参数
            
        Returns:
            搜索结果
        """
        pass
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.session.close()
