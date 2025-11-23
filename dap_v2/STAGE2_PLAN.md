# DAP v2.0 第二阶段开发计划

**日期**: 2025-11-23
**阶段**: 第二阶段 - 用户认证与核心模块
**预计周期**: 1-2周

---

## 一、开发目标

本阶段重点完成用户认证授权系统和核心业务模块的API开发，为前端开发和完整功能打下基础。

### 核心目标:
1. ✅ 完整的JWT用户认证系统
2. ✅ RBAC权限验证中间件
3. ✅ 用户管理完整API
4. ✅ 客户管理完整API
5. ✅ 数据导入映射API
6. ✅ 安全性增强

---

## 二、详细任务分解

### 2.1 用户认证系统 (优先级: 🔴 最高)

#### 任务1: JWT认证实现
**文件**: `backend/auth/jwt_handler.py`

**功能**:
- JWT token生成
- Token验证和解析
- Token刷新机制
- Token黑名单管理

**实现要点**:
```python
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

# 配置
SECRET_KEY = "your-secret-key-here"  # TODO: 使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token生成
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

#### 任务2: 密码处理
**文件**: `backend/auth/password.py`

**功能**:
- 密码强度验证
- 密码hash生成
- 密码验证
- 密码重置token

**实现要点**:
```python
import re
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def validate_password_strength(password: str) -> bool:
    """
    密码强度要求:
    - 至少8个字符
    - 包含大写字母
    - 包含小写字母
    - 包含数字
    - 包含特殊字符
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

#### 任务3: 认证依赖项
**文件**: `backend/auth/dependencies.py`

**功能**:
- 获取当前用户
- 验证用户激活状态
- 验证用户角色
- 验证用户权限

**实现要点**:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(required_roles: List[str]):
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        user_roles = [ur.role.role_code for ur in current_user.roles]
        if not any(role in required_roles for role in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def require_permission(required_permission: str):
    async def permission_checker(current_user: User = Depends(get_current_active_user)):
        # TODO: 检查用户权限
        return current_user
    return permission_checker
```

---

### 2.2 用户管理API (优先级: 🔴 最高)

#### 文件: `backend/api/users.py`

**端点规划**:

```python
router = APIRouter(tags=["Users"])

# 认证相关
@router.post("/auth/register")  # 用户注册
@router.post("/auth/login")  # 用户登录
@router.post("/auth/refresh")  # 刷新token
@router.post("/auth/logout")  # 退出登录
@router.post("/auth/forgot-password")  # 忘记密码
@router.post("/auth/reset-password")  # 重置密码

# 用户管理
@router.get("/users")  # 获取用户列表（需要manager以上权限）
@router.post("/users")  # 创建用户（需要manager以上权限）
@router.get("/users/me")  # 获取当前用户信息
@router.put("/users/me")  # 更新当前用户信息
@router.put("/users/me/password")  # 修改密码
@router.get("/users/{user_id}")  # 获取指定用户详情
@router.put("/users/{user_id}")  # 更新用户信息（需要manager以上权限）
@router.delete("/users/{user_id}")  # 删除用户（需要partner权限）
@router.post("/users/{user_id}/activate")  # 激活用户
@router.post("/users/{user_id}/deactivate")  # 停用用户

# 角色管理
@router.get("/users/{user_id}/roles")  # 获取用户角色
@router.post("/users/{user_id}/roles")  # 分配角色
@router.delete("/users/{user_id}/roles/{role_id}")  # 移除角色
```

**Pydantic Schemas**:

```python
# backend/schemas/user.py

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None

class UserResponse(BaseModel):
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

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
    is_cpa: Optional[bool] = None
    cpa_certificate_number: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)
```

---

### 2.3 客户管理API (优先级: 🟡 高)

#### 文件: `backend/api/clients.py`

**端点规划**:

```python
router = APIRouter(tags=["Clients"])

# 客户主体管理
@router.get("/clients")  # 获取客户列表
@router.post("/clients")  # 创建客户
@router.get("/clients/{client_id}")  # 获取客户详情
@router.put("/clients/{client_id}")  # 更新客户信息
@router.delete("/clients/{client_id}")  # 删除客户

# 客户实体管理
@router.get("/clients/{client_id}/entities")  # 获取客户实体列表
@router.post("/clients/{client_id}/entities")  # 添加客户实体
@router.get("/clients/{client_id}/entities/{entity_id}")  # 获取实体详情
@router.put("/clients/{client_id}/entities/{entity_id}")  # 更新实体信息
@router.delete("/clients/{client_id}/entities/{entity_id}")  # 删除实体

# 实体关系管理
@router.get("/clients/{client_id}/relationships")  # 获取实体关系图
@router.post("/clients/{client_id}/relationships")  # 创建实体关系
@router.delete("/relationships/{relationship_id}")  # 删除关系

# 联系人管理
@router.get("/clients/{client_id}/contacts")  # 获取联系人列表
@router.post("/clients/{client_id}/contacts")  # 添加联系人
@router.put("/contacts/{contact_id}")  # 更新联系人
@router.delete("/contacts/{contact_id}")  # 删除联系人

# 客户档案
@router.get("/clients/{client_id}/profile")  # 获取完整客户档案
@router.get("/clients/{client_id}/projects")  # 获取客户历史项目
```

**Models** (已存在，需验证):
- Client (客户主体)
- ClientEntity (客户实体)
- EntityRelationship (实体关系)
- ContactPerson (联系人)

**Pydantic Schemas**:

```python
# backend/schemas/client.py

class ClientCreate(BaseModel):
    client_name: str
    client_code: str
    unified_social_credit_code: Optional[str] = None
    industry: str
    company_type: str
    registered_capital: Optional[Decimal] = None
    establishment_date: Optional[date] = None
    legal_representative: Optional[str] = None
    registered_address: Optional[str] = None
    business_scope: Optional[str] = None
    is_listed: bool = False
    stock_code: Optional[str] = None
    stock_exchange: Optional[str] = None

class ClientUpdate(BaseModel):
    # 所有字段可选
    ...

class ClientResponse(BaseModel):
    id: str
    client_name: str
    client_code: str
    industry: str
    company_type: str
    is_listed: bool
    created_at: datetime
    # 关联统计
    entity_count: Optional[int] = 0
    project_count: Optional[int] = 0

class ClientEntityCreate(BaseModel):
    entity_name: str
    entity_code: str
    entity_type: str  # subsidiary/parent/related
    holding_ratio: Optional[Decimal] = None
    is_consolidated: bool = False

class EntityRelationshipCreate(BaseModel):
    parent_entity_id: str
    child_entity_id: str
    relationship_type: str  # wholly_owned/controlled/joint_venture/associated
    holding_ratio: Decimal
    is_direct: bool = True
```

---

### 2.4 数据导入映射API (优先级: 🟢 中)

#### 文件: `backend/api/data_import.py`

**端点规划**:

```python
router = APIRouter(tags=["Data Import"])

# 导入模板管理
@router.get("/import/templates")  # 获取导入模板列表
@router.post("/import/templates")  # 创建导入模板
@router.get("/import/templates/{template_id}")  # 获取模板详情
@router.put("/import/templates/{template_id}")  # 更新模板
@router.delete("/import/templates/{template_id}")  # 删除模板

# 字段映射配置
@router.get("/import/templates/{template_id}/mappings")  # 获取字段映射
@router.post("/import/templates/{template_id}/mappings")  # 创建映射
@router.put("/mappings/{mapping_id}")  # 更新映射
@router.delete("/mappings/{mapping_id}")  # 删除映射

# 数据导入历史
@router.get("/import/history")  # 获取导入历史
@router.get("/import/history/{import_id}")  # 获取导入详情
@router.post("/import/history/{import_id}/rollback")  # 回滚导入

# 数据验证规则
@router.get("/import/validation-rules")  # 获取验证规则
@router.post("/import/validation-rules")  # 创建验证规则
```

---

### 2.5 安全性增强 (优先级: 🟡 高)

#### 任务1: 配置管理
**文件**: `backend/config.py`

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "DAP Audit System v2.0"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./dap_v2.db"

    # Security
    SECRET_KEY: str  # 必须设置
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:8080"]

    # Email (for password reset)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

#### 任务2: 环境变量配置
**文件**: `backend/.env.example`

```env
# Application
DEBUG=false

# Database
DATABASE_URL=sqlite:///./dap_v2.db
# DATABASE_URL=postgresql://user:password@localhost:5432/dap_db

# Security (生成随机密钥: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your-secret-key-here-change-in-production

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-app-password
```

#### 任务3: 请求日志中间件
**文件**: `backend/middleware/logging_middleware.py`

```python
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.time()

        # Log request
        logger.info(f"[{request_id}] {request.method} {request.url.path}")

        response = await call_next(request)

        process_time = time.time() - start_time

        # Log response
        logger.info(
            f"[{request_id}] Status: {response.status_code} "
            f"Duration: {process_time:.3f}s"
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        return response
```

#### 任务4: 异常处理中间件
**文件**: `backend/middleware/exception_middleware.py`

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "message": "请求数据验证失败"
        }
    )

async def integrity_exception_handler(request: Request, exc: IntegrityError):
    logger.error(f"Database integrity error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "数据完整性约束冲突",
            "message": "可能存在重复数据或外键约束违反"
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "服务器内部错误",
            "message": "请联系管理员"
        }
    )
```

---

## 三、依赖包更新

需要添加到 `requirements.txt`:

```txt
# 已有依赖
fastapi==0.121.3
uvicorn[standard]==0.34.0
sqlalchemy==2.0.44
pydantic==2.12.4
pydantic-settings==2.7.1

# 新增依赖 - 认证相关
python-jose[cryptography]==3.3.0  # JWT处理
passlib[bcrypt]==1.7.4  # 密码加密
python-multipart==0.0.18  # 表单数据处理

# 新增依赖 - 邮件
aiosmtplib==3.0.2  # 异步SMTP
email-validator==2.2.0  # 邮箱验证

# 开发依赖
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.27.2  # 测试客户端
```

---

## 四、数据库更新

### 需要添加的表:

1. **token_blacklist** (Token黑名单)
```sql
CREATE TABLE token_blacklist (
    id TEXT PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    user_id TEXT REFERENCES users(id),
    revoked_at DATETIME DEFAULT (datetime('now')),
    expires_at DATETIME NOT NULL
);
CREATE INDEX idx_token_blacklist_token ON token_blacklist(token);
CREATE INDEX idx_token_blacklist_expires ON token_blacklist(expires_at);
```

2. **password_reset_tokens** (密码重置token)
```sql
CREATE TABLE password_reset_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    token TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT (datetime('now')),
    expires_at DATETIME NOT NULL,
    used BOOLEAN DEFAULT 0
);
CREATE INDEX idx_reset_tokens_token ON password_reset_tokens(token);
```

3. **login_history** (登录历史)
```sql
CREATE TABLE login_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    login_time DATETIME DEFAULT (datetime('now')),
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT 1,
    failure_reason VARCHAR(255)
);
CREATE INDEX idx_login_history_user ON login_history(user_id);
CREATE INDEX idx_login_history_time ON login_history(login_time);
```

---

## 五、开发顺序

### Week 1:

**Day 1-2**: 用户认证系统
- [ ] JWT工具实现
- [ ] 密码处理工具
- [ ] 认证依赖项
- [ ] 添加认证相关表

**Day 3-4**: 用户管理API
- [ ] 用户注册/登录
- [ ] Token刷新机制
- [ ] 用户CRUD端点
- [ ] 密码修改功能
- [ ] 角色分配功能

**Day 5**: 权限验证
- [ ] 角色验证装饰器
- [ ] 权限验证装饰器
- [ ] 更新现有API添加权限控制

### Week 2:

**Day 1-2**: 客户管理API
- [ ] 客户CRUD端点
- [ ] 客户实体管理
- [ ] 实体关系管理
- [ ] 联系人管理

**Day 3**: 数据导入API
- [ ] 导入模板管理
- [ ] 字段映射配置
- [ ] 导入历史记录

**Day 4**: 安全性增强
- [ ] 配置管理
- [ ] 中间件集成
- [ ] 异常处理优化
- [ ] 日志系统完善

**Day 5**: 测试与文档
- [ ] 单元测试编写
- [ ] API文档完善
- [ ] Postman集合导出
- [ ] 部署文档

---

## 六、测试计划

### 6.1 单元测试

**文件**: `tests/test_auth.py`

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_user_register():
    response = client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "Test@1234",
        "full_name": "Test User"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"

def test_user_login():
    response = client.post("/api/auth/login", data={
        "username": "testuser",
        "password": "Test@1234"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_get_current_user():
    # 先登录获取token
    login_response = client.post("/api/auth/login", data={
        "username": "testuser",
        "password": "Test@1234"
    })
    token = login_response.json()["access_token"]

    # 使用token访问保护端点
    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"

def test_unauthorized_access():
    response = client.get("/api/users/me")
    assert response.status_code == 401
```

### 6.2 集成测试

**文件**: `tests/test_users_api.py`

```python
def test_create_user_requires_manager_role():
    # 使用普通用户token尝试创建用户
    response = client.post(
        "/api/users",
        json={"username": "newuser", ...},
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert response.status_code == 403

def test_manager_can_create_user():
    # 使用manager token创建用户
    response = client.post(
        "/api/users",
        json={"username": "newuser", ...},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 201
```

---

## 七、API文档规范

### 7.1 端点注释规范

```python
@router.post("/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    用户登录

    **参数**:
    - `username`: 用户名
    - `password`: 密码

    **返回**:
    - `access_token`: 访问令牌（有效期30分钟）
    - `refresh_token`: 刷新令牌（有效期7天）
    - `token_type`: 令牌类型（bearer）

    **错误**:
    - `401`: 用户名或密码错误
    - `400`: 用户已停用

    **示例**:
    ```json
    {
        "access_token": "eyJhbGc...",
        "refresh_token": "eyJhbGc...",
        "token_type": "bearer"
    }
    ```
    """
    # 实现...
