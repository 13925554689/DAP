# DAP - 数据处理审计智能体

> **Data Processing & Auditing Intelligence Agent**
> 
> AI智慧审计大脑的核心数据处理引擎

## 🎯 项目简介

DAP是一个专为审计领域设计的三层智能数据处理系统，能够自动化地接收、清洗、存储、分类并初步分析来自异构数据源的数据，为上层"AI智慧审计大脑"提供高质量、结构化、可立即使用的数据基础。

### 核心特色

- **🚀 一键启动** - 拖拽导入，零配置处理
- **🧠 智能内置** - 自动识别、推断、清洗、分类
- **🎯 审计导向** - 专为审计需求优化的所有逻辑
- **📊 科学存储** - SQLite+视图，最小内存最大效率
- **🔌 开放接口** - RESTful API + AI智能体集成

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    [交互层] 一键启动界面                         │
│                  (One-Click Launcher UI)                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              [第三层] 外部智能体接口 (Level 3)                    │
│               External Agent Interface                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  RESTful API    │  │  Agent Bridge   │  │  Export Engine  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│           [第二层] 智能分类与规整引擎 (Level 2)                   │
│         Intelligent Classification & Arrangement            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Audit Rules     │  │ Dimension       │  │ Output          │ │
│  │ Engine          │  │ Organizer       │  │ Formatter       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│         [第一层] 通用数据清洗与存储中心 (Level 1)                  │
│        Universal Data Cleansing & Storage Hub               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Data Ingestor   │  │ Schema Inferrer │  │ Data Scrubber   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                    ┌─────────────────┐                        │
│                    │ Storage Manager │                        │
│                    └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- Windows 10/11 (主要支持平台)
- 4GB+ 内存
- 1GB+ 磁盘空间

### 安装步骤

1. **下载项目**
   ```bash
   git clone https://github.com/your-repo/DAP.git
   cd DAP
   ```

2. **运行安装脚本**
   ```bash
   # Windows
   install.bat
   
   # 手动安装
   python -m venv dap_env
   dap_env\Scripts\activate
   pip install -r requirements.txt
   ```

3. **启动应用**
   ```bash
   # 图形界面模式（推荐）
   start_gui.bat
   
   # API服务模式
   start_api.bat
   
   # 命令行模式
   start_cli.bat
   ```

### 快速体验

1. **启动图形界面**
   - 双击 `start_gui.bat`
   - 界面启动后，拖拽Excel文件到导入区域
   - 点击"开始处理"按钮
   - 等待处理完成，查看结果

2. **API服务体验**
   - 双击 `start_api.bat`
   - 浏览器访问 http://127.0.0.1:8000/docs
   - 在线测试各种API接口

## 📊 支持的数据格式

| 格式类型 | 文件扩展名 | 描述 |
|---------|-----------|------|
| Excel文件 | .xlsx, .xls | Microsoft Excel工作簿 |
| CSV文件 | .csv | 逗号分隔值文件 |
| 数据库备份 | .bak, .sql | SQL Server备份文件 |
| 数据库文件 | .db, .sqlite, .mdb | SQLite、Access数据库 |
| 压缩文件 | .zip, .rar | 包含数据文件的压缩包 |
| 文件夹 | - | 包含多个数据文件的目录 |

### 运行模式切换

默认使用完整模式。如需切换到轻量桩（在依赖不全的情况下仍能启动），可以运行下列脚本：

```bash
# Windows
scripts\enable_lightweight.bat
start_one_click.bat

# 切换回完整模式
scripts\enable_full_mode.bat
start_one_click.bat
```

轻量模式仅适合快速体验 Excel/CSV 等基础操作；若要处理压缩包、数据库或生成完整报告，请保持完整模式。

## 🔧 主要功能

### 数据处理流程

