# DAP v2.0 审计底稿与合并报表系统 - 详细开发计划

**项目名称**: DAP智能审计数据平台 v2.0
**开发周期**: 13周 (约3个月)
**开发模式**: 敏捷迭代开发
**团队规模**: 建议3-5人
**制定日期**: 2024-11-22

---

## 📅 总体时间表

```
Sprint 1  Sprint 2  Sprint 3  Sprint 4  Sprint 5  Sprint 6  Sprint 7
Week 1-2  Week 3-5  Week 6-9  Week10-11 Week12-13
  基础    合并报表   审计底稿   协同审计  测试优化
  架构      引擎      系统      功能
```

---

## 🎯 Sprint 1: 基础架构升级 (Week 1-2, 10工作日)

### 目标
- 数据库表结构升级完成
- 集团层级管理API实现
- 前端层级树组件开发

### Day 1-2: 数据库Schema设计与创建

**任务1.1**: 创建集团实体相关表
- **负责人**: 后端开发
- **工时**: 1天
- **交付物**:
```sql
-- D:\DAP\migrations\001_group_hierarchy.sql

CREATE TABLE dap_group_entities (
    entity_id TEXT PRIMARY KEY,
    entity_code TEXT UNIQUE NOT NULL,
    entity_name TEXT NOT NULL,
    entity_type TEXT CHECK(entity_type IN ('parent', 'subsidiary', 'branch', 'division')),
    parent_entity_id TEXT,
    level INTEGER CHECK(level BETWEEN 1 AND 6),
    holding_ratio DECIMAL(5,2) CHECK(holding_ratio >= 0 AND holding_ratio <= 100),
    control_type TEXT CHECK(control_type IN ('full', 'control', 'significant', 'joint')),
    consolidation_method TEXT CHECK(consolidation_method IN ('full', 'equity', 'proportional', 'cost')),
    fiscal_year INTEGER,
    fiscal_period TEXT,
    project_id TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_entity_id) REFERENCES dap_group_entities(entity_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id) ON DELETE CASCADE
);

CREATE INDEX idx_entity_project ON dap_group_entities(project_id);
CREATE INDEX idx_entity_parent ON dap_group_entities(parent_entity_id);
CREATE INDEX idx_entity_level ON dap_group_entities(level);

-- 层级路径表 (闭包表,用于快速查询祖先/后代)
CREATE TABLE dap_entity_paths (
    ancestor_id TEXT NOT NULL,
    descendant_id TEXT NOT NULL,
    path_length INTEGER NOT NULL,
    PRIMARY KEY (ancestor_id, descendant_id),
    FOREIGN KEY (ancestor_id) REFERENCES dap_group_entities(entity_id) ON DELETE CASCADE,
    FOREIGN KEY (descendant_id) REFERENCES dap_group_entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX idx_path_ancestor ON dap_entity_paths(ancestor_id);
CREATE INDEX idx_path_descendant ON dap_entity_paths(descendant_id);
```

**任务1.2**: 创建审计协同相关表
- **负责人**: 后端开发
- **工时**: 1天
- **交付物**:
```sql
-- D:\DAP\migrations\002_audit_collaboration.sql

-- 审计组表
CREATE TABLE dap_audit_teams (
    team_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    partner TEXT NOT NULL,          -- 合伙人
    project_manager TEXT NOT NULL,  -- 项目经理
    team_leader TEXT,                -- 项目组长
    members TEXT,                    -- JSON数组: 审计员列表
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id) ON DELETE CASCADE
);

-- 审计任务表
CREATE TABLE dap_audit_tasks (
    task_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_type TEXT CHECK(task_type IN ('workpaper', 'fieldwork', 'review', 'other')),
    task_name TEXT NOT NULL,
    task_description TEXT,
    assigned_to TEXT NOT NULL,      -- 分配给谁
    assigned_by TEXT,                -- 谁分配的
    entity_id TEXT,                  -- 关联集团实体
    workpaper_template_id TEXT,      -- 关联底稿模板
    priority TEXT DEFAULT 'normal' CHECK(priority IN ('low', 'normal', 'high', 'urgent')),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'review', 'completed', 'cancelled')),
    deadline DATE,
    estimated_hours DECIMAL(5,2),
    actual_hours DECIMAL(5,2),
    completion_rate INTEGER DEFAULT 0 CHECK(completion_rate BETWEEN 0 AND 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES dap_group_entities(entity_id) ON DELETE SET NULL
);

CREATE INDEX idx_task_project ON dap_audit_tasks(project_id);
CREATE INDEX idx_task_assigned ON dap_audit_tasks(assigned_to);
CREATE INDEX idx_task_status ON dap_audit_tasks(status);
```

