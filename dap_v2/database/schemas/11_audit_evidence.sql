-- ============================================
-- DAP v2.0 Database Schema
-- Module: Audit Evidence Management (审计证据管理)
-- Purpose: 支持产权证明等各类审计证据文件的导入、管理和审核
-- ============================================

-- 审计证据主表
CREATE TABLE audit_evidences (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),

    -- 关联信息
    workpaper_id TEXT REFERENCES audit_workpapers(id) ON DELETE CASCADE,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    account_code VARCHAR(50),                          -- 关联科目代码 (如: 1601-固定资产)
    account_name VARCHAR(100),                         -- 科目名称

    -- 证据分类
    evidence_category VARCHAR(50) NOT NULL,            -- 证据类别 (见下方枚举说明)
    evidence_type VARCHAR(50) NOT NULL,                -- 证据类型 (见下方枚举说明)
    business_type VARCHAR(50),                         -- 业务类型: fixed_asset/intangible/loan/inventory等

    -- 基本信息
    title VARCHAR(255) NOT NULL,                       -- 证据标题
    description TEXT,                                  -- 证据描述

    -- 文件信息
    file_name VARCHAR(255) NOT NULL,                   -- 原始文件名
    file_path VARCHAR(500) NOT NULL,                   -- 存储路径
    file_size BIGINT NOT NULL,                         -- 文件大小(字节)
    file_type VARCHAR(50) NOT NULL,                    -- 文件类型: pdf/jpg/png/xlsx/docx等
    file_hash VARCHAR(64),                             -- 文件SHA256哈希值(防篡改)
    mime_type VARCHAR(100),                            -- MIME类型

    -- 证书/证明特定字段
    certificate_number VARCHAR(100),                   -- 证书编号(产权证号、专利号等)
    issue_date DATE,                                   -- 签发日期
    expiry_date DATE,                                  -- 到期日期
    issuing_authority VARCHAR(200),                    -- 签发机关

    -- 金额相关
    amount DECIMAL(20,2),                              -- 涉及金额
    currency VARCHAR(10) DEFAULT 'CNY',                -- 币种

    -- OCR智能提取
    extracted_data TEXT,                               -- OCR提取的JSON数据
    ocr_confidence DECIMAL(5,2),                       -- OCR识别置信度(0-100)
    ocr_processed BOOLEAN DEFAULT FALSE,               -- 是否已OCR处理
    ocr_processed_at DATETIME,                         -- OCR处理时间

    -- 审核状态
    review_status VARCHAR(20) DEFAULT 'pending',       -- pending/reviewing/approved/rejected/revised
    submitted_for_review BOOLEAN DEFAULT FALSE,        -- 是否已提交审核
    reviewed_by TEXT REFERENCES users(id),             -- 审核人
    review_date DATETIME,                              -- 审核日期
    review_comments TEXT,                              -- 审核意见
    review_level INTEGER,                              -- 审核级别(1/2/3)

    -- 重要性标记
    is_key_evidence BOOLEAN DEFAULT FALSE,             -- 是否关键证据
    is_original BOOLEAN DEFAULT TRUE,                  -- 是否原件(false为复印件)
    confidentiality_level VARCHAR(20) DEFAULT 'normal', -- 保密等级: public/internal/confidential/secret

    -- 关联关系
    related_transaction_id TEXT,                       -- 关联的会计凭证ID
    related_asset_id TEXT,                             -- 关联的资产ID
    related_contract_id TEXT,                          -- 关联的合同ID
    parent_evidence_id TEXT REFERENCES audit_evidences(id), -- 父证据ID(证据组)

    -- 标签和分类
    tags TEXT,                                         -- 标签JSON数组: ["产权证明","重要","待复核"]
    keywords TEXT,                                     -- 关键词(用于搜索)

    -- 保留和归档
    retention_period INTEGER DEFAULT 10,               -- 保留期限(年)
    archive_status VARCHAR(20) DEFAULT 'active',       -- active/archived/destroyed
    archive_date DATETIME,                             -- 归档日期

    -- 审计追踪
    uploaded_by TEXT NOT NULL REFERENCES users(id),
    upload_date DATETIME DEFAULT (datetime('now')),
    last_accessed_by TEXT REFERENCES users(id),
    last_accessed_at DATETIME,
    access_count INTEGER DEFAULT 0,                    -- 访问次数

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now')),

    CONSTRAINT check_review_status CHECK (review_status IN ('pending','reviewing','approved','rejected','revised')),
    CONSTRAINT check_confidentiality CHECK (confidentiality_level IN ('public','internal','confidential','secret')),
    CONSTRAINT check_archive_status CHECK (archive_status IN ('active','archived','destroyed'))
);