1. **智能接入** - 自动识别文件格式，支持多种数据源
2. **模式推断** - 智能推断数据结构、类型和关系
3. **数据清洗** - 去重、标准化、异常值处理
4. **科学存储** - SQLite多维视图，优化查询性能
5. **智能分类** - 基于审计规则的自动分类
6. **多维组织** - 时间、业务、地域、功能维度重组
7. **AI分析** - 集成外部AI服务进行智能分析
8. **报告生成** - 多格式输出和审计报告

### 核心模块

- **Layer 1 - 数据基础层**
  - 数据接入器 (Data Ingestor)
  - 模式推断器 (Schema Inferrer) 
  - 数据清洗器 (Data Scrubber)
  - 存储管理器 (Storage Manager)

- **Layer 2 - 智能分类层**
  - 审计规则引擎 (Audit Rules Engine)
  - 维度组织器 (Dimension Organizer)
  - 输出格式化器 (Output Formatter)

- **Layer 3 - 外部接口层**
  - RESTful API服务器
  - AI智能体通信桥
  - 多格式导出引擎

## 🎨 用户界面

### 图形界面 (GUI)

- **数据导入** - 拖拽式文件导入，支持批量处理
- **系统状态** - 实时显示处理进度和系统状态
- **数据管理** - 查看表结构、视图列表、导出数据
- **AI分析** - 内置AI分析界面，支持自然语言查询

### API接口

```python
# 获取系统信息
GET /api/info

# 查看数据表
GET /api/tables

# 获取数据
GET /api/data/{table_name}

# 执行分析
POST /api/analyze

# 导出数据
POST /api/export

# 生成报告
POST /api/reports/audit
```

## 📋 配置说明

### 审计规则配置

编辑 `config/audit_rules.yaml` 文件来自定义审计规则：

```yaml
rules:
  - rule_id: 'LARGE_AMOUNT_FLAG'
    type: 'validation'
    description: '大额交易标记'
    conditions:
      - field_pattern: '*金额*|*amount*'
        operator: 'greater_than'
        value: 100000
    action:
      type: 'add_column'
      column_name: 'large_amount_flag'
      value: true
```

### AI配置

设置环境变量启用AI功能：

```bash
# OpenAI API
set OPENAI_API_KEY=your_api_key

# 本地LLM (Ollama)
# 确保本地运行 Ollama 服务
```

## 📁 项目结构

```
DAP/
├── dap_launcher.py              # 主启动界面
├── main_engine.py               # 核心处理引擎
├── layer1/                      # 第一层：数据基础
│   ├── data_ingestor.py
│   ├── schema_inferrer.py
│   ├── data_scrubber.py
│   └── storage_manager.py
├── layer2/                      # 第二层：智能分类
│   ├── audit_rules_engine.py
│   ├── dimension_organizer.py
│   └── output_formatter.py
├── layer3/                      # 第三层：外部接口
│   ├── api_server.py
│   └── agent_bridge.py
├── config/                      # 配置文件
│   └── audit_rules.yaml
├── data/                        # 数据目录
├── exports/                     # 导出目录
├── logs/                        # 日志目录
├── requirements.txt             # 依赖包
├── install.bat                  # 安装脚本
├── start_gui.bat               # GUI启动脚本
├── start_api.bat               # API启动脚本
└── start_cli.bat               # CLI启动脚本
```

## 🔧 高级用法

### 命令行使用

```python
from main_engine import get_dap_engine

# 获取引擎实例
engine = get_dap_engine()

# 处理数据文件
result = engine.process('data.xlsx')

# 导出数据
export_result = engine.export_data('table_name', 'excel')

# AI分析
ai_result = engine.analyze_with_ai("分析财务风险", "table_name")

# 生成报告
report_result = engine.generate_audit_report("公司名", "2024年度")
```

### API编程

```python
import requests

base_url = "http://127.0.0.1:8000"

# 获取系统信息
response = requests.get(f"{base_url}/api/info")
print(response.json())

# 查询数据
response = requests.get(f"{base_url}/api/data/table_name")
data = response.json()

# 执行分析
analysis_request = {
    "analysis_type": "financial_summary",
    "company_id": "company_001"
}
response = requests.post(f"{base_url}/api/analyze", json=analysis_request)
```

