-- ============================================
-- DAP v2.0 Database Schema
-- Module 8: Review Workflow (三级复核)
-- ============================================

-- 复核流程定义表
CREATE TABLE review_flows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_code VARCHAR(50) NOT NULL UNIQUE,
    flow_name VARCHAR(100) NOT NULL,
    description TEXT,

    -- 流程配置
    total_levels INTEGER NOT NULL DEFAULT 3,     -- 复核级数
    level_config JSONB NOT NULL,                 -- 各级别配置

    -- 适用范围
    applicable_project_types JSONB,              -- 适用的项目类型
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 复核任务表
CREATE TABLE review_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workpaper_id UUID REFERENCES workpapers(id),
    review_flow_id UUID REFERENCES review_flows(id),

    -- 任务信息
    task_name VARCHAR(200) NOT NULL,
    task_type VARCHAR(50),                       -- WORKPAPER/REPORT/CONSOLIDATION
    review_level INTEGER NOT NULL,               -- 当前复核级别 1/2/3

    -- 复核人
    reviewer_id UUID NOT NULL REFERENCES users(id),
    assignee_id UUID REFERENCES users(id),       -- 被指派人(编制人)

    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING/IN_PROGRESS/APPROVED/REJECTED/RETURNED
    priority VARCHAR(10) DEFAULT 'MEDIUM',       -- HIGH/MEDIUM/LOW

    -- 时间
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- 复核结论
    review_result VARCHAR(20),                   -- PASS/PASS_WITH_COMMENTS/FAIL
    review_summary TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_task_status CHECK (status IN ('PENDING', 'IN_PROGRESS', 'APPROVED', 'REJECTED', 'RETURNED')),
    CONSTRAINT check_review_result CHECK (review_result IN ('PASS', 'PASS_WITH_COMMENTS', 'FAIL') OR review_result IS NULL)
);

-- 复核意见表
CREATE TABLE review_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_task_id UUID NOT NULL REFERENCES review_tasks(id) ON DELETE CASCADE,
    workpaper_id UUID REFERENCES workpapers(id),

    -- 意见信息
    comment_type VARCHAR(20) NOT NULL,           -- QUESTION/ISSUE/SUGGESTION/APPROVAL
    comment_text TEXT NOT NULL,
    severity VARCHAR(10),                        -- HIGH/MEDIUM/LOW

    -- 关联位置
    reference_location TEXT,                     -- 引用位置(如单元格地址)
    cell_address VARCHAR(20),

    -- 状态跟踪
    status VARCHAR(20) DEFAULT 'OPEN',           -- OPEN/ADDRESSED/CLOSED/WAIVED
    response_text TEXT,                          -- 回复内容
    responded_by UUID REFERENCES users(id),
    responded_at TIMESTAMP,

    -- 关闭信息
    closed_by UUID REFERENCES users(id),
    closed_at TIMESTAMP,
    close_reason TEXT,

    -- 作者
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_comment_type CHECK (comment_type IN ('QUESTION', 'ISSUE', 'SUGGESTION', 'APPROVAL')),
    CONSTRAINT check_comment_severity CHECK (severity IN ('HIGH', 'MEDIUM', 'LOW') OR severity IS NULL),
    CONSTRAINT check_comment_status CHECK (status IN ('OPEN', 'ADDRESSED', 'CLOSED', 'WAIVED'))
);

-- 复核历史表
CREATE TABLE review_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_task_id UUID NOT NULL REFERENCES review_tasks(id),
    workpaper_id UUID REFERENCES workpapers(id),

    -- 操作信息
    action VARCHAR(50) NOT NULL,                 -- SUBMIT/APPROVE/REJECT/RETURN/COMMENT/CLOSE
    action_level INTEGER,                        -- 操作级别
    previous_status VARCHAR(20),
    new_status VARCHAR(20),

    -- 操作详情
    action_details JSONB,
    comments TEXT,

    -- 操作人
    performed_by UUID NOT NULL REFERENCES users(id),
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_review_tasks_project_id ON review_tasks(project_id);
CREATE INDEX idx_review_tasks_workpaper_id ON review_tasks(workpaper_id);
CREATE INDEX idx_review_tasks_reviewer_id ON review_tasks(reviewer_id);
CREATE INDEX idx_review_tasks_status ON review_tasks(status);
CREATE INDEX idx_review_tasks_level ON review_tasks(review_level);
CREATE INDEX idx_review_comments_task_id ON review_comments(review_task_id);
CREATE INDEX idx_review_comments_status ON review_comments(status);
CREATE INDEX idx_review_history_task_id ON review_history(review_task_id);
CREATE INDEX idx_review_history_workpaper_id ON review_history(workpaper_id);

-- 插入默认复核流程
INSERT INTO review_flows (flow_code, flow_name, description, total_levels, level_config, is_default) VALUES
('THREE_LEVEL', '三级复核流程', '标准三级复核:项目组长->项目经理->合伙人', 3,
 '[{"level": 1, "name": "一级复核", "role": "senior", "description": "项目组长复核"},
   {"level": 2, "name": "二级复核", "role": "manager", "description": "项目经理复核"},
   {"level": 3, "name": "三级复核", "role": "partner", "description": "合伙人复核"}]',
 TRUE),
('TWO_LEVEL', '两级复核流程', '简化两级复核:项目组长->项目经理', 2,
 '[{"level": 1, "name": "一级复核", "role": "senior", "description": "项目组长复核"},
   {"level": 2, "name": "二级复核", "role": "manager", "description": "项目经理复核"}]',
 FALSE);

-- 更新触发器
CREATE TRIGGER update_review_tasks_updated_at BEFORE UPDATE ON review_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE review_flows IS '复核流程定义表 - 定义复核级数和配置';
COMMENT ON TABLE review_tasks IS '复核任务表 - 每个复核任务的状态跟踪';
COMMENT ON TABLE review_comments IS '复核意见表 - 复核过程中的问题和意见';
COMMENT ON TABLE review_history IS '复核历史表 - 完整的复核操作记录';

COMMENT ON COLUMN review_tasks.review_level IS '复核级别: 1-一级(组长) 2-二级(经理) 3-三级(合伙人)';