### Day 3-5: 集团层级管理后端API开发

**任务1.3**: 开发 `layer2/group_hierarchy_manager.py` 增强版
- **负责人**: Python后端开发
- **工时**: 3天
- **关键功能**:
```python
class GroupHierarchyManager:
    # Day 3: 基础CRUD
    def create_entity(...)  # 创建集团实体
    def update_entity(...)  # 更新实体信息
    def delete_entity(...)  # 删除实体(级联或保护)
    def get_entity(...)     # 获取单个实体
    def list_entities(...)  # 列出所有实体

    # Day 4: 层级管理
    def get_entity_hierarchy(...)  # 获取层级树
    def get_ancestors(...)         # 获取所有祖先
    def get_descendants(...)       # 获取所有后代
    def move_entity(...)           # 移动实体到新父节点

    # Day 5: 合并范围与验证
    def get_consolidation_scope(...)      # 获取合并范围
    def calculate_effective_holding(...)  # 计算实际持股比例
    def validate_holding_chain(...)       # 验证持股链
    def detect_circular_reference(...)    # 检测循环引用
```

**验收标准**:
- [ ] 单元测试覆盖率 > 80%
- [ ] 支持6层级结构
- [ ] 支持批量导入(Excel)
- [ ] 提供层级路径快速查询 (闭包表)

### Day 6-8: Web API路由开发

**任务1.4**: 添加Flask/FastAPI路由
- **负责人**: 后端开发
- **工时**: 3天
- **交付物**: `web_gui/routes/group_hierarchy_routes.py`

```python
# RESTful API设计
GET    /api/group-entities                    # 列出所有实体
GET    /api/group-entities/<entity_id>        # 获取单个实体
POST   /api/group-entities                    # 创建实体
PUT    /api/group-entities/<entity_id>        # 更新实体
DELETE /api/group-entities/<entity_id>        # 删除实体
GET    /api/group-entities/<entity_id>/hierarchy        # 获取层级树
GET    /api/group-entities/<entity_id>/consolidation-scope  # 获取合并范围
POST   /api/group-entities/import             # 批量导入
GET    /api/group-entities/export             # 导出层级结构
```

### Day 9-10: 前端组件开发

**任务1.5**: 开发层级树组件
- **负责人**: 前端开发
- **工时**: 2天
- **交付物**:
  - `web_gui/static/js/components/HierarchyTree.js`
  - `web_gui/static/css/hierarchy-tree.css`

**功能要求**:
- 树形结构展示 (可折叠/展开)
- 拖拽移动节点
- 右键菜单 (添加子节点、编辑、删除)
- 持股比例可视化
- 层级标识 (颜色区分)

**Sprint 1 验收标准**:
- [ ] 数据库migration脚本通过测试
- [ ] 后端API文档自动生成
- [ ] 前端组件在Chrome/Edge/Firefox正常运行
- [ ] 性能测试: 1000个实体加载 < 2秒

---

## 🎯 Sprint 2: 合并报表引擎 (Week 3-5, 15工作日)

### 目标
- 按层次/整体合并逻辑实现
- 八大抵消分录自动生成
- 内部往来智能匹配
- 合并报表界面开发

### Day 11-13: 数据库Schema - 合并报表相关表

**任务2.1**: 创建合并报表相关表
- **负责人**: 后端开发
- **工时**: 1天
- **交付物**: `migrations/003_consolidation_engine.sql`

