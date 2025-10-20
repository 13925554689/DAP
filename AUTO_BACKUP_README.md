# DAP 自动 Git + GitHub 双备份系统

## 系统概述

**实时监控 + 智能提交 + 自动推送 = 零担心备份方案**

本系统实现了文件修改的实时监控和自动备份，采用**双重保障策略**：
- **本地Git仓库**：完整的版本历史和回滚能力
- **GitHub远程仓库**：云端备份和团队协作

## 核心特性

### 1. 实时文件监控
- 使用 `watchdog` 库监控整个项目目录
- 自动捕获文件的创建、修改、删除和移动
- 智能过滤无关文件（缓存、日志、虚拟环境等）

### 2. 智能防抖机制
- **防抖时间**：30秒（可配置）
- 同一文件在防抖时间内的多次修改只触发一次提交
- 避免频繁提交造成的提交历史混乱

### 3. 自动Git提交
- 自动 `git add --all` 添加所有变化
- 生成结构化的提交信息，包含：
  - 时间戳
  - 变更统计（新增/修改/删除文件数）
  - 自动备份标识
- 使用 `GitPython` 库进行Git操作

### 4. 自动GitHub推送
- 每次提交后自动推送到GitHub
- Token认证，无需每次输入密码
- SSL验证可配置（已禁用以解决证书问题）

### 5. 智能忽略规则
自动忽略以下内容，不会提交到仓库：
- `.git/` - Git目录本身
- `__pycache__/`, `*.pyc` - Python缓存
- `*.log` - 日志文件
- `dap_env/`, `venv/` - 虚拟环境
- `data/github_backups/` - 避免递归备份
- `.gitignore` 中定义的所有文件

## 快速开始

### 启动自动备份服务

```bash
start_auto_backup.bat
```

### 服务启动后会看到：

```
============================================================
DAP 自动 Git + GitHub 双备份系统
============================================================

监控路径: D:\DAP
防抖时间: 30 秒
GitHub仓库: 13925554689/DAP
------------------------------------------------------------
✓ 文件监控已启动
✓ 自动备份服务运行中...

监控以下变化:
  - 文件创建/修改/删除
  - 自动Git提交（防抖30秒）
  - 自动推送到GitHub

按 Ctrl+C 停止服务
============================================================
```

### 工作流程示例

1. **您修改了** `main_engine.py`
   ```
   [检测到变化] main_engine.py
   [等待30秒防抖...]
   ```

2. **30秒后自动提交**
   ```
   添加 1 个文件到Git暂存区...
   ✓ Git提交成功: a1b2c3d4
   推送到GitHub...
   ✓ GitHub推送成功
   ```

3. **提交信息**
   ```
   自动备份: 2025-01-20 19:30:15

   变更统计:
   - 新增文件: 0
   - 修改文件: 1
   - 删除文件: 0

   🤖 由 DAP 自动备份系统生成
   ```

## 配置选项

### 环境变量

在 `.env` 文件中配置：

```env
# Git防抖时间（秒）
DAP_GIT_DEBOUNCE_SECONDS=30

# GitHub Token
DAP_GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# SSL验证（已禁用）
DAP_GITHUB_BACKUP_VERIFY_SSL=false
```

### 防抖时间建议

- **开发阶段**：30-60秒（默认）
- **生产环境**：60-120秒
- **频繁修改**：15-30秒

## 工作原理

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│  文件系统变化监控 (watchdog.Observer)                   │
│  - 监控: 创建/修改/删除/移动                             │
│  - 过滤: .gitignore + 智能规则                          │
└────────────────┬────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────┐
│  防抖处理器 (Debouncer)                                 │
│  - 收集变化文件                                          │
│  - 等待30秒防抖                                          │
│  - 批量处理                                              │
└────────────────┬────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────┐
│  Git提交器 (GitAutoBackup)                              │
│  - git add --all                                        │
│  - git commit -m "..."                                  │
│  - 统计变更                                              │
└────────────────┬────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────┐
│  GitHub推送器                                            │
│  - git push origin master                               │
│  - Token认证                                            │
│  - 错误重试                                              │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

- **文件监控**: `watchdog` 6.0.0
- **Git操作**: `GitPython` 3.1.45
- **环境管理**: `python-dotenv` 1.1.1
- **并发控制**: Python `threading`
- **日志记录**: Python `logging`

## 文件结构

```
DAP/
├── auto_git_backup.py          # 核心服务脚本
├── start_auto_backup.bat       # 启动脚本
├── .gitignore                  # Git忽略规则
├── .gitattributes              # Git属性配置
├── .env                        # 环境变量（包含Token）
└── logs/
    └── auto_git_backup.log     # 服务日志
```

## 日志查看

### 实时日志
服务运行时会在控制台显示实时日志

### 历史日志
```bash
type logs\auto_git_backup.log
```

### 日志示例
```
2025-01-20 19:30:15 - INFO - 文件变化: D:\DAP\main_engine.py
2025-01-20 19:30:45 - INFO - 添加 1 个文件到Git暂存区...
2025-01-20 19:30:46 - INFO - ✓ Git提交成功: a1b2c3d4
2025-01-20 19:30:47 - INFO - 推送到GitHub...
2025-01-20 19:30:50 - INFO - ✓ GitHub推送成功: fast-forward
2025-01-20 19:30:50 - INFO - 备份完成 | 提交: a1b2c3d4 | 新增:0 修改:1 删除:0
```

