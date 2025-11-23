"""
DAP v2.0 - User Management API Routes
RESTful API for user authentication and management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from models.database import get_db
from models.user import User, Role, UserRole
from schemas.user import (
    UserRegister, UserLogin, Token, TokenRefresh,
    UserResponse, UserDetailResponse, UserListResponse,
    UserUpdate, UserAdminUpdate, UserCreate,
    PasswordChange, PasswordForgot, PasswordReset,
    RoleAssignment, UserStatistics, PasswordPolicy
)
from auth import (
    jwt_handler, hash_password, verify_password,
    validate_password_strength, get_password_strength_requirements,
    get_current_user, get_current_active_user,
    require_manager, require_partner
)
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Users & Authentication"])


# ==================== Authentication Endpoints ====================

@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    用户注册

    **流程**:
    1. 验证用户名和邮箱唯一性
    2. 验证密码强度
    3. Hash密码
    4. 创建用户
    5. 分配默认角色（审计员）

    **注意**: 新注册用户默认为停用状态，需要管理员激活
    """
    # Check if username exists
    existing_user = db.query(User).filter(
        or_(User.username == user_data.username, User.email == user_data.email)
    ).first()

    if existing_user:
        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )

    # Validate password strength
    is_valid, message = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码强度不符合要求: {message}"
        )

    # Create user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        employee_id=user_data.employee_id,
        department=user_data.department,
        position=user_data.position,
        phone=user_data.phone,
        is_active=False  # 新用户默认停用，需管理员激活
    )

    db.add(new_user)
    db.flush()

    # Assign default role (auditor)
    default_role = db.query(Role).filter(Role.role_code == "auditor").first()
    if default_role:
        user_role = UserRole(user_id=new_user.id, role_id=default_role.id)
        db.add(user_role)

    db.commit()
    db.refresh(new_user)

    logger.info(f"New user registered: {new_user.username}")

    return new_user


@router.post("/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    用户登录

    **参数**:
    - `username`: 用户名或邮箱
    - `password`: 密码

    **返回**:
    - `access_token`: 访问令牌（有效期30分钟）
    - `refresh_token`: 刷新令牌（有效期7天）

    **错误**:
    - `401`: 用户名或密码错误
    - `400`: 用户已停用
    """
    # Find user by username or email
    user = db.query(User).filter(
        or_(User.username == form_data.username, User.email == form_data.username)
    ).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        logger.warning(f"Failed login attempt for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Inactive user login attempt: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已停用，请联系管理员"
        )

    # Update last login time
    user.last_login = datetime.utcnow()
    db.commit()

    # Create token pair
    tokens = jwt_handler.create_token_pair(
        user_id=str(user.id),
        username=user.username
    )

    logger.info(f"User logged in: {user.username}")

    return {
        **tokens,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/auth/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """
    刷新访问令牌

    **参数**:
    - `refresh_token`: 刷新令牌

    **返回**:
    - 新的token对
    """
    # Verify refresh token
    payload = jwt_handler.verify_token(token_data.refresh_token, token_type="refresh")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

    user_id = payload.get("sub")

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已停用"
        )

    # Create new token pair
    tokens = jwt_handler.create_token_pair(
        user_id=str(user.id),
        username=user.username
    )

    logger.info(f"Token refreshed for user: {user.username}")

    return {
        **tokens,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: User = Depends(get_current_active_user)
):
    """
    退出登录

    **注意**: 当前实现为无状态JWT，实际登出由客户端删除token实现
    未来可扩展为token黑名单机制
    """
    logger.info(f"User logged out: {current_user.username}")
    # TODO: Add token to blacklist if implementing token blacklist
    return None


@router.get("/auth/password-policy", response_model=PasswordPolicy)
async def get_password_policy():
    """获取密码策略要求"""
    return get_password_strength_requirements()


# ==================== User Profile Endpoints ====================

@router.get("/users/me", response_model=UserDetailResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取当前用户信息（包含角色）"""
    # Load roles
    user_roles = db.query(UserRole).filter(UserRole.user_id == current_user.id).all()

    result = UserDetailResponse.model_validate(current_user)
    result.roles = [ur.role for ur in user_roles]

    return result


@router.put("/users/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新当前用户信息"""
    update_data = user_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    current_user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(current_user)

    logger.info(f"User updated profile: {current_user.username}")

    return current_user


@router.put("/users/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """修改当前用户密码"""
    # Verify old password
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误"
        )

    # Validate new password strength
    is_valid, message = validate_password_strength(password_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"新密码强度不符合要求: {message}"
        )

    # Update password
    current_user.password_hash = hash_password(password_data.new_password)
    current_user.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"User changed password: {current_user.username}")

    return None


# ==================== User Management Endpoints (Admin) ====================

@router.get("/users", response_model=List[UserListResponse])
async def list_users(
    search: Optional[str] = Query(None, description="搜索用户名/姓名/员工号"),
    department: Optional[str] = Query(None, description="部门筛选"),
    is_active: Optional[bool] = Query(None, description="激活状态"),
    is_cpa: Optional[bool] = Query(None, description="是否CPA"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    获取用户列表（需要Manager以上权限）

    支持筛选和搜索
    """
    query = db.query(User)

    # Search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(search_pattern),
                User.full_name.ilike(search_pattern),
                User.employee_id.ilike(search_pattern)
            )
        )

    # Department filter
    if department:
        query = query.filter(User.department == department)

    # Active status filter
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    # CPA filter
    if is_cpa is not None:
        query = query.filter(User.is_cpa == is_cpa)

    # Order by creation date (newest first)
    query = query.order_by(User.created_at.desc())

    # Pagination
    users = query.offset(skip).limit(limit).all()

    return users


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    创建新用户（需要Manager以上权限）

    管理员可直接激活用户并分配角色
    """
    # Check if username or email exists
    existing_user = db.query(User).filter(
        or_(User.username == user_data.username, User.email == user_data.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在"
        )

    # Validate password strength
    is_valid, message = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码强度不符合要求: {message}"
        )

    # Create user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        employee_id=user_data.employee_id,
        department=user_data.department,
        position=user_data.position,
        phone=user_data.phone,
        is_active=user_data.is_active,
        created_by=current_user.id
    )

    db.add(new_user)
    db.flush()

    # Assign roles
    if user_data.role_ids:
        for role_id in user_data.role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                user_role = UserRole(
                    user_id=new_user.id,
                    role_id=role_id,
                    assigned_by=current_user.id
                )
                db.add(user_role)

    db.commit()
    db.refresh(new_user)

    logger.info(f"User created by {current_user.username}: {new_user.username}")

    return new_user


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """获取用户详情（需要Manager以上权限）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Load roles
    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()

    result = UserDetailResponse.model_validate(user)
    result.roles = [ur.role for ur in user_roles]

    return result


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserAdminUpdate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """更新用户信息（需要Manager以上权限）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Check email uniqueness if changed
    if user_update.email and user_update.email != user.email:
        existing = db.query(User).filter(User.email == user_update.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    logger.info(f"User updated by {current_user.username}: {user.username}")

    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_partner),
    db: Session = Depends(get_db)
):
    """删除用户（需要Partner权限）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )

    db.delete(user)
    db.commit()

    logger.warning(f"User deleted by {current_user.username}: {user.username}")

    return None


