"""
DAP v2.0 - Password Utilities
Password hashing, verification and strength validation
"""
import re
import bcrypt
from typing import Tuple
import logging

from config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    # Bcrypt has a 72-byte limit
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength based on configured policy

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    errors = []

    # Check minimum length
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"密码长度至少{settings.PASSWORD_MIN_LENGTH}个字符")

    # Check for uppercase
    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("密码必须包含至少一个大写字母")

    # Check for lowercase
    if settings.PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        errors.append("密码必须包含至少一个小写字母")

    # Check for digit
    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("密码必须包含至少一个数字")

    # Check for special character
    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("密码必须包含至少一个特殊字符")

    if errors:
        return False, "; ".join(errors)

    return True, "密码强度验证通过"


def get_password_strength_requirements() -> dict:
    """
    Get password strength requirements

    Returns:
        Dictionary with password requirements
    """
    return {
        "min_length": settings.PASSWORD_MIN_LENGTH,
        "require_uppercase": settings.PASSWORD_REQUIRE_UPPERCASE,
        "require_lowercase": settings.PASSWORD_REQUIRE_LOWERCASE,
        "require_digit": settings.PASSWORD_REQUIRE_DIGIT,
        "require_special": settings.PASSWORD_REQUIRE_SPECIAL,
        "special_chars": "!@#$%^&*(),.?\":{}|<>"
    }
