# 财务数据钻取功能使用指南

## 概述

财务数据钻取系统参考用友、金蝶、鼎信诺和新纪元等主流财务软件的优秀设计，提供多级数据钻取、智能导航、高级过滤和数据导出等功能。

## 功能特点

### 1. 多级钻取路径

系统支持以下钻取路径:

```
┌─────────────────────────────────────────────────────────────┐
│              财务报表 (Financial Statements)          │
│           资产负债表 / 利润表 / 现金流量表            │
└────────────────────┬────────────────────────────────┘
                     │ 点击报表项目
                     ▼
┌─────────────────────────────────────────────────────┐
│              科目余额表 (Trial Balance)               │
│         显示所有科目的期初/期末/发生额               │
└────────────────────┬────────────────────────────────┘
                     │ 点击科目
                     ▼
┌─────────────────────────────────────────────────────┐
│             科目明细账 (Account Ledger)               │
│      显示该科目的所有交易明细 (按日期排序)           │
└────────────────────┬────────────────────────────────┘
                     │ 点击凭证号
                     ▼
┌─────────────────────────────────────────────────────┐
│              凭证详情 (Voucher Detail)                │
│       显示完整的会计分录 (借贷双方 + 附件)           │
└────────────────────┬────────────────────────────────┘
                     │ 查看附件
                     ▼
┌─────────────────────────────────────────────────────┐
│           原始单据 (Source Documents)                 │
│         发票/合同/银行回单等附件图片                  │
└─────────────────────────────────────────────────────┘
```

### 2. 核心功能

- **多维度过滤**: 支持按金额范围、对方科目、摘要关键字等多维度筛选
- **智能建议**: 根据当前上下文自动推荐可用的钻取操作
- **面包屑导航**: 清晰显示当前位置,支持快速返回任意层级
- **批量操作**: 支持批量钻取多个科目进行对比分析
- **数据导出**: 支持导出为Excel、PDF、CSV等多种格式
- **收藏夹**: 保存常用查询,快速访问

## API 使用指南

### 1. 获取可用钻取路径

```python
# Python后端调用
from layer4.financial_drilldown_engine import FinancialDrilldownEngine

engine = FinancialDrilldownEngine('data/dap_data.db')
paths = engine.get_drilldown_paths(company_id=1)

print(paths)
# 输出包含所有可用钻取路径的列表
```

```javascript
// JavaScript前端调用
const drilldownManager = new FinancialDrilldownManager();
drilldownManager.setCompanyId(1);

const paths = await drilldownManager.getAvailablePaths();
console.log(paths);
```

### 2. 资产负债表钻取

```python
# Python示例
result = engine.drill_balance_sheet_item(
    company_id=1,
    period='202412',
    item_name='应收账款',
    filters={
        'min_amount': 10000,  # 只显示余额大于1万的科目
        'account_code_prefix': '1122'  # 限定科目前缀
    }
)

if result['success']:
    accounts = result['accounts']
    summary = result['summary']
    print(f"找到 {len(accounts)} 个科目")
    print(f"期末余额合计: {summary['total_ending_balance']}")
```

```javascript
// JavaScript示例
const result = await drilldownManager.drillBalanceSheetItem(
    '202412',
    '应收账款',
    {
        min_amount: 10000,
        account_code_prefix: '1122'
    }
);

if (result.success) {
    drilldownManager.renderAccountBalanceTable(
        result.accounts,
        'accounts-container'
    );
}
```

### 3. 科目明细账钻取

```python
# Python示例
result = engine.drill_account_ledger(
    company_id=1,
    account_code='1122',
    period_start='202401',
    period_end='202412',
    filters={
        'min_amount': 5000,  # 只显示大于5000的交易
        'opposite_account': '6001',  # 只显示与6001相关的交易
        'summary_keyword': '销售'  # 摘要包含"销售"
    }
)

if result['success']:
    entries = result['entries']
    summary = result['summary']
    print(f"找到 {summary['entry_count']} 笔交易")
    print(f"借方合计: {summary['total_debit']}")
    print(f"贷方合计: {summary['total_credit']}")
    print(f"期末余额: {summary['ending_balance']}")
```

```javascript
// JavaScript示例
const result = await drilldownManager.drillAccountLedger(
    '1122',  // 应收账款
    '202401',
    '202412',
    {
        min_amount: 5000,
        opposite_account: '6001',
        summary_keyword: '销售'
    }
);

if (result.success) {
    drilldownManager.renderAccountLedger(
        result.entries,
        result.account_info,
        'ledger-container'
    );
}
```

### 4. 凭证详情钻取