```sql
-- 内部交易表
CREATE TABLE dap_internal_transactions (
    transaction_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    fiscal_period TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    seller_entity_id TEXT NOT NULL,
    buyer_entity_id TEXT NOT NULL,
    transaction_type TEXT,  -- '销售', '采购', '借款', '固定资产转让'等
    amount DECIMAL(18,2) NOT NULL,
    seller_account_code TEXT,
    buyer_account_code TEXT,
    seller_voucher_id TEXT,
    buyer_voucher_id TEXT,
    matching_status TEXT DEFAULT 'auto' CHECK(matching_status IN ('auto', 'manual', 'confirmed')),
    matching_confidence DECIMAL(3,2),  -- 匹配置信度 0-1
    needs_elimination BOOLEAN DEFAULT 1,
    elimination_status TEXT DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id),
    FOREIGN KEY (seller_entity_id) REFERENCES dap_group_entities(entity_id),
    FOREIGN KEY (buyer_entity_id) REFERENCES dap_group_entities(entity_id)
);

-- 抵消分录表
CREATE TABLE dap_elimination_entries (
    entry_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    consolidation_id TEXT,  -- 关联合并报表批次
    fiscal_period TEXT NOT NULL,
    elimination_type TEXT,  -- '长投抵消', '内部往来', '存货利润'等
    elimination_step INTEGER,  -- 八大步骤序号
    transaction_id TEXT,  -- 关联内部交易ID
    debit_account_code TEXT NOT NULL,
    debit_account_name TEXT,
    credit_account_code TEXT NOT NULL,
    credit_account_name TEXT,
    amount DECIMAL(18,2) NOT NULL,
    description TEXT,
    is_auto_generated BOOLEAN DEFAULT 1,
    is_applied BOOLEAN DEFAULT 0,
    created_by TEXT DEFAULT 'system',
    reviewed_by TEXT,
    approved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id),
    FOREIGN KEY (transaction_id) REFERENCES dap_internal_transactions(transaction_id)
);

-- 合并报表元数据表
CREATE TABLE dap_consolidations (
    consolidation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    parent_entity_id TEXT NOT NULL,
    fiscal_period TEXT NOT NULL,
    consolidation_method TEXT CHECK(consolidation_method IN ('hierarchical', 'overall')),
    scope_entity_ids TEXT,  -- JSON数组
    scope_entity_count INTEGER,
    total_elimination_entries INTEGER DEFAULT 0,
    total_elimination_amount DECIMAL(18,2) DEFAULT 0,
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'in_progress', 'completed', 'approved')),
    report_generated BOOLEAN DEFAULT 0,
    report_path TEXT,
    generated_by TEXT,
    generated_at TIMESTAMP,
    approved_by TEXT,
    approved_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES dap_projects(project_id),
    FOREIGN KEY (parent_entity_id) REFERENCES dap_group_entities(entity_id)
);
```

### Day 13-18: 合并报表引擎核心逻辑

**任务2.2**: 开发 `layer2/consolidation_engine.py` 增强版
- **负责人**: Python高级开发
- **工时**: 6天
- **关键功能**:

```python
# Day 13-14: 合并主流程
class ConsolidationEngine:
    def consolidate_by_hierarchy(...)  # 按层次合并
    def consolidate_overall(...)       # 整体合并
    def generate_consolidated_report(...)  # 生成合并报表

# Day 15-16: 抵消分录生成 (八大步骤)
    def generate_elimination_entries(...)
    def _step1_eliminate_equity_investment(...)  # 长投抵消
    def _step2_eliminate_internal_receivables(...)  # 内部往来
    def _step3_eliminate_inventory_profit(...)  # 存货未实现利润
    def _step4_eliminate_fixed_assets(...)  # 固定资产交易
    def _step5_eliminate_intangible_assets(...)  # 无形资产交易
    def _step6_adjust_retained_earnings(...)  # 盈余公积调整
    def _step7_eliminate_impairment(...)  # 减值准备
    def _step8_eliminate_cash_flow(...)  # 现金流量表抵消

# Day 17-18: 内部交易识别与匹配
    def identify_internal_transactions(...)  # 识别内部交易
    def auto_match_receivables_payables(...)  # 自动匹配应收应付
    def auto_match_inventory_sales(...)  # 自动匹配存货销售
```

**验收标准**:
- [ ] 支持3层级集团合并
- [ ] 自动识别内部往来准确率 > 85%
- [ ] 抵消分录逻辑正确性验证 (会计恒等式)
- [ ] 性能: 100家子公司合并 < 30秒

### Day 19-22: 合并报表Web API

**任务2.3**: 开发合并报表API路由
- **负责人**: 后端开发
- **工时**: 4天

