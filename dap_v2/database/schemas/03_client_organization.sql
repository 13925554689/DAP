-- ============================================
-- DAP v2.0 Database Schema
-- Module 3: Client & Organization Structure
-- (合并报表核心模块)
-- ============================================

-- 客户公司表
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_code VARCHAR(50) NOT NULL UNIQUE,    -- 客户编号
    client_name VARCHAR(200) NOT NULL,
    english_name VARCHAR(200),
    short_name VARCHAR(100),

    -- 公司类型
    company_type VARCHAR(50),                    -- 上市公司/拟上市/非上市/国企/外企
    industry VARCHAR(100),                       -- 行业分类
    listing_status VARCHAR(50),                  -- LISTED/PRE_IPO/PRIVATE
    stock_code VARCHAR(20),                      -- 股票代码

    -- 注册信息
    unified_social_credit_code VARCHAR(50),      -- 统一社会信用代码
    registration_number VARCHAR(50),             -- 工商注册号
    legal_representative VARCHAR(100),           -- 法定代表人
    registered_capital DECIMAL(20,2),            -- 注册资本
    establishment_date DATE,                     -- 成立日期
    registered_address TEXT,

    -- 联系信息
    business_address TEXT,
    contact_person VARCHAR(100),
    contact_phone VARCHAR(50),
    contact_email VARCHAR(100),
    website VARCHAR(200),

    -- 财务信息
    fiscal_year_end VARCHAR(10),                 -- 会计年度结束月日 如: 12-31
    accounting_standard VARCHAR(50),             -- 会计准则: CAS/IFRS/US GAAP
    reporting_currency VARCHAR(10) DEFAULT 'CNY', -- 报告货币

    -- 客户风险评估
    risk_rating VARCHAR(20),                     -- LOW/MEDIUM/HIGH/CRITICAL
    is_group_client BOOLEAN DEFAULT FALSE,       -- 是否集团客户
    parent_client_id UUID REFERENCES clients(id), -- 所属集团(如果是子客户)

    -- 业务关系
    first_engagement_date DATE,                  -- 首次业务日期
    is_active BOOLEAN DEFAULT TRUE,
    inactive_reason TEXT,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

-- 被审计主体表 (母公司+所有子公司)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    entity_code VARCHAR(50) NOT NULL,            -- 主体编号
    entity_name VARCHAR(200) NOT NULL,
    english_name VARCHAR(200),

    -- 主体类型
    entity_type VARCHAR(50) NOT NULL,            -- PARENT/SUBSIDIARY/ASSOCIATE/JV
    is_parent BOOLEAN DEFAULT FALSE,             -- 是否母公司
    parent_entity_id UUID REFERENCES entities(id), -- 母公司ID

    -- 注册信息
    unified_social_credit_code VARCHAR(50),
    legal_representative VARCHAR(100),
    registered_capital DECIMAL(20,2),
    registered_capital_currency VARCHAR(10) DEFAULT 'CNY',
    establishment_date DATE,
    registered_address TEXT,

    -- 财务信息
    functional_currency VARCHAR(10),             -- 记账本位币
    fiscal_year_end VARCHAR(10),
    accounting_standard VARCHAR(50),

    -- 业务信息
    main_business TEXT,                          -- 主营业务
    industry VARCHAR(100),

    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'OPERATING',      -- OPERATING/CLOSED/LIQUIDATING

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    CONSTRAINT check_entity_type CHECK (entity_type IN ('PARENT', 'SUBSIDIARY', 'ASSOCIATE', 'JV')),
    CONSTRAINT check_entity_status CHECK (status IN ('OPERATING', 'CLOSED', 'LIQUIDATING')),
    UNIQUE(client_id, entity_code)
);