## 常见问题

### Q1: 如何停止自动备份服务？
**A**: 在运行窗口按 `Ctrl+C`

### Q2: 可以手动触发提交吗？
**A**: 可以，修改任何文件后等待30秒即可自动触发

### Q3: 提交信息可以自定义吗？
**A**: 当前是自动生成的标准格式，如需自定义可修改 `auto_git_backup.py` 中的 `commit_msg` 变量

### Q4: 能否排除某些文件？
**A**: 在 `.gitignore` 文件中添加规则，或修改 `auto_git_backup.py` 中的 `ignore_patterns`

### Q5: 防抖时间太长/太短？
**A**: 修改 `.env` 中的 `DAP_GIT_DEBOUNCE_SECONDS` 值

### Q6: GitHub推送失败怎么办？
**A**: 检查：
1. 网络连接
2. Token是否有效
3. 查看日志详细错误信息

### Q7: SSL证书错误？
**A**: 已在代码中禁用SSL验证（`GIT_SSL_NO_VERIFY=1`），如需启用需安装正确的证书

### Q8: 如何查看提交历史？
**A**:
```bash
git log --oneline
# 或访问GitHub: https://github.com/13925554689/DAP/commits
```

### Q9: 能否设置开机自启？
**A**: 可以通过以下方式：
1. **计划任务**：创建Windows计划任务，登录时运行 `start_auto_backup.bat`
2. **启动文件夹**：将快捷方式放到 `shell:startup`
3. **服务**：使用 NSSM 转换为Windows服务

### Q10: 会占用很多资源吗？
**A**: 不会。watchdog使用操作系统的文件监控API，资源占用极低（<10MB内存）

## 高级功能

### 多分支支持

如需支持多分支，修改 `auto_git_backup.py`：

```python
# 获取当前分支
branch = self.repo.active_branch.name

# 推送到对应分支
origin.push(branch)
```

### 提交前Hook

在提交前运行测试或检查：

```python
# 在 _perform_backup 方法中添加
# 运行测试
try:
    subprocess.run(['pytest', 'tests/'], check=True)
except subprocess.CalledProcessError:
    logger.error("测试失败，跳过本次提交")
    return
```

### 远程通知

提交成功后发送通知：

```python
import requests

# 发送到企业微信/钉钉/Slack
def send_notification(commit_sha, stats):
    webhook_url = "YOUR_WEBHOOK_URL"
    message = f"新提交: {commit_sha}\n变更: {stats}"
    requests.post(webhook_url, json={"text": message})
```

## 与ZIP备份的区别

| 特性 | Git+GitHub | ZIP备份 (layer5) |
|-----|-----------|-----------------|
| **触发方式** | 实时自动 | 定时（2小时） |
| **备份内容** | 源代码 | 数据+配置+代码 |
| **版本控制** | ✅ 完整历史 | ❌ 单一版本 |
| **差异查看** | ✅ Git diff | ❌ 需解压对比 |
| **回滚能力** | ✅ 任意版本 | ❌ 仅最新 |
| **存储效率** | 高（增量） | 低（完整） |
| **协作功能** | ✅ Pull Request | ❌ 无 |
| **适用场景** | 代码版本管理 | 数据完整备份 |

**建议**：两种备份方式同时使用，互为补充！

## 性能优化

### 1. 排除大文件
在 `.gitignore` 中排除：
```
*.db
*.sqlite
*.log
*.zip
models/
vectors/
```

### 2. 增加防抖时间
减少提交频率：
```env
DAP_GIT_DEBOUNCE_SECONDS=60
```

### 3. 压缩提交历史
定期整理历史（谨慎使用）：
```bash
git gc --aggressive --prune=now
```

## 监控和维护

### 健康检查

```bash
# 检查服务状态
tasklist | findstr python

# 查看最近提交
git log -5 --oneline

# 检查远程同步
git status
```

### 定期维护

- **每周**: 查看日志，确认无错误
- **每月**: 清理旧日志文件
- **每季度**: 检查仓库大小，考虑是否需要清理历史

## 故障恢复

### 推送冲突

```bash
# 拉取远程更新
git pull origin master --rebase

# 手动推送
git push origin master
```

### 回滚错误提交

```bash
# 查看历史
git log --oneline

# 回滚到指定提交
git reset --hard <commit-sha>

# 强制推送（谨慎）
git push origin master --force
```

## 安全建议

1. **Token管理**
   - 定期更新Token
   - 不要分享或提交Token到代码
   - 使用最小权限原则

2. **敏感数据**
   - 确保 `.env` 在 `.gitignore` 中
   - 不要提交密码、密钥等敏感信息

3. **访问控制**
   - 使用私有仓库存储敏感项目
   - 配置分支保护规则

## 技术支持

- **日志文件**: `logs/auto_git_backup.log`
- **GitHub仓库**: https://github.com/13925554689/DAP
- **提交历史**: https://github.com/13925554689/DAP/commits/master

---

**自动备份，安心开发！** 🚀
