-- ============================================
-- DAP v2.0 Database Schema
-- Module 7: Consolidation & Elimination
-- 合并报表与抵消分录
-- ============================================

-- 抵消规则表
CREATE TABLE elimination_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code VARCHAR(50) NOT NULL UNIQUE,
    rule_name VARCHAR(200) NOT NULL,
    rule_category VARCHAR(50) NOT NULL,          -- INTERCOMPANY/INVESTMENT/TRANSACTION/UNREALIZED_PROFIT

    -- 规则描述
    description TEXT,
    elimination_type VARCHAR(50),                -- AUTO/SEMI_AUTO/MANUAL

    -- 匹配条件
    matching_criteria JSONB,                     -- 匹配条件配置
    debit_account_pattern VARCHAR(50),           -- 借方科目模式
    credit_account_pattern VARCHAR(50),          -- 贷方科目模式

    -- 抵消分录模板
    entry_template JSONB,                        -- 抵消分录生成模板

    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100,                -- 执行优先级

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 抵消分录表
CREATE TABLE elimination_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    consolidation_id UUID,                       -- 关联合并报表

    -- 抵消信息
    elimination_number VARCHAR(50),              -- 抵消分录编号 如: E-001
    elimination_type VARCHAR(50) NOT NULL,       -- 抵消类型
    elimination_step INTEGER,                    -- 抵消步骤 1-8

    -- 涉及主体
    investor_entity_id UUID REFERENCES entities(id), -- 投资方
    investee_entity_id UUID REFERENCES entities(id), -- 被投资方

    -- 分录信息
    entry_date DATE DEFAULT CURRENT_DATE,
    description TEXT,                            -- 抵消说明

    -- 借方
    debit_account_code VARCHAR(20),
    debit_account_name VARCHAR(200),
    debit_amount DECIMAL(20,2) NOT NULL,

    -- 贷方
    credit_account_code VARCHAR(20),
    credit_account_name VARCHAR(200),
    credit_amount DECIMAL(20,2) NOT NULL,

    -- 来源
    source_type VARCHAR(20) DEFAULT 'AUTO',      -- AUTO/MANUAL
    rule_id UUID REFERENCES elimination_rules(id),
    manually_adjusted BOOLEAN DEFAULT FALSE,
    adjustment_reason TEXT,

    -- 审核状态
    status VARCHAR(20) DEFAULT 'DRAFT',          -- DRAFT/PENDING/APPROVED/REJECTED
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    CONSTRAINT check_entry_status CHECK (status IN ('DRAFT', 'PENDING', 'APPROVED', 'REJECTED')),
    CONSTRAINT check_balance CHECK (debit_amount = credit_amount)
);

-- 合并报表表
CREATE TABLE consolidated_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- 报表信息
    report_name VARCHAR(200) NOT NULL,
    report_type VARCHAR(50) NOT NULL,            -- BALANCE_SHEET/INCOME/CASH_FLOW/EQUITY_CHANGE
    fiscal_year INTEGER NOT NULL,
    fiscal_period INTEGER,                       -- 0=年度 1-12=月度

    -- 报表数据
    report_data JSONB NOT NULL,                  -- 报表数据JSON
    parent_data JSONB,                           -- 母公司数据
    subsidiary_data JSONB,                       -- 子公司汇总数据
    elimination_data JSONB,                      -- 抵消数据
    consolidated_data JSONB,                     -- 合并后数据

    -- 状态
    status VARCHAR(20) DEFAULT 'DRAFT',          -- DRAFT/GENERATED/REVIEWED/APPROVED
    version INTEGER DEFAULT 1,

    -- 审核
    generated_at TIMESTAMP,
    generated_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_report_type CHECK (report_type IN ('BALANCE_SHEET', 'INCOME', 'CASH_FLOW', 'EQUITY_CHANGE'))
);

-- 少数股东权益表
CREATE TABLE minority_interests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id),
    consolidated_report_id UUID REFERENCES consolidated_reports(id),

    -- 期间
    fiscal_year INTEGER NOT NULL,
    fiscal_period INTEGER,

    -- 少数股东比例
    minority_percentage DECIMAL(10,4) NOT NULL,  -- 少数股东持股比例

    -- 少数股东权益明细
    opening_balance DECIMAL(20,2) DEFAULT 0,     -- 期初余额
    share_of_net_profit DECIMAL(20,2) DEFAULT 0, -- 应享有的净利润
    share_of_oci DECIMAL(20,2) DEFAULT 0,        -- 应享有的其他综合收益
    dividends_declared DECIMAL(20,2) DEFAULT 0,  -- 宣告分配的股利
    other_changes DECIMAL(20,2) DEFAULT 0,       -- 其他变动
    closing_balance DECIMAL(20,2) DEFAULT 0,     -- 期末余额

    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(project_id, entity_id, fiscal_year, fiscal_period)
);