-- 股权关系表 (合并报表关键)
CREATE TABLE equity_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    project_id UUID REFERENCES projects(id),     -- 关联审计项目

    -- 投资方与被投资方
    investor_entity_id UUID NOT NULL REFERENCES entities(id), -- 投资方(母公司)
    investee_entity_id UUID NOT NULL REFERENCES entities(id), -- 被投资方(子公司)

    -- 股权比例
    ownership_percentage DECIMAL(10,4) NOT NULL, -- 持股比例 如: 51.00
    voting_rights_percentage DECIMAL(10,4),      -- 表决权比例(可能不同于持股比例)

    -- 股权性质
    equity_type VARCHAR(50),                     -- DIRECT/INDIRECT
    control_type VARCHAR(50),                    -- FULL/CONTROLLING/SIGNIFICANT/NONE

    -- 投资信息
    investment_date DATE,                        -- 投资日期
    investment_cost DECIMAL(20,2),               -- 投资成本
    investment_cost_currency VARCHAR(10),

    -- 权益法相关
    is_equity_method BOOLEAN DEFAULT FALSE,      -- 是否采用权益法核算

    -- 合并相关
    consolidation_method VARCHAR(50),            -- FULL/PARTIAL/EQUITY/NONE
    is_in_consolidation_scope BOOLEAN DEFAULT TRUE, -- 是否纳入合并范围
    exclusion_reason TEXT,                       -- 不纳入合并原因

    -- 层级信息(用于多层级集团)
    relationship_level INTEGER DEFAULT 1,        -- 层级: 1-直接子公司 2-二级子公司 ...
    relationship_path TEXT,                      -- 股权路径 如: "A->B->C"

    -- 审批信息
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP,

    -- 生效期间
    effective_from DATE NOT NULL,
    effective_to DATE,                           -- NULL表示持续有效
    is_active BOOLEAN DEFAULT TRUE,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    CONSTRAINT check_ownership CHECK (ownership_percentage >= 0 AND ownership_percentage <= 100),
    CONSTRAINT check_voting_rights CHECK (voting_rights_percentage IS NULL OR (voting_rights_percentage >= 0 AND voting_rights_percentage <= 100)),
    CONSTRAINT check_not_self_investment CHECK (investor_entity_id != investee_entity_id),
    CONSTRAINT check_consolidation_method CHECK (consolidation_method IN ('FULL', 'PARTIAL', 'EQUITY', 'NONE') OR consolidation_method IS NULL)
);

-- 合并范围表 (每个项目的合并范围)
CREATE TABLE consolidation_scope (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id),

    -- 合并判断
    is_included BOOLEAN DEFAULT TRUE,            -- 是否纳入合并范围
    inclusion_reason TEXT,                       -- 纳入理由
    exclusion_reason TEXT,                       -- 排除理由

    -- 控制判断
    control_assessment TEXT,                     -- 控制评估说明
    has_control BOOLEAN,                         -- 是否具有控制权
    control_evidence TEXT,                       -- 控制证据

    -- 合并方法
    consolidation_method VARCHAR(50),            -- FULL/EQUITY

    -- 合并期间
    consolidation_from DATE,                     -- 合并起始日
    consolidation_to DATE,                       -- 合并结束日(如有)

    -- 审核信息
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    UNIQUE(project_id, entity_id)
);

-- 创建索引
CREATE INDEX idx_clients_client_code ON clients(client_code);
CREATE INDEX idx_clients_is_active ON clients(is_active);
CREATE INDEX idx_clients_parent_client_id ON clients(parent_client_id);
CREATE INDEX idx_entities_client_id ON entities(client_id);
CREATE INDEX idx_entities_entity_code ON entities(entity_code);
CREATE INDEX idx_entities_parent_entity_id ON entities(parent_entity_id);
CREATE INDEX idx_entities_is_parent ON entities(is_parent);
CREATE INDEX idx_equity_relations_investor ON equity_relations(investor_entity_id);
CREATE INDEX idx_equity_relations_investee ON equity_relations(investee_entity_id);
CREATE INDEX idx_equity_relations_client_id ON equity_relations(client_id);
CREATE INDEX idx_equity_relations_project_id ON equity_relations(project_id);
CREATE INDEX idx_consolidation_scope_project_id ON consolidation_scope(project_id);
CREATE INDEX idx_consolidation_scope_entity_id ON consolidation_scope(entity_id);

-- 更新时间戳触发器
CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entities_updated_at BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_equity_relations_updated_at BEFORE UPDATE ON equity_relations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_consolidation_scope_updated_at BEFORE UPDATE ON consolidation_scope
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE clients IS '客户公司表 - 审计客户主体信息';
COMMENT ON TABLE entities IS '被审计主体表 - 母公司及所有子公司实体';
COMMENT ON TABLE equity_relations IS '股权关系表 - 投资方与被投资方的股权关系';
COMMENT ON TABLE consolidation_scope IS '合并范围表 - 每个审计项目的合并范围确定';

COMMENT ON COLUMN entities.entity_type IS 'PARENT-母公司 SUBSIDIARY-子公司 ASSOCIATE-联营企业 JV-合营企业';
COMMENT ON COLUMN equity_relations.control_type IS 'FULL-全资 CONTROLLING-控制 SIGNIFICANT-重大影响 NONE-无控制';
COMMENT ON COLUMN equity_relations.consolidation_method IS 'FULL-全面合并 PARTIAL-比例合并 EQUITY-权益法 NONE-不合并';
COMMENT ON COLUMN equity_relations.relationship_level IS '股权层级: 1-直接投资 2-间接二级 3-间接三级...';
