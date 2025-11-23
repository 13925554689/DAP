-- ============================================
-- DAP v2.0 Database Schema
-- Module 6: Audit Workpaper System
-- ============================================

-- 底稿模板表
CREATE TABLE workpaper_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_code VARCHAR(50) NOT NULL UNIQUE,   -- 模板编号 如: A-CASH
    template_name VARCHAR(200) NOT NULL,         -- 模板名称 如: 货币资金审计底稿
    template_category VARCHAR(50),               -- 分类: ASSET/LIABILITY/EQUITY/INCOME/EXPENSE
    template_type VARCHAR(50),                   -- 底稿类型: LEAD/DETAIL/TEST/MEMO

    -- 模板内容
    excel_template_path TEXT,                    -- Excel模板文件路径
    template_structure JSONB,                    -- 模板结构定义(单元格映射)
    default_index_prefix VARCHAR(10),            -- 默认索引号前缀 如: A

    -- 数据映射
    data_sources JSONB,                          -- 数据源配置(哪些单元格从哪取数)
    formula_definitions JSONB,                   -- 公式定义

    -- 版本控制
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    is_system_template BOOLEAN DEFAULT TRUE,     -- 是否系统内置模板

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id)
);

-- 审计底稿主表
CREATE TABLE workpapers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entities(id),
    template_id UUID REFERENCES workpaper_templates(id),

    -- 底稿信息
    workpaper_code VARCHAR(50) NOT NULL,         -- 底稿编号
    workpaper_name VARCHAR(200) NOT NULL,
    index_number VARCHAR(20),                    -- 索引号 如: A-1-01
    parent_index VARCHAR(20),                    -- 上级索引号

    -- 底稿类型
    workpaper_type VARCHAR(50),                  -- LEAD/DETAIL/TEST/MEMO/SUMMARY
    workpaper_category VARCHAR(50),              -- ASSET/LIABILITY/EQUITY/INCOME/EXPENSE

    -- 责任人
    preparer_id UUID REFERENCES users(id),       -- 编制人
    reviewer_id UUID REFERENCES users(id),       -- 复核人

    -- 状态
    status VARCHAR(20) DEFAULT 'DRAFT',          -- DRAFT/IN_PROGRESS/PENDING_REVIEW/REVIEWED/APPROVED
    completion_percentage INTEGER DEFAULT 0,

    -- 复核信息
    review_level INTEGER DEFAULT 0,              -- 当前复核级别 0-未复核 1-一级 2-二级 3-三级
    review_status VARCHAR(20),                   -- PENDING/APPROVED/REJECTED

    -- 时间戳
    prepared_at TIMESTAMP,
    reviewed_at TIMESTAMP,
    approved_at TIMESTAMP,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    CONSTRAINT check_workpaper_status CHECK (status IN ('DRAFT', 'IN_PROGRESS', 'PENDING_REVIEW', 'REVIEWED', 'APPROVED')),
    UNIQUE(project_id, workpaper_code)
);

-- 底稿单元格数据表 (核心数据存储)
CREATE TABLE workpaper_cells (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workpaper_id UUID NOT NULL REFERENCES workpapers(id) ON DELETE CASCADE,

    -- 单元格位置
    sheet_name VARCHAR(100) DEFAULT 'Sheet1',    -- 工作表名
    cell_address VARCHAR(20) NOT NULL,           -- 单元格地址 如: B5
    row_index INTEGER,
    col_index INTEGER,

    -- 单元格值
    cell_value TEXT,                             -- 单元格值
    cell_type VARCHAR(20),                       -- TEXT/NUMBER/DATE/FORMULA/BOOLEAN
    display_value TEXT,                          -- 显示值(公式计算结果)
    formula TEXT,                                -- 公式内容

    -- 数据来源
    data_source VARCHAR(50),                     -- MANUAL/AUTO/FORMULA/IMPORT
    source_reference TEXT,                       -- 数据来源引用(如: cleaned_balances.closing_balance)

    -- 保护标记
    is_protected BOOLEAN DEFAULT FALSE,          -- 是否锁定
    is_formula_cell BOOLEAN DEFAULT FALSE,       -- 是否公式单元格

    -- 审计追踪
    last_modified_by UUID REFERENCES users(id),
    last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(workpaper_id, sheet_name, cell_address)
);

