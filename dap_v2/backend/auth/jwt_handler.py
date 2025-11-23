"""
DAP v2.0 - JWT Token Handler
JSON Web Token generation and validation
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import logging

from config import settings

logger = logging.getLogger(__name__)


class JWTHandler:
    """JWT token generation and validation"""

    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建访问令牌

        Args:
            data: 要编码的数据（通常包含user_id, username等）
            expires_delta: 自定义过期时间

        Returns:
            编码后的JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        logger.debug(f"Created access token for user: {data.get('sub')}")

        return encoded_jwt

    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建刷新令牌

        Args:
            data: 要编码的数据
            expires_delta: 自定义过期时间

        Returns:
            编码后的JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        logger.debug(f"Created refresh token for user: {data.get('sub')}")

        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        解码JWT token

        Args:
            token: JWT token字符串

        Returns:
            解码后的payload字典

        Raises:
            JWTError: token无效或过期
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except JWTError as e:
            logger.error(f"JWT decode error: {str(e)}")
            raise

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        验证token有效性

        Args:
            token: JWT token字符串
            token_type: token类型（access/refresh）

        Returns:
            验证通过返回payload，否则返回None
        """
        try:
            payload = self.decode_token(token)

            # 验证token类型
            if payload.get("type") != token_type:
                logger.warning(f"Token type mismatch. Expected: {token_type}, Got: {payload.get('type')}")
                return None

            # 验证是否过期
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                logger.warning("Token has expired")
                return None

            return payload

        except JWTError as e:
            logger.error(f"Token verification failed: {str(e)}")
            return None

    def get_user_id_from_token(self, token: str) -> Optional[str]:
        """
        从token中提取用户ID

        Args:
            token: JWT token字符串

        Returns:
            用户ID或None
        """
        payload = self.verify_token(token)
        if payload:
            return payload.get("sub")
        return None

    def create_token_pair(self, user_id: str, username: str, **extra_data) -> Dict[str, str]:
        """
        创建访问令牌和刷新令牌对

        Args:
            user_id: 用户ID
            username: 用户名
            **extra_data: 额外要包含的数据

        Returns:
            包含access_token和refresh_token的字典
        """
        token_data = {
            "sub": user_id,
            "username": username,
            **extra_data
        }

        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token({"sub": user_id})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }


# Global JWT handler instance
jwt_handler = JWTHandler()