-- 证据批注表 (支持PDF/图片批注)
CREATE TABLE evidence_annotations (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),
    evidence_id TEXT NOT NULL REFERENCES audit_evidences(id) ON DELETE CASCADE,

    -- 批注位置
    page_number INTEGER,                               -- 页码(PDF)
    position_x DECIMAL(10,2),                          -- X坐标
    position_y DECIMAL(10,2),                          -- Y坐标
    width DECIMAL(10,2),                               -- 宽度
    height DECIMAL(10,2),                              -- 高度

    -- 批注类型和内容
    annotation_type VARCHAR(20) NOT NULL,              -- highlight/comment/stamp/arrow/rect/circle
    content TEXT,                                      -- 批注内容
    color VARCHAR(20) DEFAULT '#FFFF00',               -- 颜色代码

    -- 审计标记
    mark_type VARCHAR(50),                             -- 标记类型: 异常/疑点/核实/确认/问题
    severity VARCHAR(20),                              -- 严重程度: low/medium/high/critical

    created_by TEXT NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

-- 证据版本历史表
CREATE TABLE evidence_versions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),
    evidence_id TEXT NOT NULL REFERENCES audit_evidences(id) ON DELETE CASCADE,

    version_number INTEGER NOT NULL,                   -- 版本号
    file_path VARCHAR(500) NOT NULL,                   -- 该版本文件路径
    file_size BIGINT NOT NULL,
    file_hash VARCHAR(64),

    change_type VARCHAR(50),                           -- 变更类型: upload/replace/update/restore
    changes_description TEXT,                          -- 变更说明

    created_by TEXT NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT (datetime('now')),

    UNIQUE(evidence_id, version_number)
);

-- 证据关联关系表
CREATE TABLE evidence_relationships (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),
    evidence_id TEXT NOT NULL REFERENCES audit_evidences(id) ON DELETE CASCADE,
    related_evidence_id TEXT NOT NULL REFERENCES audit_evidences(id) ON DELETE CASCADE,

    relationship_type VARCHAR(50) NOT NULL,            -- supporting/contradicting/related/superseded
    description TEXT,

    created_by TEXT NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT (datetime('now')),

    UNIQUE(evidence_id, related_evidence_id, relationship_type)
);

-- 证据检查清单表 (针对特定业务类型的必需证据)
CREATE TABLE evidence_checklists (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),

    business_type VARCHAR(50) NOT NULL,                -- fixed_asset/intangible/loan等
    account_code VARCHAR(50),

    checklist_name VARCHAR(200) NOT NULL,              -- 清单名称
    required_evidences TEXT NOT NULL,                  -- 必需证据JSON数组
    optional_evidences TEXT,                           -- 可选证据JSON数组
    validation_rules TEXT,                             -- 验证规则JSON

    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

-- 证据审核历史表
CREATE TABLE evidence_review_history (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),
    evidence_id TEXT NOT NULL REFERENCES audit_evidences(id) ON DELETE CASCADE,

    review_level INTEGER NOT NULL,                     -- 审核级别 1/2/3
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    review_status VARCHAR(20) NOT NULL,                -- approved/rejected/revised
    review_comments TEXT,
    review_date DATETIME DEFAULT (datetime('now')),

    -- 审核要点
    completeness_score INTEGER,                        -- 完整性评分(1-5)
    authenticity_score INTEGER,                        -- 真实性评分(1-5)
    relevance_score INTEGER,                           -- 相关性评分(1-5)

    created_at DATETIME DEFAULT (datetime('now'))
);

