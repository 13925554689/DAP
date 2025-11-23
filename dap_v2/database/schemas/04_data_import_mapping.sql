-- ============================================
-- DAP v2.0 Database Schema
-- Module 4: Data Import & Account Mapping
-- ============================================

-- 源系统类型表
CREATE TABLE source_systems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(50) NOT NULL UNIQUE,     -- KINGDEE/UFIDA/SAP/EXCEL
    system_name VARCHAR(100) NOT NULL,           -- 金蝶/用友/SAP/Excel
    system_version VARCHAR(50),                  -- K3 Cloud/U8+/S4HANA
    file_formats JSONB,                          -- 支持的文件格式
    parser_class VARCHAR(200),                   -- 解析器类名
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 标准科目表 (企业会计准则)
CREATE TABLE account_standard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_code VARCHAR(20) NOT NULL,           -- 标准科目代码
    account_name VARCHAR(200) NOT NULL,          -- 标准科目名称
    account_level INTEGER NOT NULL,              -- 科目级次 1-一级 2-二级...
    parent_code VARCHAR(20),                     -- 上级科目代码
    account_category VARCHAR(50) NOT NULL,       -- 资产/负债/权益/成本/损益
    account_direction VARCHAR(10),               -- DEBIT/CREDIT 借方/贷方
    is_leaf BOOLEAN DEFAULT TRUE,                -- 是否末级科目
    report_item VARCHAR(100),                    -- 对应报表项目
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_code)
);

-- 数据导入历史表
CREATE TABLE import_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),      -- 被审计主体

    -- 导入信息
    import_type VARCHAR(50) NOT NULL,            -- VOUCHER/BALANCE/DETAIL/ALL
    source_system_id UUID REFERENCES source_systems(id),
    file_name VARCHAR(500),
    file_path TEXT,
    file_size BIGINT,
    file_hash VARCHAR(64),                       -- 文件MD5校验

    -- 导入结果
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING/PROCESSING/SUCCESS/FAILED/PARTIAL
    total_records INTEGER,
    success_records INTEGER,
    failed_records INTEGER,
    error_log TEXT,

    -- 数据期间
    fiscal_year INTEGER,
    period_from DATE,
    period_to DATE,

    -- 处理时间
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    CONSTRAINT check_import_status CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'PARTIAL'))
);

-- 科目映射表 (源科目->标准科目)
CREATE TABLE account_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    -- 源科目信息
    source_account_code VARCHAR(50) NOT NULL,    -- 源科目代码
    source_account_name VARCHAR(200) NOT NULL,   -- 源科目名称
    source_system_id UUID REFERENCES source_systems(id),

    -- 目标标准科目
    standard_account_id UUID REFERENCES account_standard(id),
    standard_account_code VARCHAR(20),
    standard_account_name VARCHAR(200),

    -- 映射状态
    mapping_status VARCHAR(20) DEFAULT 'PENDING', -- PENDING/AUTO/MANUAL/CONFIRMED
    confidence_score DECIMAL(5,2),               -- AI映射置信度 0-100

    -- 手动调整
    manually_adjusted BOOLEAN DEFAULT FALSE,
    adjusted_by UUID REFERENCES users(id),
    adjusted_at TIMESTAMP,
    adjustment_reason TEXT,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_mapping_status CHECK (mapping_status IN ('PENDING', 'AUTO', 'MANUAL', 'CONFIRMED')),
    UNIQUE(project_id, entity_id, source_account_code)
);

-- 创建索引
CREATE INDEX idx_import_history_project_id ON import_history(project_id);
CREATE INDEX idx_import_history_status ON import_history(status);
CREATE INDEX idx_import_history_entity_id ON import_history(entity_id);
CREATE INDEX idx_account_mapping_project_id ON account_mapping(project_id);
CREATE INDEX idx_account_mapping_source_code ON account_mapping(source_account_code);
CREATE INDEX idx_account_mapping_status ON account_mapping(mapping_status);
CREATE INDEX idx_account_standard_code ON account_standard(account_code);
CREATE INDEX idx_account_standard_category ON account_standard(account_category);

