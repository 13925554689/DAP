"""
DAP v2.0 - Authentication Module
JWT token handling, password utilities, and authentication dependencies
"""

from .jwt_handler import jwt_handler, JWTHandler
from .password import (
    hash_password,
    verify_password,
    validate_password_strength,
    get_password_strength_requirements
)
from .dependencies import (
    get_current_user,
    get_current_active_user,
    require_roles,
    require_permission,
    require_min_role_level,
    require_auditor,
    require_senior,
    require_manager,
    require_partner,
    get_optional_user
)

__all__ = [
    # JWT Handler
    "jwt_handler",
    "JWTHandler",

    # Password utilities
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "get_password_strength_requirements",

    # Authentication dependencies
    "get_current_user",
    "get_current_active_user",
    "require_roles",
    "require_permission",
    "require_min_role_level",
    "require_auditor",
    "require_senior",
    "require_manager",
    "require_partner",
    "get_optional_user",
]