-- 文件访问日志表 (安全审计)
CREATE TABLE evidence_access_log (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))),
    evidence_id TEXT NOT NULL REFERENCES audit_evidences(id) ON DELETE CASCADE,

    user_id TEXT NOT NULL REFERENCES users(id),
    action VARCHAR(50) NOT NULL,                       -- view/download/print/edit/delete
    ip_address VARCHAR(45),
    user_agent TEXT,
    access_time DATETIME DEFAULT (datetime('now'))
);

-- ==================== 索引 ====================

-- 主要查询索引
CREATE INDEX idx_evidences_workpaper ON audit_evidences(workpaper_id);
CREATE INDEX idx_evidences_project ON audit_evidences(project_id);
CREATE INDEX idx_evidences_account ON audit_evidences(account_code);
CREATE INDEX idx_evidences_category ON audit_evidences(evidence_category);
CREATE INDEX idx_evidences_type ON audit_evidences(evidence_type);
CREATE INDEX idx_evidences_business_type ON audit_evidences(business_type);
CREATE INDEX idx_evidences_status ON audit_evidences(review_status);
CREATE INDEX idx_evidences_uploaded_by ON audit_evidences(uploaded_by);
CREATE INDEX idx_evidences_upload_date ON audit_evidences(upload_date);
CREATE INDEX idx_evidences_certificate_no ON audit_evidences(certificate_number);
CREATE INDEX idx_evidences_hash ON audit_evidences(file_hash);

-- 批注索引
CREATE INDEX idx_annotations_evidence ON evidence_annotations(evidence_id);
CREATE INDEX idx_annotations_creator ON evidence_annotations(created_by);

-- 版本索引
CREATE INDEX idx_versions_evidence ON evidence_versions(evidence_id);
CREATE INDEX idx_versions_number ON evidence_versions(version_number);

-- 关系索引
CREATE INDEX idx_relationships_evidence ON evidence_relationships(evidence_id);
CREATE INDEX idx_relationships_related ON evidence_relationships(related_evidence_id);

-- 审核历史索引
CREATE INDEX idx_review_history_evidence ON evidence_review_history(evidence_id);
CREATE INDEX idx_review_history_reviewer ON evidence_review_history(reviewer_id);
CREATE INDEX idx_review_history_level ON evidence_review_history(review_level);

-- 访问日志索引
CREATE INDEX idx_access_log_evidence ON evidence_access_log(evidence_id);
CREATE INDEX idx_access_log_user ON evidence_access_log(user_id);
CREATE INDEX idx_access_log_time ON evidence_access_log(access_time);

-- ==================== 初始化数据 ====================

-- 插入证据检查清单模板

-- 固定资产证据清单
INSERT INTO evidence_checklists (business_type, account_code, checklist_name, required_evidences, optional_evidences, validation_rules) VALUES (
    'fixed_asset',
    '1601',
    '固定资产-房屋建筑物证据清单',
    '[
        {"name": "产权证明", "type": "property_certificate", "description": "房产证或不动产权证书"},
        {"name": "购买合同/发票", "type": "contract_invoice", "description": "购房合同及购房发票"},
        {"name": "折旧计算表", "type": "depreciation_schedule", "description": "固定资产折旧计算明细表"}
    ]',
    '[
        {"name": "评估报告", "type": "appraisal_report", "description": "资产评估报告"},
        {"name": "现场照片", "type": "site_photo", "description": "资产实物照片"},
        {"name": "维修记录", "type": "maintenance_record", "description": "大修理、改建记录"}
    ]',
    '{
        "check_certificate_valid": true,
        "check_amount_match": true,
        "check_depreciation_rate": true,
        "max_useful_life": 50
    }'
);