-- 插入默认源系统
INSERT INTO source_systems (system_code, system_name, file_formats) VALUES
('KINGDEE', '金蝶', '["xlsx", "xls", "bak", "sql"]'),
('UFIDA', '用友', '["xlsx", "xls", "bak", "acc"]'),
('SAP', 'SAP', '["csv", "txt", "xlsx"]'),
('EXCEL', 'Excel通用', '["xlsx", "xls", "csv"]'),
('AIS', 'AIS系统', '["db", "mdb", "accdb"]');

-- 插入标准科目 (一级科目示例)
INSERT INTO account_standard (account_code, account_name, account_level, account_category, account_direction, is_leaf) VALUES
('1001', '库存现金', 1, '资产', 'DEBIT', TRUE),
('1002', '银行存款', 1, '资产', 'DEBIT', FALSE),
('1012', '其他货币资金', 1, '资产', 'DEBIT', TRUE),
('1101', '交易性金融资产', 1, '资产', 'DEBIT', TRUE),
('1121', '应收票据', 1, '资产', 'DEBIT', TRUE),
('1122', '应收账款', 1, '资产', 'DEBIT', TRUE),
('1123', '预付账款', 1, '资产', 'DEBIT', TRUE),
('1131', '应收股利', 1, '资产', 'DEBIT', TRUE),
('1132', '应收利息', 1, '资产', 'DEBIT', TRUE),
('1221', '其他应收款', 1, '资产', 'DEBIT', TRUE),
('1401', '材料采购', 1, '资产', 'DEBIT', TRUE),
('1402', '在途物资', 1, '资产', 'DEBIT', TRUE),
('1403', '原材料', 1, '资产', 'DEBIT', TRUE),
('1405', '库存商品', 1, '资产', 'DEBIT', TRUE),
('1601', '固定资产', 1, '资产', 'DEBIT', TRUE),
('1602', '累计折旧', 1, '资产', 'CREDIT', TRUE),
('1701', '无形资产', 1, '资产', 'DEBIT', TRUE),
('2001', '短期借款', 1, '负债', 'CREDIT', TRUE),
('2201', '应付票据', 1, '负债', 'CREDIT', TRUE),
('2202', '应付账款', 1, '负债', 'CREDIT', TRUE),
('2203', '预收账款', 1, '负债', 'CREDIT', TRUE),
('2211', '应付职工薪酬', 1, '负债', 'CREDIT', TRUE),
('2221', '应交税费', 1, '负债', 'CREDIT', TRUE),
('2241', '其他应付款', 1, '负债', 'CREDIT', TRUE),
('2501', '长期借款', 1, '负债', 'CREDIT', TRUE),
('4001', '实收资本', 1, '权益', 'CREDIT', TRUE),
('4002', '资本公积', 1, '权益', 'CREDIT', TRUE),
('4101', '盈余公积', 1, '权益', 'CREDIT', TRUE),
('4103', '本年利润', 1, '权益', 'CREDIT', TRUE),
('4104', '利润分配', 1, '权益', 'CREDIT', TRUE),
('5001', '生产成本', 1, '成本', 'DEBIT', TRUE),
('5101', '制造费用', 1, '成本', 'DEBIT', TRUE),
('6001', '主营业务收入', 1, '损益', 'CREDIT', TRUE),
('6051', '其他业务收入', 1, '损益', 'CREDIT', TRUE),
('6401', '主营业务成本', 1, '损益', 'DEBIT', TRUE),
('6402', '其他业务成本', 1, '损益', 'DEBIT', TRUE),
('6403', '税金及附加', 1, '损益', 'DEBIT', TRUE),
('6601', '销售费用', 1, '损益', 'DEBIT', TRUE),
('6602', '管理费用', 1, '损益', 'DEBIT', TRUE),
('6603', '财务费用', 1, '损益', 'DEBIT', TRUE),
('6701', '资产减值损失', 1, '损益', 'DEBIT', TRUE),
('6801', '所得税费用', 1, '损益', 'DEBIT', TRUE);

-- 更新时间戳触发器
CREATE TRIGGER update_account_mapping_updated_at BEFORE UPDATE ON account_mapping
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE source_systems IS '源系统类型表 - 支持的财务系统类型';
COMMENT ON TABLE account_standard IS '标准科目表 - 企业会计准则标准科目';
COMMENT ON TABLE import_history IS '数据导入历史表 - 记录每次数据导入';
COMMENT ON TABLE account_mapping IS '科目映射表 - 源科目到标准科目的映射关系';
