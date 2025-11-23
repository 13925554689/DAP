-- ============================================
-- DAP v2.0 Database Schema Enhancement
-- 模板多版本多来源管理 + 手动编辑功能
-- ============================================

-- 1. 创建模板来源表
CREATE TABLE IF NOT EXISTS template_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code VARCHAR(10) UNIQUE NOT NULL,    -- SYS/DXN/ZP/PWC/DTT/EY/KPMG/RSM/CST
    source_name VARCHAR(100) NOT NULL,          -- 系统内置/鼎信诺/中普/普华永道...
    source_type VARCHAR(20) NOT NULL,           -- SYSTEM/VENDOR/FIRM/CUSTOM
    vendor_version VARCHAR(50),                 -- 软件版本号
    logo_path TEXT,                             -- 来源Logo路径
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 扩展workpaper_templates表 (增强版本管理)
ALTER TABLE workpaper_templates ADD COLUMN IF NOT EXISTS
    source_id VARCHAR(36),                      -- 关联template_sources
    template_type VARCHAR(10) NOT NULL DEFAULT 'WP', -- WP/AR/ML/TC
    template_category VARCHAR(10),              -- A/B/L/E/PL/CF/C/M/T/STD/IPO/TAX...
    category_name VARCHAR(50),                  -- 分类中文名
    template_sequence INTEGER,                  -- 同类别下的序号

    -- 版本管理字段
    version_major INTEGER DEFAULT 1,            -- 主版本号
    version_minor INTEGER DEFAULT 0,            -- 次版本号
    version_year INTEGER,                       -- 年度版本
    version_string VARCHAR(20),                 -- 完整版本字符串 V1.0.2024
    full_template_code VARCHAR(100) UNIQUE,     -- 完整模板编号 SYS-WP-A-01-V1.0

    -- 版本继承关系
    parent_template_id VARCHAR(36),             -- 父模板ID(版本继承)
    is_latest_version BOOLEAN DEFAULT TRUE,     -- 是否最新版本
    replaced_by VARCHAR(36),                    -- 被哪个版本替代

    -- 生效期间
    effective_date DATE,                        -- 生效日期
    expiry_date DATE,                           -- 失效日期

    -- 变更日志
    change_log TEXT,                            -- 版本变更日志
    change_summary VARCHAR(500),                -- 变更摘要

    -- 手动编辑相关字段 (新增)
    is_editable BOOLEAN DEFAULT TRUE,           -- 是否允许手动编辑
    is_deletable BOOLEAN DEFAULT TRUE,          -- 是否允许删除
    is_system_locked BOOLEAN DEFAULT FALSE,     -- 系统锁定(内置模板不可删除)
    allow_content_edit BOOLEAN DEFAULT TRUE,    -- 允许编辑内容
    allow_structure_edit BOOLEAN DEFAULT FALSE, -- 允许编辑结构(公式、格式)

    -- 编辑历史
    last_edited_by VARCHAR(36),                 -- 最后编辑人
    last_edited_at TIMESTAMP,                   -- 最后编辑时间
    edit_count INTEGER DEFAULT 0;               -- 编辑次数

-- 3. 创建模板编辑历史表 (新增 - 用于审计追踪)
CREATE TABLE IF NOT EXISTS template_edit_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id VARCHAR(36) NOT NULL,

    -- 编辑信息
    edit_type VARCHAR(20) NOT NULL,             -- CREATE/UPDATE/DELETE/COPY/RESTORE
    edit_action VARCHAR(50),                    -- 具体操作: 修改公式/添加字段/删除行...

    -- 变更内容
    field_changed VARCHAR(100),                 -- 变更的字段
    old_value TEXT,                             -- 旧值
    new_value TEXT,                             -- 新值
    change_description TEXT,                    -- 变更描述

    -- 完整快照 (用于恢复)
    before_snapshot JSONB,                      -- 变更前完整快照
    after_snapshot JSONB,                       -- 变更后完整快照

    -- 编辑人信息
    edited_by VARCHAR(36) NOT NULL,             -- 编辑人ID
    edited_by_name VARCHAR(100),                -- 编辑人姓名
    edit_reason VARCHAR(500),                   -- 编辑原因

    -- 时间戳
    edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 元数据
    ip_address INET,                            -- 编辑IP
    user_agent TEXT                             -- 浏览器信息
);

-- 4. 创建报告附注模板表 (新增)
CREATE TABLE IF NOT EXISTS report_note_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_template_id VARCHAR(36),             -- 关联审计报告模板

    -- 附注信息
    note_number VARCHAR(20) NOT NULL,           -- 附注编号 如: 三、(一)、1
    note_title VARCHAR(200) NOT NULL,           -- 附注标题
    note_level INTEGER DEFAULT 1,               -- 层级 1-一级 2-二级 3-三级
    parent_note_id VARCHAR(36),                 -- 父附注ID
    display_order INTEGER,                      -- 显示顺序

    -- 附注内容
    content_template TEXT,                      -- 内容模板
    content_type VARCHAR(20),                   -- TEXT/TABLE/FORMULA/MIXED
    default_content TEXT,                       -- 默认内容

    -- 数据绑定
    data_source VARCHAR(100),                   -- 数据来源
    data_mapping JSONB,                         -- 数据映射规则

    -- 编辑控制
    is_required BOOLEAN DEFAULT TRUE,           -- 是否必需
    is_editable BOOLEAN DEFAULT TRUE,           -- 是否可编辑
    can_add_subsection BOOLEAN DEFAULT TRUE,    -- 是否允许添加子节
    can_delete BOOLEAN DEFAULT TRUE,            -- 是否可删除

    -- 元数据
    created_by VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 创建模板自定义字段表 (新增 - 支持用户扩展模板)
