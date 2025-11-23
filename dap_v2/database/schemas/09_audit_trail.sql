-- ============================================
-- DAP v2.0 Database Schema
-- Module 9: Audit Trail & System Logs
-- ============================================

-- 审计日志表 (核心操作追踪)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 操作信息
    action_type VARCHAR(50) NOT NULL,            -- CREATE/UPDATE/DELETE/VIEW/EXPORT/APPROVE
    action_category VARCHAR(50) NOT NULL,        -- PROJECT/WORKPAPER/CONSOLIDATION/USER/SYSTEM
    action_description TEXT,

    -- 操作对象
    target_table VARCHAR(100),                   -- 目标表名
    target_id UUID,                              -- 目标记录ID
    target_name VARCHAR(200),                    -- 目标名称(便于显示)

    -- 关联项目
    project_id UUID REFERENCES projects(id),
    entity_id UUID REFERENCES entities(id),

    -- 操作数据
    old_values JSONB,                            -- 修改前的值
    new_values JSONB,                            -- 修改后的值
    change_summary TEXT,                         -- 变更摘要

    -- 操作人
    performed_by UUID NOT NULL REFERENCES users(id),
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 客户端信息
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(100)
);

-- 变更历史表 (详细字段级变更)
CREATE TABLE change_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_log_id UUID REFERENCES audit_logs(id),

    -- 变更字段
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    field_name VARCHAR(100) NOT NULL,

    -- 变更值
    old_value TEXT,
    new_value TEXT,
    data_type VARCHAR(50),                       -- 数据类型

    -- 变更原因
    change_reason TEXT,

    -- 操作人
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 登录日志表
CREATE TABLE login_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    username VARCHAR(100),

    -- 登录信息
    login_type VARCHAR(20),                      -- PASSWORD/TOKEN/SSO
    login_status VARCHAR(20) NOT NULL,           -- SUCCESS/FAILED/LOCKED
    failure_reason TEXT,

    -- 时间
    login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logout_at TIMESTAMP,
    session_duration INTEGER,                    -- 会话时长(秒)

    -- 客户端信息
    ip_address INET,
    user_agent TEXT,
    device_type VARCHAR(50),                     -- DESKTOP/MOBILE/TABLET
    browser VARCHAR(100),
    os VARCHAR(100),
    location VARCHAR(200),                       -- 登录地点

    CONSTRAINT check_login_status CHECK (login_status IN ('SUCCESS', 'FAILED', 'LOCKED'))
);

-- 系统操作日志表
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    log_level VARCHAR(20) NOT NULL,              -- DEBUG/INFO/WARNING/ERROR/CRITICAL
    log_category VARCHAR(50),                    -- SYSTEM/DATABASE/API/SCHEDULER

    -- 日志内容
    message TEXT NOT NULL,
    details JSONB,
    stack_trace TEXT,

    -- 来源
    source_module VARCHAR(100),
    source_function VARCHAR(200),
    source_line INTEGER,

    -- 时间
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 关联用户(如有)
    user_id UUID REFERENCES users(id),
    request_id VARCHAR(100)                      -- 请求追踪ID
);

-- 数据导出记录表
CREATE TABLE export_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),

    -- 导出信息
    export_type VARCHAR(50) NOT NULL,            -- WORKPAPER/REPORT/DATA
    export_format VARCHAR(20),                   -- EXCEL/PDF/CSV/ZIP
    file_name VARCHAR(500),
    file_path TEXT,
    file_size BIGINT,

    -- 导出内容
    export_scope TEXT,                           -- 导出范围描述
    record_count INTEGER,

    -- 操作人
    exported_by UUID NOT NULL REFERENCES users(id),
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 下载信息
    download_count INTEGER DEFAULT 0,
    last_download_at TIMESTAMP,
    expires_at TIMESTAMP                         -- 下载链接过期时间
);

-- 创建索引
CREATE INDEX idx_audit_logs_action_type ON audit_logs(action_type);
CREATE INDEX idx_audit_logs_target_table ON audit_logs(target_table);
CREATE INDEX idx_audit_logs_project_id ON audit_logs(project_id);
CREATE INDEX idx_audit_logs_performed_by ON audit_logs(performed_by);
CREATE INDEX idx_audit_logs_performed_at ON audit_logs(performed_at);
CREATE INDEX idx_change_history_record_id ON change_history(record_id);
CREATE INDEX idx_change_history_table_name ON change_history(table_name);
CREATE INDEX idx_login_logs_user_id ON login_logs(user_id);
CREATE INDEX idx_login_logs_login_at ON login_logs(login_at);
CREATE INDEX idx_login_logs_status ON login_logs(login_status);
CREATE INDEX idx_system_logs_level ON system_logs(log_level);
CREATE INDEX idx_system_logs_logged_at ON system_logs(logged_at);
CREATE INDEX idx_export_logs_project_id ON export_logs(project_id);
CREATE INDEX idx_export_logs_exported_by ON export_logs(exported_by);

-- 自动清理旧日志的函数 (保留90天)
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM system_logs WHERE logged_at < NOW() - INTERVAL '90 days';
    DELETE FROM login_logs WHERE login_at < NOW() - INTERVAL '365 days';
    -- audit_logs 和 change_history 永久保留
END;
$$ LANGUAGE plpgsql;

-- 注释
COMMENT ON TABLE audit_logs IS '审计日志表 - 记录所有关键操作的审计追踪';
COMMENT ON TABLE change_history IS '变更历史表 - 字段级别的详细变更记录';
COMMENT ON TABLE login_logs IS '登录日志表 - 用户登录登出记录';
COMMENT ON TABLE system_logs IS '系统日志表 - 系统运行日志';
COMMENT ON TABLE export_logs IS '数据导出记录表 - 数据导出审计';

COMMENT ON COLUMN audit_logs.old_values IS '修改前的完整JSON数据';
COMMENT ON COLUMN audit_logs.new_values IS '修改后的完整JSON数据';