```

---

## 八、验收标准

### 8.1 功能验收
- [ ] 所有API端点正常响应
- [ ] JWT认证正常工作
- [ ] 权限验证正确执行
- [ ] 数据验证正确
- [ ] 错误处理完善

### 8.2 性能验收
- [ ] API响应时间 < 200ms
- [ ] 支持100并发用户
- [ ] 数据库查询优化

### 8.3 安全验收
- [ ] 密码正确加密
- [ ] JWT token安全
- [ ] SQL注入防护
- [ ] XSS防护
- [ ] CSRF防护

### 8.4 文档验收
- [ ] API文档完整
- [ ] 代码注释充分
- [ ] README更新
- [ ] 部署指南

---

## 九、风险管理

### 潜在风险:
1. **JWT密钥泄露** → 使用环境变量+定期轮换
2. **密码破解** → 强制密码强度+限制登录尝试
3. **Token滥用** → Token黑名单机制
4. **性能问题** → 数据库索引优化+缓存

---

## 十、下一步行动

立即开始:
1. 安装新依赖包
2. 创建auth目录结构
3. 实现JWT工具函数
4. 创建用户认证端点
5. 编写测试用例

---

**计划制定人**: Claude Code
**计划日期**: 2025-11-23
**目标完成日期**: 2025-12-06