-- 内部往来匹配表
CREATE TABLE intercompany_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- 交易双方
    entity_a_id UUID NOT NULL REFERENCES entities(id),
    entity_b_id UUID NOT NULL REFERENCES entities(id),

    -- 交易信息
    transaction_type VARCHAR(50),                -- AR_AP/REVENUE_COST/LOAN/DIVIDEND
    transaction_date DATE,
    description TEXT,

    -- A方记录
    entity_a_account_code VARCHAR(20),
    entity_a_amount DECIMAL(20,2),

    -- B方记录
    entity_b_account_code VARCHAR(20),
    entity_b_amount DECIMAL(20,2),

    -- 匹配状态
    difference_amount DECIMAL(20,2),             -- 差额
    is_matched BOOLEAN DEFAULT FALSE,
    match_status VARCHAR(20) DEFAULT 'UNMATCHED', -- UNMATCHED/MATCHED/ADJUSTED

    -- 抵消分录关联
    elimination_entry_id UUID REFERENCES elimination_entries(id),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_different_entities CHECK (entity_a_id != entity_b_id)
);

-- 创建索引
CREATE INDEX idx_elimination_entries_project_id ON elimination_entries(project_id);
CREATE INDEX idx_elimination_entries_type ON elimination_entries(elimination_type);
CREATE INDEX idx_elimination_entries_status ON elimination_entries(status);
CREATE INDEX idx_consolidated_reports_project_id ON consolidated_reports(project_id);
CREATE INDEX idx_consolidated_reports_type ON consolidated_reports(report_type);
CREATE INDEX idx_minority_interests_project_id ON minority_interests(project_id);
CREATE INDEX idx_intercompany_transactions_project_id ON intercompany_transactions(project_id);
CREATE INDEX idx_intercompany_transactions_entities ON intercompany_transactions(entity_a_id, entity_b_id);

-- 插入默认抵消规则
INSERT INTO elimination_rules (rule_code, rule_name, rule_category, elimination_type, description) VALUES
('RULE-01', '母公司对子公司长期股权投资与子公司所有者权益抵消', 'INVESTMENT', 'AUTO', '第一步:长投与权益抵消'),
('RULE-02', '内部应收应付款项抵消', 'INTERCOMPANY', 'AUTO', '第二步:内部债权债务抵消'),
('RULE-03', '内部商品购销抵消', 'TRANSACTION', 'AUTO', '第三步:内部交易收入成本抵消'),
('RULE-04', '内部固定资产交易抵消', 'TRANSACTION', 'SEMI_AUTO', '第四步:内部固定资产交易抵消'),
('RULE-05', '内部存货未实现利润抵消', 'UNREALIZED_PROFIT', 'SEMI_AUTO', '第五步:存货未实现利润抵消'),
('RULE-06', '内部债券投资与应付债券抵消', 'INTERCOMPANY', 'MANUAL', '第六步:内部债券抵消'),
('RULE-07', '递延所得税调整', 'UNREALIZED_PROFIT', 'MANUAL', '第七步:递延所得税调整'),
('RULE-08', '少数股东权益与损益确认', 'INVESTMENT', 'AUTO', '第八步:少数股东权益确认');

-- 更新触发器
CREATE TRIGGER update_elimination_rules_updated_at BEFORE UPDATE ON elimination_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_elimination_entries_updated_at BEFORE UPDATE ON elimination_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_consolidated_reports_updated_at BEFORE UPDATE ON consolidated_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_minority_interests_updated_at BEFORE UPDATE ON minority_interests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE elimination_rules IS '抵消规则表 - 定义合并报表抵消规则';
COMMENT ON TABLE elimination_entries IS '抵消分录表 - 存储具体的抵消分录';
COMMENT ON TABLE consolidated_reports IS '合并报表表 - 生成的合并财务报表';
COMMENT ON TABLE minority_interests IS '少数股东权益表 - 少数股东权益计算';
COMMENT ON TABLE intercompany_transactions IS '内部往来匹配表 - 集团内部交易匹配';

COMMENT ON COLUMN elimination_entries.elimination_step IS '抵消步骤: 1-长投权益 2-内部往来 3-内部交易 4-固定资产 5-存货利润 6-债券 7-递延税 8-少数股东';