-- 底稿附件表
CREATE TABLE workpaper_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workpaper_id UUID NOT NULL REFERENCES workpapers(id) ON DELETE CASCADE,

    attachment_name VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    attachment_type VARCHAR(50),                 -- SCAN/DOCUMENT/PHOTO/OTHER

    description TEXT,
    uploaded_by UUID REFERENCES users(id),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 底稿批注表
CREATE TABLE workpaper_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workpaper_id UUID NOT NULL REFERENCES workpapers(id) ON DELETE CASCADE,

    -- 批注位置
    cell_address VARCHAR(20),                    -- 关联单元格
    sheet_name VARCHAR(100),

    -- 批注内容
    comment_type VARCHAR(20) NOT NULL,           -- QUESTION/SUGGESTION/ISSUE/NOTE
    comment_text TEXT NOT NULL,
    priority VARCHAR(10),                        -- HIGH/MEDIUM/LOW

    -- 批注状态
    status VARCHAR(20) DEFAULT 'OPEN',           -- OPEN/RESOLVED/CLOSED
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMP,
    resolution_text TEXT,

    -- 作者
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_comment_type CHECK (comment_type IN ('QUESTION', 'SUGGESTION', 'ISSUE', 'NOTE')),
    CONSTRAINT check_comment_status CHECK (status IN ('OPEN', 'RESOLVED', 'CLOSED'))
);

-- 底稿版本表
CREATE TABLE workpaper_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workpaper_id UUID NOT NULL REFERENCES workpapers(id) ON DELETE CASCADE,

    version_number INTEGER NOT NULL,
    version_name VARCHAR(100),
    version_data JSONB NOT NULL,                 -- 完整底稿数据快照
    change_summary TEXT,                         -- 变更说明

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(workpaper_id, version_number)
);

-- 创建索引
CREATE INDEX idx_workpapers_project_id ON workpapers(project_id);
CREATE INDEX idx_workpapers_status ON workpapers(status);
CREATE INDEX idx_workpapers_preparer_id ON workpapers(preparer_id);
CREATE INDEX idx_workpapers_index_number ON workpapers(index_number);
CREATE INDEX idx_workpaper_cells_workpaper_id ON workpaper_cells(workpaper_id);
CREATE INDEX idx_workpaper_cells_address ON workpaper_cells(cell_address);
CREATE INDEX idx_workpaper_comments_workpaper_id ON workpaper_comments(workpaper_id);
CREATE INDEX idx_workpaper_comments_status ON workpaper_comments(status);
CREATE INDEX idx_workpaper_versions_workpaper_id ON workpaper_versions(workpaper_id);
CREATE INDEX idx_workpaper_attachments_workpaper_id ON workpaper_attachments(workpaper_id);

-- 插入默认模板
INSERT INTO workpaper_templates (template_code, template_name, template_category, template_type, default_index_prefix) VALUES
('LEAD-CASH', '货币资金审定表', 'ASSET', 'LEAD', 'A'),
('LEAD-AR', '应收账款审定表', 'ASSET', 'LEAD', 'B'),
('LEAD-INV', '存货审定表', 'ASSET', 'LEAD', 'C'),
('LEAD-FA', '固定资产审定表', 'ASSET', 'LEAD', 'D'),
('LEAD-AP', '应付账款审定表', 'LIABILITY', 'LEAD', 'AA'),
('LEAD-REVENUE', '营业收入审定表', 'INCOME', 'LEAD', 'PL'),
('LEAD-COST', '营业成本审定表', 'EXPENSE', 'LEAD', 'PL'),
('TEST-CASH', '货币资金测试底稿', 'ASSET', 'TEST', 'A'),
('TEST-AR-CONF', '应收账款函证', 'ASSET', 'TEST', 'B'),
('MEMO-RISK', '风险评估备忘录', NULL, 'MEMO', 'M');

-- 更新时间戳触发器
CREATE TRIGGER update_workpaper_templates_updated_at BEFORE UPDATE ON workpaper_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workpapers_updated_at BEFORE UPDATE ON workpapers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE workpaper_templates IS '底稿模板表 - 审计底稿Excel模板定义';
COMMENT ON TABLE workpapers IS '审计底稿主表 - 每个底稿的基本信息';
COMMENT ON TABLE workpaper_cells IS '底稿单元格表 - 底稿中每个单元格的数据';
COMMENT ON TABLE workpaper_attachments IS '底稿附件表 - 底稿相关附件';
COMMENT ON TABLE workpaper_comments IS '底稿批注表 - 复核意见与问题';
COMMENT ON TABLE workpaper_versions IS '底稿版本表 - 版本控制与历史回溯';
