-- ============================================
-- DAP v2.0 Database Schema
-- Module 2: Project Management (中普模式)
-- ============================================

-- 项目类型表
CREATE TABLE project_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_code VARCHAR(20) NOT NULL UNIQUE,      -- IPO/ANNUAL/FINANCIAL/TAX/SPECIAL
    type_name VARCHAR(50) NOT NULL,             -- IPO审计/年报审计/财务审计/税务审计/专项审计
    description TEXT,
    default_workflow JSONB,                     -- 默认审计流程配置
    required_workpapers JSONB,                  -- 必需底稿清单
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 审计项目主表
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_code VARCHAR(50) NOT NULL UNIQUE,   -- 项目编号 如: IPO-2024-001
    project_name VARCHAR(200) NOT NULL,
    project_type_id UUID NOT NULL REFERENCES project_types(id),
    client_id UUID NOT NULL,                    -- 关联客户表(待创建)

    -- 项目时间
    fiscal_year INTEGER NOT NULL,               -- 会计年度
    fiscal_period VARCHAR(20),                  -- 会计期间 如: 2024-01-01至2024-12-31
    start_date DATE NOT NULL,
    end_date DATE,
    expected_completion_date DATE,
    actual_completion_date DATE,

    -- 项目状态
    status VARCHAR(20) NOT NULL DEFAULT 'PLANNING',  -- PLANNING/IN_PROGRESS/REVIEW/COMPLETED/ARCHIVED
    risk_level VARCHAR(20) DEFAULT 'MEDIUM',    -- LOW/MEDIUM/HIGH/CRITICAL

    -- 审计范围
    audit_scope TEXT,                           -- 审计范围描述
    is_group_audit BOOLEAN DEFAULT FALSE,       -- 是否集团审计
    consolidation_required BOOLEAN DEFAULT FALSE, -- 是否需要合并报表

    -- 重要性水平
    materiality_amount DECIMAL(20,2),           -- 重要性水平金额
    performance_materiality DECIMAL(20,2),      -- 实际执行的重要性

    -- 技术委员会审批
    tc_required BOOLEAN DEFAULT FALSE,          -- 是否需要技术委员会审批
    tc_status VARCHAR(20),                      -- PENDING/APPROVED/REJECTED
    tc_approved_at TIMESTAMP,
    tc_approved_by UUID REFERENCES users(id),
    tc_comments TEXT,

    -- 项目负责人
    partner_id UUID REFERENCES users(id),       -- 签字合伙人
    manager_id UUID REFERENCES users(id),       -- 项目经理
    senior_id UUID REFERENCES users(id),        -- 项目组长

    -- 审计意见
    audit_opinion VARCHAR(50),                  -- 无保留意见/保留意见/否定意见/无法表示意见
    opinion_issued_date DATE,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),

    CONSTRAINT check_status CHECK (status IN ('PLANNING', 'IN_PROGRESS', 'REVIEW', 'COMPLETED', 'ARCHIVED')),
    CONSTRAINT check_risk_level CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT check_tc_status CHECK (tc_status IN ('PENDING', 'APPROVED', 'REJECTED') OR tc_status IS NULL)
);

-- 审计组表
CREATE TABLE audit_teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    team_name VARCHAR(100) NOT NULL,
    team_code VARCHAR(50),                      -- 审计组编号
    description TEXT,
    is_main_team BOOLEAN DEFAULT TRUE,          -- 是否主审计组(集团审计时可能有多个组)
    entity_id UUID,                             -- 负责的被审计主体(关联entities表)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, team_code)
);

-- 审计组成员表
CREATE TABLE team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES audit_teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    role_in_team VARCHAR(50) NOT NULL,          -- PARTNER/MANAGER/SENIOR/STAFF
    assignment_date DATE DEFAULT CURRENT_DATE,
    estimated_hours DECIMAL(8,2),               -- 预计工时
    actual_hours DECIMAL(8,2),                  -- 实际工时
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, user_id)
);

-- 项目里程碑表
CREATE TABLE project_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_name VARCHAR(100) NOT NULL,
    milestone_type VARCHAR(50),                 -- PLANNING/FIELDWORK/REVIEW/REPORTING/DELIVERY
    planned_date DATE,
    actual_date DATE,
    status VARCHAR(20) DEFAULT 'PENDING',       -- PENDING/IN_PROGRESS/COMPLETED/DELAYED
    responsible_user_id UUID REFERENCES users(id),
    deliverables TEXT,                          -- 可交付成果
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_milestone_status CHECK (status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'DELAYED'))
);

-- 项目文档表
CREATE TABLE project_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_name VARCHAR(200) NOT NULL,
    document_type VARCHAR(50),                  -- ENGAGEMENT_LETTER/PLAN/REPORT/MEMO
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    version INTEGER DEFAULT 1,
    is_final BOOLEAN DEFAULT FALSE,
    uploaded_by UUID REFERENCES users(id),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- 项目沟通记录表
CREATE TABLE project_communications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    communication_type VARCHAR(50),             -- MEETING/EMAIL/PHONE/DOCUMENT
    subject VARCHAR(200),
    content TEXT,
    participants JSONB,                         -- 参与人员列表
    communication_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    follow_up_required BOOLEAN DEFAULT FALSE,
    follow_up_date DATE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_projects_project_code ON projects(project_code);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_fiscal_year ON projects(fiscal_year);
CREATE INDEX idx_projects_client_id ON projects(client_id);
CREATE INDEX idx_projects_partner_id ON projects(partner_id);
CREATE INDEX idx_projects_manager_id ON projects(manager_id);
CREATE INDEX idx_audit_teams_project_id ON audit_teams(project_id);
CREATE INDEX idx_team_members_team_id ON team_members(team_id);
CREATE INDEX idx_team_members_user_id ON team_members(user_id);
CREATE INDEX idx_project_milestones_project_id ON project_milestones(project_id);
CREATE INDEX idx_project_milestones_status ON project_milestones(status);
CREATE INDEX idx_project_documents_project_id ON project_documents(project_id);
CREATE INDEX idx_project_communications_project_id ON project_communications(project_id);

-- 插入默认项目类型
INSERT INTO project_types (type_code, type_name, description) VALUES
('IPO', 'IPO审计', '首次公开发行(IPO)专项审计,需要技术委员会审批'),
('ANNUAL', '年报审计', '年度财务报表审计,上市公司或大型企业'),
('FINANCIAL', '财务审计', '一般财务报表审计'),
('TAX', '税务审计', '税务合规性审计与鉴证'),
('SPECIAL', '专项审计', '特殊目的审计项目');

-- 更新时间戳触发器
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE project_types IS '项目类型表 - 定义不同类型的审计项目';
COMMENT ON TABLE projects IS '审计项目主表 - 核心项目信息管理';
COMMENT ON TABLE audit_teams IS '审计组表 - 项目审计团队组织';
COMMENT ON TABLE team_members IS '审计组成员表 - 团队成员与角色';
COMMENT ON TABLE project_milestones IS '项目里程碑表 - 项目关键节点跟踪';
COMMENT ON TABLE project_documents IS '项目文档表 - 项目相关文档管理';
COMMENT ON TABLE project_communications IS '项目沟通记录表 - 沟通历史追踪';

COMMENT ON COLUMN projects.tc_required IS '是否需要技术委员会审批 - IPO等高风险项目必须';
COMMENT ON COLUMN projects.materiality_amount IS '重要性水平 - 审计重要性判断基准';
COMMENT ON COLUMN projects.audit_opinion IS '审计意见类型 - 最终出具的审计结论';
