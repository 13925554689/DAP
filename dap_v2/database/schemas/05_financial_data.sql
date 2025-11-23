-- ============================================
-- DAP v2.0 Database Schema
-- Module 5: Financial Data Storage
-- ============================================

-- 原始凭证表
CREATE TABLE raw_vouchers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES import_history(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    -- 凭证信息
    voucher_number VARCHAR(50),                  -- 凭证号
    voucher_type VARCHAR(20),                    -- 记/收/付/转
    voucher_date DATE NOT NULL,
    fiscal_year INTEGER,
    fiscal_period INTEGER,                       -- 会计期间 1-12

    -- 分录信息
    entry_number INTEGER,                        -- 分录序号
    account_code VARCHAR(50) NOT NULL,           -- 科目代码
    account_name VARCHAR(200),                   -- 科目名称
    auxiliary_accounting JSONB,                  -- 辅助核算(客户/供应商/部门等)
    summary TEXT,                                -- 摘要

    -- 金额
    debit_amount DECIMAL(20,2) DEFAULT 0,        -- 借方金额
    credit_amount DECIMAL(20,2) DEFAULT 0,       -- 贷方金额
    currency VARCHAR(10) DEFAULT 'CNY',
    exchange_rate DECIMAL(10,6) DEFAULT 1,
    original_amount DECIMAL(20,2),               -- 原币金额

    -- 附加信息
    preparer VARCHAR(100),                       -- 制单人
    reviewer VARCHAR(100),                       -- 审核人
    bookkeeper VARCHAR(100),                     -- 记账人
    attachment_count INTEGER DEFAULT 0,          -- 附件数

    -- 数据状态
    is_valid BOOLEAN DEFAULT TRUE,
    validation_errors JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 清洗后凭证表 (映射到标准科目)
CREATE TABLE cleaned_vouchers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_voucher_id UUID REFERENCES raw_vouchers(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    -- 凭证信息 (继承自原始)
    voucher_number VARCHAR(50),
    voucher_type VARCHAR(20),
    voucher_date DATE NOT NULL,
    fiscal_year INTEGER,
    fiscal_period INTEGER,
    entry_number INTEGER,

    -- 标准科目信息
    standard_account_code VARCHAR(20),
    standard_account_name VARCHAR(200),
    account_category VARCHAR(50),                -- 资产/负债/权益/成本/损益

    -- 金额
    debit_amount DECIMAL(20,2) DEFAULT 0,
    credit_amount DECIMAL(20,2) DEFAULT 0,
    currency VARCHAR(10) DEFAULT 'CNY',

    -- 摘要
    summary TEXT,
    auxiliary_accounting JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 原始余额表
CREATE TABLE raw_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES import_history(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    -- 科目信息
    account_code VARCHAR(50) NOT NULL,
    account_name VARCHAR(200),
    account_level INTEGER,

    -- 期间
    fiscal_year INTEGER NOT NULL,
    fiscal_period INTEGER,                       -- 0=年初 1-12=各月
    balance_type VARCHAR(20) DEFAULT 'MONTHLY',  -- OPENING/MONTHLY/CLOSING

    -- 金额
    opening_debit DECIMAL(20,2) DEFAULT 0,       -- 期初借方
    opening_credit DECIMAL(20,2) DEFAULT 0,      -- 期初贷方
    current_debit DECIMAL(20,2) DEFAULT 0,       -- 本期借方发生
    current_credit DECIMAL(20,2) DEFAULT 0,      -- 本期贷方发生
    ytd_debit DECIMAL(20,2) DEFAULT 0,           -- 本年累计借方
    ytd_credit DECIMAL(20,2) DEFAULT 0,          -- 本年累计贷方
    closing_debit DECIMAL(20,2) DEFAULT 0,       -- 期末借方
    closing_credit DECIMAL(20,2) DEFAULT 0,      -- 期末贷方

    currency VARCHAR(10) DEFAULT 'CNY',

    -- 辅助核算余额
    auxiliary_accounting JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 清洗后余额表
CREATE TABLE cleaned_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_balance_id UUID REFERENCES raw_balances(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    -- 标准科目
    standard_account_code VARCHAR(20),
    standard_account_name VARCHAR(200),
    account_category VARCHAR(50),
    account_direction VARCHAR(10),

    -- 期间
    fiscal_year INTEGER NOT NULL,
    fiscal_period INTEGER,
    balance_type VARCHAR(20),

    -- 金额 (净额)
    opening_balance DECIMAL(20,2) DEFAULT 0,     -- 期初余额
    current_debit DECIMAL(20,2) DEFAULT 0,
    current_credit DECIMAL(20,2) DEFAULT 0,
    closing_balance DECIMAL(20,2) DEFAULT 0,     -- 期末余额

    currency VARCHAR(10) DEFAULT 'CNY',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 原始明细表 (辅助核算明细)
CREATE TABLE raw_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES import_history(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    -- 科目
    account_code VARCHAR(50) NOT NULL,
    account_name VARCHAR(200),

    -- 期间
    fiscal_year INTEGER,
    fiscal_period INTEGER,
    detail_date DATE,

    -- 辅助核算类型
    auxiliary_type VARCHAR(50),                  -- CUSTOMER/SUPPLIER/EMPLOYEE/DEPARTMENT/PROJECT
    auxiliary_code VARCHAR(100),
    auxiliary_name VARCHAR(200),

    -- 明细数据
    document_number VARCHAR(100),                -- 单据号
    document_type VARCHAR(50),                   -- 单据类型
    summary TEXT,

    -- 金额
    debit_amount DECIMAL(20,2) DEFAULT 0,
    credit_amount DECIMAL(20,2) DEFAULT 0,
    balance DECIMAL(20,2) DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 清洗后明细表
CREATE TABLE cleaned_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_detail_id UUID REFERENCES raw_details(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    standard_account_code VARCHAR(20),
    standard_account_name VARCHAR(200),

    fiscal_year INTEGER,
    fiscal_period INTEGER,
    detail_date DATE,

    auxiliary_type VARCHAR(50),
    auxiliary_code VARCHAR(100),
    auxiliary_name VARCHAR(200),

    debit_amount DECIMAL(20,2) DEFAULT 0,
    credit_amount DECIMAL(20,2) DEFAULT 0,
    balance DECIMAL(20,2) DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_raw_vouchers_project_id ON raw_vouchers(project_id);
CREATE INDEX idx_raw_vouchers_voucher_date ON raw_vouchers(voucher_date);
CREATE INDEX idx_raw_vouchers_account_code ON raw_vouchers(account_code);
CREATE INDEX idx_raw_vouchers_fiscal_year ON raw_vouchers(fiscal_year);
CREATE INDEX idx_cleaned_vouchers_project_id ON cleaned_vouchers(project_id);
CREATE INDEX idx_cleaned_vouchers_standard_code ON cleaned_vouchers(standard_account_code);
CREATE INDEX idx_raw_balances_project_id ON raw_balances(project_id);
CREATE INDEX idx_raw_balances_account_code ON raw_balances(account_code);
CREATE INDEX idx_cleaned_balances_project_id ON cleaned_balances(project_id);
CREATE INDEX idx_cleaned_balances_standard_code ON cleaned_balances(standard_account_code);
CREATE INDEX idx_raw_details_project_id ON raw_details(project_id);
CREATE INDEX idx_cleaned_details_project_id ON cleaned_details(project_id);

-- 分区建议 (大数据量时按年份分区)
-- CREATE TABLE raw_vouchers_2024 PARTITION OF raw_vouchers FOR VALUES FROM (2024) TO (2025);

-- 注释
COMMENT ON TABLE raw_vouchers IS '原始凭证表 - 导入的原始凭证数据';
COMMENT ON TABLE cleaned_vouchers IS '清洗后凭证表 - 映射到标准科目的凭证';
COMMENT ON TABLE raw_balances IS '原始余额表 - 导入的原始科目余额';
COMMENT ON TABLE cleaned_balances IS '清洗后余额表 - 标准化的科目余额';
COMMENT ON TABLE raw_details IS '原始明细表 - 辅助核算明细数据';
COMMENT ON TABLE cleaned_details IS '清洗后明细表 - 标准化的明细数据';