-- 无形资产证据清单
INSERT INTO evidence_checklists (business_type, account_code, checklist_name, required_evidences, optional_evidences, validation_rules) VALUES (
    'intangible_asset',
    '1701',
    '无形资产-专利权证据清单',
    '[
        {"name": "专利证书", "type": "patent_certificate", "description": "国家知识产权局颁发的专利证书"},
        {"name": "购买合同", "type": "contract", "description": "专利购买或研发合同"},
        {"name": "摊销计算表", "type": "amortization_schedule", "description": "无形资产摊销计算表"}
    ]',
    '[
        {"name": "专利年费缴纳证明", "type": "annual_fee_receipt", "description": "专利年费缴费凭证"},
        {"name": "技术鉴定报告", "type": "tech_appraisal", "description": "技术成果鉴定报告"}
    ]',
    '{
        "check_patent_valid": true,
        "check_expiry_date": true,
        "max_amortization_period": 10
    }'
);

-- 借款利息证据清单
INSERT INTO evidence_checklists (business_type, account_code, checklist_name, required_evidences, optional_evidences, validation_rules) VALUES (
    'loan_interest',
    '2201',
    '短期借款利息证据清单',
    '[
        {"name": "借款合同", "type": "loan_contract", "description": "与金融机构签订的借款合同"},
        {"name": "银行对账单", "type": "bank_statement", "description": "借款发放及还款的银行对账单"},
        {"name": "利息计算表", "type": "interest_calculation", "description": "利息费用计算明细表"}
    ]',
    '[
        {"name": "还款凭证", "type": "repayment_voucher", "description": "本金及利息还款凭证"},
        {"name": "授信协议", "type": "credit_agreement", "description": "银行授信额度协议"}
    ]',
    '{
        "check_interest_rate_reasonable": true,
        "check_interest_calculation": true,
        "max_interest_rate": 24.0
    }'
);

-- 应收账款证据清单
INSERT INTO evidence_checklists (business_type, account_code, checklist_name, required_evidences, optional_evidences) VALUES (
    'accounts_receivable',
    '1122',
    '应收账款证据清单',
    '[
        {"name": "销售合同", "type": "sales_contract", "description": "与客户签订的销售合同"},
        {"name": "销售发票", "type": "sales_invoice", "description": "开具的增值税发票"},
        {"name": "发货单据", "type": "delivery_note", "description": "签收的发货单或物流单据"}
    ]',
    '[
        {"name": "对账单", "type": "reconciliation_statement", "description": "与客户的对账确认单"},
        {"name": "收款记录", "type": "payment_record", "description": "银行收款凭证"}
    ]'
);

-- 存货证据清单
INSERT INTO evidence_checklists (business_type, account_code, checklist_name, required_evidences, optional_evidences) VALUES (
    'inventory',
    '1405',
    '存货盘点证据清单',
    '[
        {"name": "存货盘点表", "type": "inventory_count_sheet", "description": "实地盘点记录表"},
        {"name": "盘点照片", "type": "inventory_photo", "description": "存货实物照片"},
        {"name": "出入库单据", "type": "warehouse_document", "description": "出入库流水单"}
    ]',
    '[
        {"name": "盘点差异说明", "type": "variance_explanation", "description": "盘盈盘亏原因说明"},
        {"name": "仓库平面图", "type": "warehouse_layout", "description": "仓库布局示意图"}
    ]'
);

-- ==================== 表注释 ====================
-- 由于SQLite不支持COMMENT语法，这里用SQL注释说明

/*
证据类别 (evidence_category) 枚举值:
- property_certificate: 产权证明 (房产证、土地证、车辆登记证等)
- contract: 合同协议
- invoice: 发票凭证
- calculation_sheet: 计算表 (折旧表、摊销表、利息表等)
- financial_statement: 财务报表
- bank_document: 银行单据 (对账单、回单等)
- photo: 照片资料
- certificate: 各类证书 (专利证、商标证、资质证等)
- appraisal_report: 评估报告
- legal_document: 法律文书 (判决书、仲裁书等)
- other: 其他

证据类型 (evidence_type) 枚举值:
- original: 原件
- copy: 复印件
- scan: 扫描件
- photo: 拍照件
- electronic: 电子文件
*/