```python
# Python示例
result = engine.drill_voucher_detail(
    company_id=1,
    voucher_id=12345
)

if result['success']:
    header = result['voucher_header']
    entries = result['entries']
    summary = result['summary']
    audit_info = result['audit_info']

    print(f"凭证号: {header['voucher_number']}")
    print(f"日期: {header['voucher_date']}")
    print(f"分录数: {len(entries)}")
    print(f"借贷平衡: {'是' if summary['is_balanced'] else '否'}")
    print(f"已审核: {'是' if audit_info['is_reviewed'] else '否'}")
    print(f"已过账: {'是' if audit_info['is_posted'] else '否'}")
```

```javascript
// JavaScript示例
const result = await drilldownManager.drillVoucherDetail(12345);

if (result.success) {
    drilldownManager.renderVoucherDetail(
        result,
        'voucher-container'
    );
}
```

### 5. 批量科目钻取

```python
# Python示例 - 批量对比多个科目
result = engine.batch_drill_accounts(
    company_id=1,
    account_codes=['1001', '1002', '1122', '2202'],
    period='202412'
)

if result['success']:
    for account_code, account_result in result['results'].items():
        if account_result['success']:
            summary = account_result['summary']
            print(f"{account_code}: 期末余额 {summary['ending_balance']}")
```

```javascript
// JavaScript示例
const result = await drilldownManager.batchDrillAccounts(
    ['1001', '1002', '1122', '2202'],
    '202412'
);

if (result.success) {
    // 处理批量结果
    for (const [accountCode, accountResult] of Object.entries(result.results)) {
        console.log(`${accountCode}: ${accountResult.summary.ending_balance}`);
    }
}
```

### 6. 智能钻取建议

```python
# Python示例
suggestions = engine.suggest_drill_paths(
    company_id=1,
    current_context={
        'type': 'account',
        'account_code': '1122'
    }
)

for suggestion in suggestions:
    print(f"{suggestion['description']} (优先级: {suggestion['priority']})")
```

```javascript
// JavaScript示例
const suggestions = await drilldownManager.getSuggestions({
    type: 'account',
    account_code: '1122'
});

suggestions.forEach(suggestion => {
    console.log(`${suggestion.description} (优先级: ${suggestion.priority})`);
});
```

### 7. 数据导出

```python
# Python示例
export_result = engine.export_drill_result(
    drill_data=result,
    export_format='excel',
    output_path='exports/drill_result.xlsx'
)

if export_result['success']:
    print(f"导出成功: {export_result['output_path']}")
```

```javascript
// JavaScript示例
const exportResult = await drilldownManager.exportDrillResult(
    result,
    'excel'
);

if (exportResult.success) {
    alert(`导出成功: ${exportResult.output_path}`);
}
```

## 前端集成示例

### HTML页面结构

```html
<!DOCTYPE html>
<html>
<head>
    <title>财务数据钻取</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
</head>
<body>
    <div class="container mt-4">
        <!-- 面包屑导航 -->
        <div id="drill-breadcrumb"></div>

        <!-- 操作按钮 -->
        <div class="mb-3">
            <button class="btn btn-secondary" onclick="drilldownManager.goBack()">
                ← 返回上一级
            </button>
            <button class="btn btn-primary" onclick="exportCurrentView()">
                导出当前数据
            </button>
            <button class="btn btn-info" onclick="addToFavorites()">
                ★ 添加到收藏
            </button>
        </div>

        <!-- 数据显示容器 -->
        <div id="data-container"></div>
    </div>

    <!-- 引入JavaScript -->
    <script src="/static/financial_drilldown.js"></script>
    <script>
        // 初始化
        drilldownManager.setCompanyId(1);

        // 示例: 从资产负债表开始钻取
        async function startDrill() {
            drilldownManager.showLoading('data-container');

            try {
                const result = await drilldownManager.drillBalanceSheetItem(
                    '202412',
                    '应收账款'
                );

                if (result.success) {
                    drilldownManager.renderAccountBalanceTable(
                        result.accounts,
                        'data-container'
                    );
                }
            } catch (error) {
                drilldownManager.showError('data-container', error.message);
            }
        }

        // 导出当前视图
        async function exportCurrentView() {
            const current = drilldownManager.getCurrentLevel();
            if (current) {
                await drilldownManager.exportDrillResult(current.data, 'excel');
            }
        }

        // 添加到收藏
        function addToFavorites() {
            const current = drilldownManager.getCurrentLevel();
            if (current) {
                const name = prompt('请输入收藏名称:');
                if (name) {
                    drilldownManager.addToFavorites(name, current.params);
                    alert('已添加到收藏夹');
                }
            }
        }
    </script>
</body>
</html>
```