@router.post("/users/{user_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_user(
    user_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """激活用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    user.is_active = True
    user.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"User activated by {current_user.username}: {user.username}")

    return None


@router.post("/users/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """停用用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Prevent self-deactivation
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己"
        )

    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"User deactivated by {current_user.username}: {user.username}")

    return None


# ==================== Role Assignment Endpoints ====================

@router.get("/users/{user_id}/roles", response_model=List[dict])
async def get_user_roles(
    user_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """获取用户角色列表"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()

    return [
        {
            "id": ur.id,
            "role": {
                "id": ur.role.id,
                "role_name": ur.role.role_name,
                "role_code": ur.role.role_code,
                "level": ur.role.level
            },
            "project_id": ur.project_id,
            "assigned_at": ur.assigned_at
        }
        for ur in user_roles
    ]


@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: str,
    role_data: RoleAssignment,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """分配角色给用户"""
    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Check role exists
    role = db.query(Role).filter(Role.id == role_data.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )

    # Check if already assigned
    existing = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_data.role_id,
        UserRole.project_id == role_data.project_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该角色已分配"
        )

    # Assign role
    user_role = UserRole(
        user_id=user_id,
        role_id=role_data.role_id,
        project_id=role_data.project_id,
        assigned_by=current_user.id
    )

    db.add(user_role)
    db.commit()

    logger.info(f"Role {role.role_name} assigned to {user.username} by {current_user.username}")

    return {"message": "角色分配成功"}


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    user_id: str,
    role_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """移除用户角色"""
    user_role = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id
    ).first()

    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色分配不存在"
        )

    db.delete(user_role)
    db.commit()

    logger.info(f"Role removed from user {user_id} by {current_user.username}")

    return None


# ==================== Statistics Endpoint ====================

@router.get("/users/stats/summary", response_model=UserStatistics)
async def get_user_statistics(
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """获取用户统计信息"""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    inactive_users = total_users - active_users
    cpa_count = db.query(User).filter(User.is_cpa == True).count()

    # By department
    dept_stats = db.query(
        User.department, func.count(User.id)
    ).filter(
        User.department.isnot(None)
    ).group_by(User.department).all()

    by_department = {dept: count for dept, count in dept_stats if dept}

    # By role
    role_stats = db.query(
        Role.role_name, func.count(UserRole.id)
    ).join(UserRole, UserRole.role_id == Role.id).group_by(Role.role_name).all()

    by_role = {role_name: count for role_name, count in role_stats}

    return UserStatistics(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        by_department=by_department,
        by_role=by_role,
        cpa_count=cpa_count
    )