```python
# RESTful API
POST   /api/consolidations                         # 创建合并任务
GET    /api/consolidations/<consolidation_id>      # 获取合并结果
GET    /api/consolidations/<consolidation_id>/eliminations  # 获取抵消分录
POST   /api/consolidations/<consolidation_id>/approve      # 审批合并报表
GET    /api/internal-transactions                  # 查询内部交易
POST   /api/internal-transactions/identify         # 自动识别内部交易
PUT    /api/elimination-entries/<entry_id>         # 手动调整抵消分录
```

### Day 23-25: 前端界面开发

**任务2.4**: 开发合并报表管理界面
- **负责人**: 前端开发
- **工时**: 3天
- **交付物**:
  - `web_gui/static/js/pages/ConsolidationManagement.js`
  - 合并范围选择器
  - 抵消分录工作底稿展示
  - 合并报表预览

**Sprint 2 验收标准**:
- [ ] 完成3层级按整体合并测试
- [ ] 八大抵消分录全部实现
- [ ] 前端界面可用性测试通过
- [ ] 集成测试: 端到端合并流程

---

## 🎯 Sprint 3: 审计底稿系统 (Week 6-9, 20工作日)

### 目标
- 底稿模板库建设 (20+模板)
- 自动填写引擎开发
- 索引号管理系统
- 分级复核流程
- 批注与留痕系统

### Day 26-28: 数据库Schema - 底稿系统

**任务3.1**: 创建底稿系统相关表
- **负责人**: 后端开发
- **工时**: 1天
- **交付物**: `migrations/004_workpaper_system.sql`

```sql
-- 见方案文档第525-579行
-- (底稿模板表、底稿实例表、批注表、索引号关联表)
```

### Day 28-30: 底稿模板库建设

**任务3.2**: 制作Excel底稿模板
- **负责人**: 审计专家 + 前端开发
- **工时**: 3天
- **交付物**: 20个Excel模板

**优先级1 (必须)**: 10个模板
1. A-1-01: 货币资金 - 库存现金盘点表
2. A-1-02: 货币资金 - 银行存款审定表
3. A-2-01: 应收账款 - 账龄分析表
4. A-2-02: 应收账款 - 函证汇总表
5. A-3-01: 存货 - 盘点汇总表
6. A-3-02: 存货 - 跌价准备计算表
7. A-4-01: 固定资产 - 固定资产清单
8. A-5-01: 应付账款 - 明细表
9. B-1-01: 收入 - 收入确认测试表
10. C-1-01: 合并报表 - 抵消分录汇总表

**优先级2 (可选)**: 10个模板
11. 长期股权投资审定表
12. 无形资产审定表
13. 短期借款审定表
14. 长期借款审定表
15. 其他应收款审定表
16. 预收账款审定表
17. 费用分析表
18. 资产负债表审定表
19. 利润表审定表
20. 现金流量表审定表

**模板设计规范**:
```
每个模板必须包含:
├─ 标准页眉 (项目名称、会计期间、索引号)
├─ 数据区域 (清晰定义开始行/结束行)
├─ 自动取数标记 ({{account_code}}, {{period}}等)
├─ 公式区域 (求和、计算等)
├─ 审计结论区域
└─ 编制人/复核人签字区域
```

### Day 31-38: 底稿管理引擎开发

**任务3.3**: 开发 `layer3/workpaper_manager.py`
- **负责人**: Python开发
- **工时**: 8天

```python
# Day 31-33: 底稿核心功能
class WorkpaperManager:
    def create_from_template(...)  # 从模板创建底稿
    def fill_with_data(...)        # 自动填写数据
    def save_workpaper(...)        # 保存底稿
    def generate_excel(...)        # 生成Excel文件

# Day 34-35: 索引号管理
class IndexManager:
    def generate_index_number(...)  # 生成索引号
    def link_workpapers(...)        # 关联底稿索引
    def get_related_workpapers(...) # 获取关联底稿
    def validate_index(...)         # 验证索引号唯一性

# Day 36-37: 复核流程
class ReviewWorkflow:
    def submit_for_review(...)  # 提交复核
    def approve_review(...)     # 批准复核
    def reject_review(...)      # 退回修改
    def get_review_chain(...)   # 获取复核链

# Day 38: 批注系统
class CommentManager:
    def add_comment(...)        # 添加批注
    def reply_comment(...)      # 回复批注
    def resolve_comment(...)    # 解决批注
    def get_comments(...)       # 获取批注列表
```

