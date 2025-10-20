# DAP GitHub 自动备份部署指南

## 快速开始

### 方式1: 一键配置向导 (推荐)

```bash
setup_github_backup.bat
```

交互式配置工具会引导您完成所有配置步骤。

### 方式2: 手动配置

#### 1. 获取 GitHub Token

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择权限：
   - ✓ repo (完整仓库访问权限)
4. 生成并复制 token

#### 2. 配置环境变量

复制 `.env.example` 为 `.env`:

```bash
copy .env.example .env
```

编辑 `.env` 文件，填入以下关键信息:

```env
# 必填项
DAP_GITHUB_BACKUP_ENABLED=true
DAP_GITHUB_BACKUP_REPO=13925554689/DAP
DAP_GITHUB_TOKEN=your_github_token_here

# 可选项
DAP_GITHUB_BACKUP_BRANCH=main
DAP_GITHUB_BACKUP_INTERVAL_MINUTES=120
```

#### 3. 运行部署脚本

```bash
deploy_github.bat
```

该脚本会:
- 检查依赖
- 验证配置
- 执行测试备份
- 创建自动备份服务

## 启动自动备份服务

### 方式1: 命令行运行 (前台)

```bash
start_github_backup.bat
```

服务会持续运行，按配置间隔自动备份。按 Ctrl+C 停止。

### 方式2: Windows 计划任务 (后台)

1. 打开 "任务计划程序" (Task Scheduler)
2. 创建基本任务
3. 设置触发器：
   - 每天运行
   - 或每 2 小时运行一次
4. 操作：启动程序
   - 程序: `D:\DAP\start_github_backup.bat`
   - 起始于: `D:\DAP`

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DAP_GITHUB_BACKUP_ENABLED` | 是否启用备份 | false |
| `DAP_GITHUB_BACKUP_REPO` | GitHub仓库 (格式: owner/repo) | - |
| `DAP_GITHUB_TOKEN` | GitHub访问令牌 | - |
| `DAP_GITHUB_BACKUP_BRANCH` | 目标分支 | main |
| `DAP_GITHUB_BACKUP_INTERVAL_MINUTES` | 备份间隔(分钟) | 120 |
| `DAP_GITHUB_BACKUP_PATHS` | 备份路径(逗号分隔) | data,exports,config,... |
| `DAP_GITHUB_BACKUP_REMOTE_PATH` | 远程存储路径 | backups |

### 备份内容

默认备份以下内容:
- `data/` - 数据文件
- `exports/` - 导出文件
- `config/` - 配置文件
- `layer1/` 到 `layer5/` - 核心代码
- `main_engine.py`, `dap_launcher.py` - 主程序

您可以通过 `DAP_GITHUB_BACKUP_PATHS` 环境变量自定义。

## 工作原理

### 备份流程

1. **打包**: 系统将配置的文件和目录打包为 ZIP 文件
2. **命名**: 使用时间戳命名 `dap-backup-YYYYMMDDTHHMMSSZ.zip`
3. **上传**: 通过 GitHub REST API 上传到指定仓库
4. **清理**: 删除临时文件

### 定时机制

- 使用后台线程实现定时任务
- 首次启动立即执行一次备份
- 之后按配置间隔定期执行
- 支持手动触发备份

### 安全性

- Token 通过环境变量管理，不会提交到仓库
- 支持 SSL 验证
- 临时文件自动清理
- 完整的错误处理和日志记录

## 验证部署

### 1. 检查配置

```bash
python -c "from config.settings import get_config; cfg = get_config(); print(f'备份启用: {cfg.github_backup.enabled}'); print(f'目标仓库: {cfg.github_backup.repository}')"
```

### 2. 手动触发备份

```python
python -c "from layer5.github_backup_manager import GitHubBackupManager; from config.settings import get_config; manager = GitHubBackupManager(get_config().github_backup); manager.run_backup('manual')"
```

### 3. 查看备份文件

访问: https://github.com/13925554689/DAP/tree/main/backups

## 故障排查

### Token 无效

**问题**: `GitHub API error (status=401)`

**解决**:
1. 确认 Token 复制完整
2. 检查 Token 权限是否包含 `repo`
3. Token 是否已过期

### 仓库不存在

**问题**: `GitHub API error (status=404)`

**解决**:
1. 确认仓库名称格式: `username/repo`
2. 确认仓库已创建
3. 确认 Token 有该仓库的访问权限

### 网络问题

**问题**: 连接超时或失败

**解决**:
1. 检查网络连接
2. 尝试访问 https://api.github.com
3. 检查防火墙设置
4. 如在国内，考虑网络代理

### 文件过大

**问题**: 上传失败 (GitHub 单文件限制 100MB)

**解决**:
1. 排除大文件目录 (如 `models/`, `vectors/`)
2. 调整 `DAP_GITHUB_BACKUP_PATHS` 配置
3. 已在 `.gitignore` 中排除大文件

## 监控和维护

### 查看日志

```bash
# 主日志
type logs\dap.log

