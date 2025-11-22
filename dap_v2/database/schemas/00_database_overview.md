# DAP v2.0 Database Architecture

## 数据库设计理念

基于**审计业务需求**与**中普审计软件优秀实践**设计的专业审计数据库架构

## 核心模块划分

### 1. 用户权限模块 (User & Permission)
- users - 用户表
- roles - 角色表
- permissions - 权限表
- user_roles - 用户角色关联表
- role_permissions - 角色权限关联表

### 2. 项目管理模块 (Project Management)
- projects - 审计项目主表
- project_types - 项目类型(IPO/年报/财务/税务)
- audit_teams - 审计组表
- team_members - 审计组成员表
- project_milestones - 项目里程碑表

### 3. 客户与组织架构模块 (Client & Structure)
- clients - 客户公司表
- entities - 被审计主体表(母公司+子公司)
- equity_relations - 股权关系表
- consolidation_scope - 合并范围表

### 4. 数据导入与映射模块 (Data Import & Mapping)
- import_history - 数据导入历史表
- source_systems - 源系统类型表(金蝶/用友/SAP)
- account_mapping - 科目映射表
- account_standard - 标准科目表

### 5. 财务数据存储模块 (Financial Data)
- raw_vouchers - 原始凭证表
- raw_balances - 原始余额表
- raw_details - 原始明细表
- cleaned_vouchers - 清洗后凭证表
- cleaned_balances - 清洗后余额表
- cleaned_details - 清洗后明细表

### 6. 审计底稿模块 (Audit Workpaper)
- workpaper_templates - 底稿模板表
- workpapers - 审计底稿主表
- workpaper_cells - 底稿单元格数据表
- workpaper_attachments - 底稿附件表
- workpaper_comments - 底稿批注表
- workpaper_versions - 底稿版本表

### 7. 合并报表模块 (Consolidation)
- elimination_rules - 抵消规则表
- elimination_entries - 抵消分录表
- consolidated_reports - 合并报表表
- minority_interests - 少数股东权益表

### 8. 复核流程模块 (Review Workflow)
- review_flows - 复核流程表
- review_tasks - 复核任务表
- review_comments - 复核意见表
- review_history - 复核历史表

### 9. 系统日志与审计追踪模块 (Audit Trail)
- audit_logs - 审计日志表
- change_history - 变更历史表
- login_logs - 登录日志表

## 数据库设计原则

1. **审计合规性**: 所有关键操作记录完整审计追踪
2. **数据完整性**: 外键约束确保数据关联完整
3. **版本控制**: 关键数据支持版本管理和回滚
4. **性能优化**: 合理建立索引,支持大数据量查询
5. **扩展性**: 预留扩展字段,支持未来功能迭代

## 总表数 (Total Tables)

**35 张核心表** + 未来扩展表

下一步:详细设计每个模块的表结构