## 🛠️ 性能优化

### 处理大数据集

- 使用分块处理：单次处理限制在1GB以内
- 启用并行处理：配置 `parallel_workers` 参数
- 内存优化：使用列式存储和数据压缩

### 性能监控

- 查看处理日志：`logs/dap.log`
- 监控内存使用：任务管理器
- API性能：访问 `/api/stats` 端点

## 📈 扩展开发

### 添加新的数据源

1. 在 `layer1/data_ingestor.py` 中添加新的处理器
2. 实现 `process()` 方法
3. 注册到 `handlers` 字典

### 自定义审计规则

1. 编辑 `config/audit_rules.yaml`
2. 定义新的规则类型和条件
3. 重启系统应用新规则

### 集成新的AI服务

1. 在 `layer3/agent_bridge.py` 中添加新的客户端
2. 实现 `AIClient` 接口
3. 注册到 `ai_clients` 字典

## 🐛 故障排除

### 常见问题

**Q: 安装依赖失败**
```bash
# 解决方案：使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

**Q: 图形界面无法启动**
```bash
# 解决方案：安装tkinterdnd2
pip install tkinterdnd2
```

**Q: API服务端口被占用**
```bash
# 解决方案：更改端口
python -c "from layer3.api_server import start_api_server; start_api_server(port=8001)"
```

**Q: 数据库锁定错误**
```bash
# 解决方案：关闭所有DAP进程，删除数据库锁文件
del data\dap_data.db-wal
del data\dap_data.db-shm
```

### 日志分析

- 系统日志：`logs/dap.log`
- 审计规则日志：`logs/audit_rules.log`
- API访问日志：控制台输出

## ☁️ GitHub 自动备份

系统现已支持将指定目录的运行成果自动打包并上传至 GitHub 仓库，用于云端备份或多端协同。启用步骤如下：

- 在运行环境中设置 `DAP_GITHUB_BACKUP_ENABLED=true`
- 提供目标仓库 `DAP_GITHUB_BACKUP_REPO=org/project` 以及访问令牌 `DAP_GITHUB_TOKEN`
- 可选参数：
  - `DAP_GITHUB_BACKUP_BRANCH`：提交分支，默认为 `main`
  - `DAP_GITHUB_BACKUP_PATHS`：分号或逗号分隔的备份目录，默认为 `data;exports`
  - `DAP_GITHUB_BACKUP_INTERVAL_MINUTES`：定时备份间隔（分钟）
  - `DAP_GITHUB_BACKUP_COMMIT_MESSAGE`：提交消息模板，支持 `{timestamp}`、`{files}`、`{trigger}`
- 项目启动时会自动开启备份线程并立即执行一次备份；在执行 `process()` 或 `import_data_file()` 等修改数据前也会自动触发一次备份，确保操作可追溯
- 运行时可通过 `EnhancedDAPEngine.trigger_github_backup()` 立即触发备份，并在引擎关闭时自动释放后台任务

> ⚠️ GitHub 访问令牌仅需 `repo` 范围权限，请以环境变量方式安全注入，避免写入配置文件。

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🎯 路线图

### v1.1 (计划中)
- [ ] 支持更多数据库类型 (PostgreSQL, MySQL)
- [ ] 增强AI分析能力
- [ ] 添加实时数据监控
- [ ] 优化大数据处理性能

### v1.2 (规划中) 
- [ ] 分布式处理支持
- [ ] 云服务集成
- [ ] 移动端支持
- [ ] 多语言界面

## 📞 联系我们

- 项目主页：[GitHub Repository](https://github.com/your-repo/DAP)
- 问题反馈：[Issues](https://github.com/your-repo/DAP/issues)
- 技术文档：[Wiki](https://github.com/your-repo/DAP/wiki)

## 🙏 致谢

感谢所有为DAP项目做出贡献的开发者和使用者！

---

**DAP - Data Processing & Auditing Intelligence Agent**  
*让数据处理更智能，让审计分析更高效*
