-- ============================================
-- DAP v2.0 Database Schema
-- Module 1: User & Permission Management
-- ============================================

-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    employee_id VARCHAR(50),                   -- 员工工号
    department VARCHAR(100),                   -- 部门
    position VARCHAR(100),                     -- 职位 (审计员/项目经理/合伙人)
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    is_cpa BOOLEAN DEFAULT FALSE,              -- 是否注册会计师
    cpa_certificate_number VARCHAR(50),        -- CPA证书号
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    CONSTRAINT check_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

-- 角色表
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name VARCHAR(50) NOT NULL UNIQUE,
    role_code VARCHAR(20) NOT NULL UNIQUE,     -- auditor/senior/manager/partner
    description TEXT,
    level INTEGER NOT NULL,                    -- 权限级别 1-审计员 2-项目组长 3-项目经理 4-合伙人
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_level CHECK (level BETWEEN 1 AND 4)
);

-- 权限表
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_name VARCHAR(100) NOT NULL UNIQUE,
    permission_code VARCHAR(50) NOT NULL UNIQUE,
    module VARCHAR(50) NOT NULL,               -- 模块: project/workpaper/consolidation/review
    action VARCHAR(20) NOT NULL,               -- 操作: create/read/update/delete/approve
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户-角色关联表 (多对多)
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    project_id UUID,                           -- 可选:特定项目的角色
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by UUID REFERENCES users(id),
    UNIQUE(user_id, role_id, project_id)
);

-- 角色-权限关联表 (多对多)
CREATE TABLE role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_id, permission_id)
);

-- 创建索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_employee_id ON users(employee_id);
CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX idx_user_roles_project_id ON user_roles(project_id);
CREATE INDEX idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX idx_role_permissions_permission_id ON role_permissions(permission_id);

-- 插入默认角色
INSERT INTO roles (role_name, role_code, description, level) VALUES
('审计员', 'auditor', '初级审计人员,负责具体审计工作', 1),
('项目组长', 'senior', '高级审计员,负责审计组管理', 2),
('项目经理', 'manager', '审计项目经理,负责整体项目管理和一级复核', 3),
('合伙人', 'partner', '签字合伙人,负责最终审计意见和风险控制', 4);

-- 插入默认权限
INSERT INTO permissions (permission_name, permission_code, module, action, description) VALUES
-- 项目管理权限
('创建项目', 'project_create', 'project', 'create', '创建新的审计项目'),
('查看项目', 'project_read', 'project', 'read', '查看审计项目信息'),
('编辑项目', 'project_update', 'project', 'update', '编辑审计项目信息'),
('删除项目', 'project_delete', 'project', 'delete', '删除审计项目'),
('项目审批', 'project_approve', 'project', 'approve', '审批项目立项/结案'),

-- 底稿管理权限
('创建底稿', 'workpaper_create', 'workpaper', 'create', '创建审计底稿'),
('查看底稿', 'workpaper_read', 'workpaper', 'read', '查看审计底稿'),
('编辑底稿', 'workpaper_update', 'workpaper', 'update', '编辑审计底稿'),
('删除底稿', 'workpaper_delete', 'workpaper', 'delete', '删除审计底稿'),

-- 复核权限
('一级复核', 'review_level1', 'review', 'approve', '项目组长复核'),
('二级复核', 'review_level2', 'review', 'approve', '项目经理复核'),
('三级复核', 'review_level3', 'review', 'approve', '合伙人复核'),

-- 合并报表权限
('查看合并报表', 'consolidation_read', 'consolidation', 'read', '查看合并报表'),
('编辑抵消分录', 'consolidation_update', 'consolidation', 'update', '编辑抵消分录'),
('生成合并报表', 'consolidation_generate', 'consolidation', 'create', '生成合并报表');

-- 分配默认权限给角色 (审计员 - 基础权限)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.role_code = 'auditor'
AND p.permission_code IN ('project_read', 'workpaper_create', 'workpaper_read', 'workpaper_update', 'consolidation_read');

-- 分配默认权限给角色 (项目组长 - 审计员权限 + 一级复核)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.role_code = 'senior'
AND p.permission_code IN ('project_read', 'project_update', 'workpaper_create', 'workpaper_read', 'workpaper_update', 'workpaper_delete', 'review_level1', 'consolidation_read', 'consolidation_update');

-- 分配默认权限给角色 (项目经理 - 全部权限除签字)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.role_code = 'manager'
AND p.module IN ('project', 'workpaper', 'consolidation')
OR p.permission_code IN ('review_level1', 'review_level2');

-- 分配默认权限给角色 (合伙人 - 全部权限)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.role_code = 'partner';

-- 更新时间戳触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_roles_updated_at BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE users IS '用户表 - 存储审计人员基本信息';
COMMENT ON TABLE roles IS '角色表 - 定义审计组织中的角色层级';
COMMENT ON TABLE permissions IS '权限表 - 定义系统功能权限';
COMMENT ON TABLE user_roles IS '用户角色关联表 - 实现用户与角色的多对多关系';
COMMENT ON TABLE role_permissions IS '角色权限关联表 - 实现角色与权限的多对多关系';