CREATE TABLE IF NOT EXISTS template_custom_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id VARCHAR(36) NOT NULL,

    -- 字段信息
    field_name VARCHAR(100) NOT NULL,           -- 字段名称
    field_label VARCHAR(200),                   -- 字段标签
    field_type VARCHAR(20) NOT NULL,            -- TEXT/NUMBER/DATE/BOOLEAN/SELECT
    field_category VARCHAR(50),                 -- 字段分类

    -- 字段配置
    default_value TEXT,                         -- 默认值
    validation_rules JSONB,                     -- 验证规则
    options_list JSONB,                         -- 选项列表(用于SELECT类型)

    -- 显示控制
    display_order INTEGER,
    is_visible BOOLEAN DEFAULT TRUE,
    is_required BOOLEAN DEFAULT FALSE,
    placeholder TEXT,                           -- 占位符
    help_text TEXT,                             -- 帮助文本

    -- 元数据
    created_by VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_template_sources_code ON template_sources(source_code);
CREATE INDEX IF NOT EXISTS idx_workpaper_templates_full_code ON workpaper_templates(full_template_code);
CREATE INDEX IF NOT EXISTS idx_workpaper_templates_source ON workpaper_templates(source_id);
CREATE INDEX IF NOT EXISTS idx_workpaper_templates_type ON workpaper_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_workpaper_templates_latest ON workpaper_templates(is_latest_version);
CREATE INDEX IF NOT EXISTS idx_template_edit_history_template ON template_edit_history(template_id);
CREATE INDEX IF NOT EXISTS idx_template_edit_history_edited_by ON template_edit_history(edited_by);
CREATE INDEX IF NOT EXISTS idx_report_note_templates_report ON report_note_templates(report_template_id);
CREATE INDEX IF NOT EXISTS idx_template_custom_fields_template ON template_custom_fields(template_id);

-- 插入默认模板来源
INSERT INTO template_sources (source_code, source_name, source_type, description, display_order) VALUES
('SYS', '系统内置', 'SYSTEM', 'DAP系统标准审计模板', 1),
('DXN', '鼎信诺', 'VENDOR', '鼎信诺审计软件模板库', 10),
('ZP', '中普', 'VENDOR', '中普审计软件模板库', 20),
('PWC', '普华永道', 'FIRM', 'PwC审计底稿模板', 30),
('DTT', '德勤', 'FIRM', 'Deloitte审计底稿模板', 40),
('EY', '安永', 'FIRM', 'Ernst & Young审计底稿模板', 50),
('KPMG', '毕马威', 'FIRM', 'KPMG审计底稿模板', 60),
('RSM', '瑞华', 'FIRM', '瑞华会计师事务所模板', 70),
('CST', '自定义', 'CUSTOM', '用户自定义模板', 999)
ON CONFLICT (source_code) DO NOTHING;

-- 更新时间戳触发器
CREATE OR REPLACE FUNCTION update_template_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_template_sources_timestamp
    BEFORE UPDATE ON template_sources
    FOR EACH ROW EXECUTE FUNCTION update_template_timestamp();

CREATE TRIGGER update_report_note_templates_timestamp
    BEFORE UPDATE ON report_note_templates
    FOR EACH ROW EXECUTE FUNCTION update_template_timestamp();

-- 注释
COMMENT ON TABLE template_sources IS '模板来源表 - 管理不同来源的模板(系统/鼎信诺/中普/四大/自定义)';
COMMENT ON TABLE template_edit_history IS '模板编辑历史表 - 完整的模板变更审计追踪';
COMMENT ON TABLE report_note_templates IS '审计报告附注模板表 - 管理报告附注的结构和内容';
COMMENT ON TABLE template_custom_fields IS '模板自定义字段表 - 支持用户扩展模板字段';

COMMENT ON COLUMN workpaper_templates.full_template_code IS '完整模板编号 格式: {来源}-{类型}-{分类}-{序号}-V{版本} 如: SYS-WP-A-01-V1.0';
COMMENT ON COLUMN workpaper_templates.is_editable IS '是否允许手动编辑 - 控制模板是否可被用户修改';
COMMENT ON COLUMN workpaper_templates.is_system_locked IS '系统锁定 - 内置核心模板不可删除,仅可复制后编辑';
COMMENT ON COLUMN workpaper_templates.allow_structure_edit IS '允许编辑结构 - 是否可修改公式、格式、单元格结构';