# 备份专用日志
type logs\github_backup.log
```

### 查看状态

```python
from layer5.github_backup_manager import GitHubBackupManager
from config.settings import get_config

manager = GitHubBackupManager(get_config().github_backup)
status = manager.get_status()
print(status)
```

### 日志级别

在 `.env` 中设置:

```env
DAP_LOG_LEVEL=DEBUG  # 详细日志
DAP_LOG_LEVEL=INFO   # 正常日志 (默认)
DAP_LOG_LEVEL=WARNING  # 仅警告和错误
```

## 最佳实践

1. **定期检查**: 每周检查一次备份日志
2. **验证备份**: 定期访问 GitHub 确认备份存在
3. **Token 安全**: 不要将 Token 提交到代码仓库
4. **合理间隔**: 建议备份间隔 2-4 小时
5. **监控日志**: 配置日志告警机制

## 高级配置

### 自定义提交信息

```env
DAP_GITHUB_BACKUP_COMMIT_MESSAGE=DAP自动备份 {timestamp} - {files}个文件 [{trigger}]
```

支持的占位符:
- `{timestamp}`: 时间戳
- `{files}`: 文件数量
- `{trigger}`: 触发方式 (manual/scheduled/startup)

### 配置作者信息

```env
DAP_GITHUB_BACKUP_AUTHOR_NAME=Your Name
DAP_GITHUB_BACKUP_AUTHOR_EMAIL=your.email@example.com
```

### 多仓库备份

创建多个配置文件，使用不同的环境变量前缀。

## 技术架构

```
┌─────────────────────────────────────────┐
│  start_github_backup.py                 │
│  (后台服务)                              │
└─────────────┬───────────────────────────┘
              │
              v
┌─────────────────────────────────────────┐
│  GitHubBackupManager                    │
│  (layer5/github_backup_manager.py)      │
└─────────────┬───────────────────────────┘
              │
              ├─> 定时器线程 (Scheduler)
              ├─> ZIP 打包器
              └─> GitHub API 客户端
                   │
                   v
┌─────────────────────────────────────────┐
│  GitHub REST API                        │
│  PUT /repos/{owner}/{repo}/contents/... │
└─────────────────────────────────────────┘
```

## 相关文件

- `layer5/github_backup_manager.py` - 核心备份管理器
- `config/settings.py` - 配置管理 (GitHubBackupConfig)
- `start_github_backup.py` - 后台服务脚本
- `setup_github_backup.py` - 配置向导
- `deploy_github.bat` - 部署脚本
- `.env.example` - 配置模板

## 支持和反馈

如有问题，请查看:
1. 日志文件: `logs/github_backup.log`
2. 系统日志: `logs/dap.log`
3. GitHub 仓库 Issues

## 版本历史

- v1.0.0 (2025-01-20)
  - 初始版本
  - 支持自动定时备份
  - GitHub REST API 集成
  - 交互式配置向导
  - Windows 服务支持
