"""
DAP v2.0 - User Pydantic Schemas
Data validation models for user management
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


# ============= Authentication Schemas =============

class UserRegister(BaseModel):
    """用户注册数据模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, description="密码")
    full_name: str = Field(..., max_length=100, description="姓名")
    employee_id: Optional[str] = Field(None, max_length=50, description="员工工号")
    department: Optional[str] = Field(None, max_length=100, description="部门")
    position: Optional[str] = Field(None, max_length=100, description="职位")
    phone: Optional[str] = Field(None, max_length=20, description="电话")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "zhangsan",
                "email": "zhangsan@example.com",
                "password": "SecurePass@123",
                "full_name": "张三",
                "employee_id": "EMP001",
                "department": "审计部",
                "position": "审计员"
            }
        }


class UserLogin(BaseModel):
    """用户登录数据模型"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "zhangsan",
                "password": "SecurePass@123"
            }
        }


class Token(BaseModel):
    """Token响应模型"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


class TokenRefresh(BaseModel):
    """Token刷新请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class PasswordChange(BaseModel):
    """修改密码数据模型"""
    old_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=8, description="新密码")

    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "OldPass@123",
                "new_password": "NewSecurePass@456"
            }
        }


class PasswordReset(BaseModel):
    """重置密码数据模型"""
    token: str = Field(..., description="重置令牌")
    new_password: str = Field(..., min_length=8, description="新密码")


class PasswordForgot(BaseModel):
    """忘记密码请求"""
    email: EmailStr = Field(..., description="注册邮箱")


# ============= User Response Schemas =============

class RoleSimple(BaseModel):
    """简化的角色信息"""
    id: str
    role_name: str
    role_code: str
    level: int

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """用户信息响应"""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    employee_id: Optional[str]
    department: Optional[str]
    position: Optional[str]
    phone: Optional[str]
    is_active: bool
    is_cpa: bool
    cpa_certificate_number: Optional[str]
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "zhangsan",
                "email": "zhangsan@example.com",
                "full_name": "张三",
                "employee_id": "EMP001",
                "department": "审计部",
                "position": "审计员",
                "phone": "13800138000",
                "is_active": True,
                "is_cpa": False,
                "cpa_certificate_number": None,
                "last_login": "2025-11-23T10:30:00",
                "created_at": "2025-11-20T09:00:00",
                "updated_at": "2025-11-23T10:30:00"
            }
        }


class UserDetailResponse(UserResponse):
    """用户详细信息（包含角色）"""
    roles: List[RoleSimple] = []


class UserListResponse(BaseModel):
    """用户列表项"""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    employee_id: Optional[str]
    department: Optional[str]
    position: Optional[str]
    is_active: bool
    is_cpa: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============= User Update Schemas =============

class UserUpdate(BaseModel):
    """更新用户信息"""
    full_name: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_cpa: Optional[bool] = None
    cpa_certificate_number: Optional[str] = Field(None, max_length=50)

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "张三",
                "department": "审计一部",
                "position": "高级审计员",
                "phone": "13800138000",
                "is_cpa": True,
                "cpa_certificate_number": "CPA20250001"
            }
        }


class UserAdminUpdate(UserUpdate):
    """管理员更新用户信息（包含更多权限）"""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class UserCreate(BaseModel):
    """管理员创建用户"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., max_length=100)
    employee_id: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: bool = True
    role_ids: List[str] = Field(default_factory=list, description="初始角色ID列表")


# ============= Role Assignment Schemas =============

class RoleAssignment(BaseModel):
    """角色分配"""
    role_id: str = Field(..., description="角色ID")
    project_id: Optional[str] = Field(None, description="项目ID（可选，特定项目角色）")

    class Config:
        json_schema_extra = {
            "example": {
                "role_id": "550e8400-e29b-41d4-a716-446655440001",
                "project_id": None
            }
        }


# ============= Statistics Schemas =============

class UserStatistics(BaseModel):
    """用户统计信息"""
    total_users: int = Field(..., description="总用户数")
    active_users: int = Field(..., description="活跃用户数")
    inactive_users: int = Field(..., description="停用用户数")
    by_department: dict = Field(default_factory=dict, description="按部门统计")
    by_role: dict = Field(default_factory=dict, description="按角色统计")
    cpa_count: int = Field(..., description="注册会计师数量")


# ============= Query Schemas =============

class UserQuery(BaseModel):
    """用户查询参数"""
    search: Optional[str] = Field(None, description="搜索关键词（用户名/姓名/员工号）")
    department: Optional[str] = Field(None, description="部门筛选")
    position: Optional[str] = Field(None, description="职位筛选")
    is_active: Optional[bool] = Field(None, description="激活状态筛选")
    is_cpa: Optional[bool] = Field(None, description="是否CPA筛选")
    role_code: Optional[str] = Field(None, description="按角色筛选")
    skip: int = Field(0, ge=0, description="跳过记录数")
    limit: int = Field(20, ge=1, le=100, description="返回记录数")


# ============= Password Policy Schema =============

class PasswordPolicy(BaseModel):
    """密码策略配置"""
    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_special: bool
    special_chars: str
