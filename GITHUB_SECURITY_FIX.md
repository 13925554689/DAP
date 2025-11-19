# GitHub安全问题修复指南

## 问题描述
GitHub的安全机制检测到代码库中包含敏感信息（Personal Access Token），导致无法推送代码。

## 解决方案

### 方案一：通过GitHub网站允许推送（推荐）

1. 访问以下URL（使用您收到的特定URL）：
   ```
   https://github.com/13925554689/DAP/security/secret-scanning/unblock-secret/34x7za0XDbttUF8xWm7iTxgeDyK
   ```

2. 登录您的GitHub账户

3. 点击 "Allow this secret to be pushed" 按钮

4. 然后重新运行推送命令：
   ```bash
   git push origin master
   ```

### 方案二：撤销并重新生成Token

1. 访问GitHub Token管理页面：
   ```
   https://github.com/settings/tokens
   ```

2. 找到并撤销泄露的Token

3. 生成新的Token并更新到您的.env文件中

### 方案三：清理历史提交中的敏感信息

如果您无法通过上述方法解决，可以考虑以下步骤：

1. 创建新的分支：
   ```bash
   git checkout --orphan clean-branch
   git add .
   git commit -m "Initial commit with cleaned files"
   git push origin clean-branch
   ```

2. 在GitHub上将此分支设置为默认分支

3. 删除包含敏感信息的旧分支

## 预防措施

1. 始终使用 `.env` 文件存储敏感信息
2. 确保 `.gitignore` 文件包含 `.env`
3. 定期更换Token
4. 使用 `.env.example` 作为模板文件

## 验证修复

修复后，运行以下命令验证备份功能：
```bash
python trigger_github_backup.py
```

如果成功，您将在GitHub仓库的 `backups` 目录中看到新的备份文件。