### Day 39-42: 自动填写引擎

**任务3.4**: 开发 `layer3/auto_fill_engine.py`
- **负责人**: Python开发
- **工时**: 4天

```python
class AutoFillEngine:
    """智能取数引擎"""

    # 支持的数据源类型
    DATA_SOURCES = {
        'account_balance': '科目余额',
        'voucher_detail': '凭证明细',
        'account_detail': '科目明细账',
        'aging_analysis': '账龄分析',
        'custom_sql': '自定义SQL',
        'api_call': 'API调用'
    }

    def parse_template_placeholders(...)  # 解析模板占位符
    def fetch_data_by_rule(...)           # 根据规则取数
    def apply_data_to_excel(...)          # 填充数据到Excel
    def preserve_formulas(...)            # 保留Excel公式
```

### Day 43-45: 前端底稿界面

**任务3.5**: 开发底稿管理前端
- **负责人**: 前端开发
- **工时**: 3天
- **交付物**:
  - 底稿列表页面
  - 底稿创建向导
  - 底稿在线预览 (基于SheetJS/Luckysheet)
  - 批注界面
  - 复核流程界面

**Sprint 3 验收标准**:
- [ ] 20个底稿模板全部可用
- [ ] 自动填写引擎准确率 > 90%
- [ ] 三级复核流程测试通过
- [ ] 批注系统可用性测试

---

## 🎯 Sprint 4: 协同审计功能 (Week 10-11, 10工作日)

### 目标
- 审计组管理
- 任务分配系统
- 进度看板
- 通知与提醒

### Day 46-48: 审计组管理后端

**任务4.1**: 开发 `layer0/audit_team_manager.py`
- **负责人**: Python开发
- **工时**: 3天

```python
class AuditTeamManager:
    def create_team(...)        # 创建审计组
    def assign_role(...)        # 分配角色
    def assign_task(...)        # 分配任务
    def update_task_status(...) # 更新任务状态
    def get_team_workload(...)  # 获取团队工作量
```

### Day 49-52: 进度看板开发

**任务4.2**: 开发项目进度看板
- **负责人**: 全栈开发
- **工时**: 4天
- **后端API**:
```python
GET /api/projects/<project_id>/dashboard   # 获取看板数据
GET /api/projects/<project_id>/tasks       # 任务列表
POST /api/tasks                             # 创建任务
PUT /api/tasks/<task_id>                    # 更新任务
```

- **前端组件**:
  - 甘特图 (基于Frappe Gantt或dhtmlxGantt)
  - 任务卡片看板 (Kanban)
  - 成员工作量图表 (ECharts)
  - 底稿完成进度条

### Day 53-55: 通知与提醒系统

**任务4.3**: 开发通知系统
- **负责人**: 后端开发
- **工时**: 3天

```python
# 通知引擎
class NotificationManager:
    def send_notification(...)    # 发送通知
    def send_email(...)            # 邮件通知
    def send_sms(...)              # 短信通知 (可选)
    def send_websocket_msg(...)    # 实时推送

# 提醒规则
REMINDER_RULES = [
    '任务截止前3天提醒',
    '底稿提交复核时通知复核人',
    '批注被回复时通知',
    '任务超期时每天提醒',
]
```

**Sprint 4 验收标准**:
- [ ] 审计组管理完整流程测试
- [ ] 看板数据实时更新
- [ ] 通知系统可靠性测试
- [ ] 多用户协同测试

---

## 🎯 Sprint 5: 测试与优化 (Week 12-13, 10工作日)

### Day 56-58: 功能测试

**任务5.1**: 编写测试用例
- **负责人**: 测试工程师
- **工时**: 3天
- **测试清单**:

```
功能测试 (100+用例):
├─ 集团层级管理 (15用例)
├─ 合并报表引擎 (30用例)
├─ 底稿系统 (40用例)
└─ 协同功能 (15用例)

集成测试 (10场景):
├─ 单体公司审计完整流程
├─ 3层级集团合并审计流程
├─ 多人协同审计流程
└─ 数据导入→合并→底稿→输出

性能测试 (5项指标):
├─ 1000个实体加载时间 < 3秒
├─ 100家子公司合并 < 30秒
├─ 底稿生成 < 5秒
├─ 并发50用户系统响应 < 2秒
└─ 数据库查询响应 < 500ms
```

