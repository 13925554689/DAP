-- ============================================
-- DAP v2.0 Database Schema - Progress Summary
-- ============================================

## 数据库架构设计进度

### 已完成模块 (16/35 表)

#### 模块1: 用户权限管理 (5表) ✅
- users - 用户表
- roles - 角色表
- permissions - 权限表
- user_roles - 用户角色关联表
- role_permissions - 角色权限关联表

#### 模块2: 项目管理(中普模式) (7表) ✅
- project_types - 项目类型表
- projects - 审计项目主表
- audit_teams - 审计组表
- team_members - 审计组成员表
- project_milestones - 项目里程碑表
- project_documents - 项目文档表
- project_communications - 项目沟通记录表

#### 模块3: 客户与组织架构 (4表) ✅
- clients - 客户公司表
- entities - 被审计主体表(母公司+子公司)
- equity_relations - 股权关系表
- consolidation_scope - 合并范围表

### 待完成模块 (19表)

#### 模块4: 数据导入与映射
- import_history
- source_systems
- account_mapping
- account_standard

#### 模块5: 财务数据存储
- raw_vouchers / cleaned_vouchers
- raw_balances / cleaned_balances
- raw_details / cleaned_details

#### 模块6: 审计底稿
- workpaper_templates
- workpapers
- workpaper_cells
- workpaper_attachments
- workpaper_comments
- workpaper_versions

#### 模块7: 合并报表
- elimination_rules
- elimination_entries
- consolidated_reports
- minority_interests

#### 模块8: 复核流程
- review_flows
- review_tasks
- review_comments
- review_history

#### 模块9: 系统日志
- audit_logs
- change_history
- login_logs

## 设计特点

1. **审计合规性**: 完整审计追踪,满足监管要求
2. **中普模式**: 吸收中普审计软件项目管理优点
3. **合并报表**: 完整股权关系与合并范围管理
4. **权限分级**: 四级权限(审计员/组长/经理/合伙人)
5. **版本控制**: 关键数据支持版本回溯

## 下一步

继续快速完成模块4-9的SQL设计
