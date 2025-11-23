"""
DAP v2.0 - Authentication Dependencies
FastAPI dependency functions for authentication and authorization
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from models.database import get_db
from models.user import User, Role
from auth.jwt_handler import jwt_handler

logger = logging.getLogger(__name__)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    scheme_name="JWT"
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token

    Args:
        token: JWT access token
        db: Database session

    Returns:
        Current user object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Verify token
    payload = jwt_handler.verify_token(token, token_type="access")
    if not payload:
        logger.warning("Invalid or expired token")
        raise credentials_exception

    # Extract user_id
    user_id: str = payload.get("sub")
    if user_id is None:
        logger.warning("Token missing user_id (sub)")
        raise credentials_exception

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning(f"User not found: {user_id}")
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user

    Args:
        current_user: Current user from token

    Returns:
        Active user object

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        logger.warning(f"Inactive user attempted access: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已停用"
        )
    return current_user


def require_roles(required_roles: List[str]):
    """
    Dependency factory for role-based access control

    Args:
        required_roles: List of role codes that are allowed

    Returns:
        Dependency function that checks user roles

    Example:
        @router.get("/admin", dependencies=[Depends(require_roles(["manager", "partner"]))])
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> User:
        # Get user roles
        user_roles = [ur.role.role_code for ur in current_user.roles]

        # Check if user has any of the required roles
        if not any(role in required_roles for role in user_roles):
            logger.warning(
                f"User {current_user.username} attempted access with insufficient roles. "
                f"Required: {required_roles}, Has: {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(required_roles)}"
            )

        return current_user

    return role_checker


def require_permission(permission_code: str):
    """
    Dependency factory for permission-based access control

    Args:
        permission_code: Required permission code

    Returns:
        Dependency function that checks user permissions

    Example:
        @router.post("/projects", dependencies=[Depends(require_permission("project_create"))])
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> User:
        # Get user permissions through roles
        user_permissions = set()
        for user_role in current_user.roles:
            for role_perm in user_role.role.permissions:
                user_permissions.add(role_perm.permission.permission_code)

        # Check if user has the required permission
        if permission_code not in user_permissions:
            logger.warning(
                f"User {current_user.username} attempted access without required permission: "
                f"{permission_code}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要权限: {permission_code}"
            )

        return current_user

    return permission_checker


def require_min_role_level(min_level: int):
    """
    Dependency factory for minimum role level requirement

    Args:
        min_level: Minimum role level (1=auditor, 2=senior, 3=manager, 4=partner)

    Returns:
        Dependency function that checks user role level

    Example:
        @router.delete("/projects/{id}", dependencies=[Depends(require_min_role_level(3))])
    """
    async def level_checker(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> User:
        # Get user's highest role level
        user_max_level = 0
        for user_role in current_user.roles:
            if user_role.role.level > user_max_level:
                user_max_level = user_role.role.level

        # Check if user meets minimum level requirement
        if user_max_level < min_level:
            logger.warning(
                f"User {current_user.username} attempted access with insufficient role level. "
                f"Required: {min_level}, Has: {user_max_level}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要角色级别至少为 {min_level}"
            )

        return current_user

    return level_checker


# Convenience dependencies for common role requirements
require_auditor = require_min_role_level(1)  # Any logged-in user
require_senior = require_min_role_level(2)   # Senior or above
require_manager = require_min_role_level(3)  # Manager or above
require_partner = require_min_role_level(4)  # Partner only


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None
    Useful for endpoints that have different behavior for authenticated/anonymous users

    Args:
        token: JWT access token (optional)
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    if not token:
        return None

    try:
        payload = jwt_handler.verify_token(token, token_type="access")
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = db.query(User).filter(User.id == user_id).first()
        return user if user and user.is_active else None

    except Exception as e:
        logger.debug(f"Optional user authentication failed: {str(e)}")
        return None