### Day 59-61: Bug修复

**任务5.2**: 修复测试发现的问题
- **负责人**: 开发团队
- **工时**: 3天
- **优先级**:
  - P0 (阻塞性Bug): 立即修复
  - P1 (严重Bug): 当天修复
  - P2 (一般Bug): 本周修复
  - P3 (建议): 记录到Backlog

### Day 62-63: 性能优化

**任务5.3**: 系统性能优化
- **负责人**: 高级开发
- **工时**: 2天

```
优化清单:
├─ 数据库查询优化 (添加索引、优化SQL)
├─ 前端渲染优化 (虚拟列表、懒加载)
├─ API响应优化 (缓存、异步处理)
└─ 大文件处理优化 (流式处理)
```

### Day 64-65: 文档编写与部署

**任务5.4**: 编写文档并部署
- **负责人**: 技术文档工程师
- **工时**: 2天
- **交付物**:

```
文档清单:
├─ 用户手册 (50页)
│   ├─ 快速入门指南
│   ├─ 集团层级管理教程
│   ├─ 合并报表操作手册
│   └─ 审计底稿使用指南
├─ 开发文档 (30页)
│   ├─ API接口文档
│   ├─ 数据库Schema文档
│   └─ 部署运维手册
└─ 底稿模板制作指南 (20页)
```

---

## 📦 交付物清单

### 代码模块 (新增/修改)

```
D:\DAP\
├─ migrations/           # 数据库迁移脚本
│   ├─ 001_group_hierarchy.sql
│   ├─ 002_audit_collaboration.sql
│   ├─ 003_consolidation_engine.sql
│   └─ 004_workpaper_system.sql
│
├─ layer0/               # 新增Layer
│   ├─ audit_team_manager.py
│   └─ notification_manager.py
│
├─ layer2/               # 增强
│   ├─ group_hierarchy_manager.py (完善)
│   ├─ consolidation_engine.py (完善)
│   └─ internal_transaction_matcher.py (新增)
│
├─ layer3/               # 新增Layer
│   ├─ workpaper_manager.py
│   ├─ template_parser.py
│   ├─ auto_fill_engine.py
│   ├─ index_manager.py
│   ├─ review_workflow.py
│   └─ comment_manager.py
│
├─ web_gui/
│   ├─ routes/
│   │   ├─ group_hierarchy_routes.py
│   │   ├─ consolidation_routes.py
│   │   ├─ workpaper_routes.py
│   │   └─ task_routes.py
│   │
│   ├─ static/
│   │   ├─ js/
│   │   │   ├─ components/
│   │   │   │   ├─ HierarchyTree.js
│   │   │   │   ├─ ConsolidationWizard.js
│   │   │   │   ├─ WorkpaperViewer.js
│   │   │   │   └─ TaskKanban.js
│   │   │   └─ pages/
│   │   │       ├─ GroupManagement.js
│   │   │       ├─ ConsolidationPage.js
│   │   │       ├─ WorkpaperPage.js
│   │   │       └─ AuditDashboard.js
│   │   └─ css/
│   │       ├─ hierarchy-tree.css
│   │       ├─ consolidation.css
│   │       └─ workpaper.css
│   │
│   └─ templates/
│       └─ workpapers/        # Excel模板库
│           ├─ A-1-01_库存现金.xlsx
│           ├─ A-1-02_银行存款.xlsx
│           ├─ ... (共20个)
│           └─ template_config.json
│
└─ tests/                # 测试用例
    ├─ test_group_hierarchy.py
    ├─ test_consolidation.py
    ├─ test_workpaper.py
    └─ test_integration.py
```

### 数据库表 (新增)

```
新增表 (10张):
├─ dap_group_entities
├─ dap_entity_paths
├─ dap_audit_teams
├─ dap_audit_tasks
├─ dap_internal_transactions
├─ dap_elimination_entries
├─ dap_consolidations
├─ dap_workpaper_templates
├─ dap_workpapers
└─ dap_workpaper_comments
```

---

## 👥 团队分工建议

### 角色配置 (5人团队)