## 高级功能

### 1. 使用面包屑导航

```javascript
// 面包屑会自动显示完整的钻取路径
// 用户可以点击任意层级快速返回

// 示例: 首页 > 资产负债表 > 科目明细账 > 凭证详情
//       ↑       ↑           ↑           当前位置
//       可点击   可点击      可点击
```

### 2. 键盘快捷键

- **Alt + ←**: 返回上一级
- **Alt + H**: 显示钻取历史

### 3. 收藏夹管理

```javascript
// 添加收藏
const favorite = drilldownManager.addToFavorites('常用查询1', {
    account_code: '1122',
    period: '202412'
});

// 查看所有收藏
console.log(drilldownManager.favorites);

// 删除收藏
drilldownManager.removeFromFavorites(favorite.id);
```

## REST API 端点

### 获取钻取路径
```
GET /api/drilldown/paths/<company_id>
```

### 资产负债表钻取
```
POST /api/drilldown/balance-sheet
Content-Type: application/json

{
    "company_id": 1,
    "period": "202412",
    "item_name": "应收账款",
    "filters": {
        "min_amount": 10000
    }
}
```

### 科目明细账钻取
```
POST /api/drilldown/account-ledger
Content-Type: application/json

{
    "company_id": 1,
    "account_code": "1122",
    "period_start": "202401",
    "period_end": "202412",
    "filters": {}
}
```

### 凭证详情钻取
```
GET /api/drilldown/voucher/<company_id>/<voucher_id>
```

### 批量科目钻取
```
POST /api/drilldown/batch-accounts
Content-Type: application/json

{
    "company_id": 1,
    "account_codes": ["1001", "1002", "1122"],
    "period": "202412"
}
```

### 智能建议
```
POST /api/drilldown/suggest
Content-Type: application/json

{
    "company_id": 1,
    "context": {
        "type": "account",
        "account_code": "1122"
    }
}
```

### 导出钻取结果
```
POST /api/drilldown/export
Content-Type: application/json

{
    "drill_data": { ... },
    "format": "excel",
    "output_path": "exports/result.xlsx"
}
```

## 最佳实践

### 1. 性能优化

- 使用过滤器减少数据量
- 分页显示大量数据
- 缓存常用查询结果

### 2. 用户体验

- 显示清晰的面包屑导航
- 提供智能建议
- 保存用户常用查询到收藏夹
- 支持键盘快捷键

### 3. 数据验证

- 检查借贷平衡
- 标记异常交易
- 显示审核状态

## 故障排除

### 问题1: 钻取功能不可用

**解决方案**:
```python
# 检查是否正确导入了钻取引擎
from layer4.financial_drilldown_engine import FinancialDrilldownEngine

# 确认数据库路径正确
engine = FinancialDrilldownEngine('data/dap_data.db')
```

### 问题2: 数据显示不完整

**解决方案**:
- 检查数据库表是否存在
- 确认数据已正确导入
- 检查过滤条件是否过于严格

### 问题3: 导出失败

**解决方案**:
```python
# 确保导出目录存在
import os
os.makedirs('exports', exist_ok=True)

# 检查是否安装了必要的库
pip install openpyxl pandas
```

## 参考资料

- [用友财务软件操作手册](https://www.yonyou.com/)
- [金蝶K3云操作指南](https://www.kingdee.com/)
- [鼎信诺审计软件使用说明](https://www.dxn.com.cn/)
- [新纪元财务数据采集工具](https://www.newageerp.com/)

## 更新日志

### v1.0.0 (2024-11-21)

**新增功能**:
- ✅ 完整的多级钻取功能
- ✅ 资产负债表、利润表钻取支持
- ✅ 科目明细账查询
- ✅ 凭证详情查看
- ✅ 批量科目钻取
- ✅ 智能钻取建议
- ✅ 多格式数据导出
- ✅ 面包屑导航
- ✅ 收藏夹功能
- ✅ 键盘快捷键支持

**参考软件**:
- 用友U8+/NC: 借鉴了其完善的科目体系和凭证管理
- 金蝶K/3 Cloud: 学习了灵活的报表钻取和数据关联
- 鼎信诺审计软件: 采纳了专业的审计功能和数据验证
- 新纪元数据采集工具: 参考了强大的数据采集和多源支持

## 联系支持

如有问题或建议,请联系开发团队:
- Email: support@dap-system.com
- GitHub: https://github.com/your-repo/dap-system

---

**版权所有 © 2024 DAP System**