| 角色 | 人数 | 主要职责 | 技能要求 |
|------|------|---------|---------|
| **后端开发** | 2人 | Python API开发、数据库设计、业务逻辑 | Python, Flask/FastAPI, SQLite, 审计知识 |
| **前端开发** | 1人 | Web界面、组件开发、用户体验优化 | JavaScript, React/Vue, CSS, HTML5 |
| **全栈开发** | 1人 | 前后端联调、复杂功能实现、技术攻关 | Python + JavaScript, 架构设计 |
| **测试+文档** | 1人 | 测试用例编写、Bug跟踪、文档编写 | 测试框架, 文档写作 |

---

## 📊 里程碑与验收

### Milestone 1: 基础架构完成 (Week 2结束)
- [ ] 集团层级管理API全部可用
- [ ] 前端层级树组件正常运行
- [ ] 支持6层级结构
- [ ] 性能测试通过

### Milestone 2: 合并报表引擎完成 (Week 5结束)
- [ ] 按整体合并功能可用
- [ ] 八大抵消分录自动生成
- [ ] 内部往来识别准确率 > 85%
- [ ] 端到端合并测试通过

### Milestone 3: 审计底稿系统完成 (Week 9结束)
- [ ] 20个底稿模板全部可用
- [ ] 自动填写准确率 > 90%
- [ ] 三级复核流程完整
- [ ] 底稿界面可用性良好

### Milestone 4: 系统整体完成 (Week 13结束)
- [ ] 所有功能测试通过
- [ ] 性能指标达标
- [ ] 文档齐全
- [ ] 用户培训完成

---

## 🔥 风险管理

### 高风险项

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **合并逻辑复杂度超预期** | 高 | 中 | 提前咨询审计专家,分步实现,先支持简单场景 |
| **底稿模板制作周期长** | 中 | 高 | 与审计专家并行工作,优先完成10个核心模板 |
| **性能优化难度大** | 中 | 中 | 预留专门的优化时间,必要时引入缓存/异步处理 |
| **团队成员不熟悉审计业务** | 高 | 中 | 开发前进行审计知识培训,配备审计顾问 |

---

## 🎯 MVP范围界定

**如果时间紧张,可以先实现MVP版本 (8周)**:

### MVP功能范围

```
Phase 1: 基础功能 (2周)
├─ 集团层级管理 (仅支持3层级)
└─ 基础API

Phase 2: 简化合并 (3周)
├─ 按整体合并 (不支持按层次)
├─ 前5大抵消分录
└─ 手动确认内部交易

Phase 3: 核心底稿 (2周)
├─ 10个核心底稿模板
├─ 简化自动填写
└─ 二级复核 (去掉第三级)

Phase 4: 测试上线 (1周)
├─ 功能测试
└─ 文档编写
```

---

## 📞 每日站会与周报

### 每日站会 (15分钟)
- 时间: 每天上午9:30
- 内容:
  - 昨天完成了什么?
  - 今天计划做什么?
  - 有什么阻塞问题?

### 周报模板
```
DAP v2.0 开发周报 - Week X

【本周完成】
- 功能1: 描述
- 功能2: 描述

【下周计划】
- 任务1
- 任务2

【遇到的问题】
- 问题1: 解决方案
- 问题2: 需要协助

【风险预警】
- 风险1: 缓解措施
```

---

## ✅ 开始开发检查清单

在开始开发前,请确认:

- [ ] 开发环境已搭建 (Python 3.8+, Node.js 14+)
- [ ] 代码仓库已创建分支 `feature/dap-v2.0`
- [ ] 团队成员已分配角色
- [ ] 审计专家已确认可配合
- [ ] 项目管理工具已配置 (Jira/Trello/GitHub Projects)
- [ ] 沟通渠道已建立 (钉钉/企业微信/Slack)
- [ ] 开发规范已确定 (代码风格、Git流程、CR规则)

---

**计划制定人**: Claude Code
**审核**: 待项目负责人确认
**开始日期**: 待定
**预计结束**: 开始后13周

---

## 🚀 立即开始?

如果您认可这个开发计划,我可以:

1. **立即开始Sprint 1 Day 1的工作** - 创建数据库migration脚本
2. **生成项目看板** - 导出到Jira/GitHub Projects格式
3. **创建开发分支** - 设置Git工作流
4. **编写第一个模块** - 从集团层级管理开始

**请确认是否开始开发!** 🎯
