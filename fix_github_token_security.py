#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复GitHub Token安全问题
"""

import os
import sys
import re
from pathlib import Path

def clean_sensitive_files():
    """清理包含敏感信息的文件"""
    print("🔍 清理敏感信息...")
    
    # 1. 清理SECURITY_ALERT.md中的敏感信息
    security_alert_file = Path("SECURITY_ALERT.md")
    if security_alert_file.exists():
        with open(security_alert_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除具体的Token信息
        content = re.sub(r'ghp_[a-zA-Z0-9]+', 'ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', content)
        content = re.sub(r'[a-zA-Z0-9]{40}', 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', content)
        
        with open(security_alert_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ 已清理 SECURITY_ALERT.md")
    
    # 2. 清理CODE_REVIEW_COMPLETION.md中的敏感信息
    code_review_file = Path("CODE_REVIEW_COMPLETION.md")
    if code_review_file.exists():
        with open(code_review_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除具体的Token信息
        content = re.sub(r'ghp_[a-zA-Z0-9]+', 'ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', content)
        content = re.sub(r'[a-zA-Z0-9]{40}', 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', content)
        
        with open(code_review_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ 已清理 CODE_REVIEW_COMPLETION.md")
    
    # 3. 确保.env文件中的Token是占位符
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("DAP_GITHUB_TOKEN="):
                # 确保Token是占位符而不是实际值
                if "ghp_" in line and "YOUR_TOKEN_HERE" not in line and "REPLACE_ME" not in line:
                    lines[i] = "DAP_GITHUB_TOKEN=ghp_YOUR_ACTUAL_TOKEN_HERE_REPLACE_ME  # ⚠️ 请设置您的 GitHub Token（请勿提交到代码仓库）\n"
                    updated = True
        
        if updated:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print("✅ 已更新 .env 文件中的Token为占位符")
    
    print("✅ 敏感信息清理完成")

def create_secure_env_template():
    """创建安全的环境配置模板"""
    print("\n📝 创建安全的环境配置模板...")
    
    # 创建.env.example的安全版本
    env_example_content = """# DAP GitHub 自动备份配置示例
# 复制此文件为 .env 并填入您的配置信息
# ⚠️ 警告：.env 文件包含敏感信息，请勿提交到代码仓库！

# ================================
# GitHub 备份配置
# ================================
DAP_GITHUB_BACKUP_ENABLED=true
DAP_GITHUB_BACKUP_REPO=your-username/your-repo-name
DAP_GITHUB_BACKUP_BRANCH=master

# GitHub Personal Access Token
# 如何获取：GitHub Settings > Developer settings > Personal access tokens
# 所需权限：repo (完整仓库访问权限)
DAP_GITHUB_TOKEN=ghp_YOUR_ACTUAL_TOKEN_HERE_REPLACE_ME

# 备份设置
DAP_GITHUB_BACKUP_PATHS=data,exports,config,layer1,layer2,layer3,layer4,layer5,main_engine.py,dap_launcher.py,CLAUDE.md
DAP_GITHUB_BACKUP_REMOTE_PATH=backups
DAP_GITHUB_BACKUP_TEMP_DIR=data/github_backups
DAP_GITHUB_BACKUP_INTERVAL_MINUTES=120
DAP_GITHUB_BACKUP_COMMIT_MESSAGE=自动备份 DAP 项目: {timestamp} (包含 {files} 个文件, 触发方式: {trigger})
DAP_GITHUB_BACKUP_AUTHOR_NAME=DAP Backup Bot
DAP_GITHUB_BACKUP_AUTHOR_EMAIL=backup-bot@dap.com
DAP_GITHUB_BACKUP_RETENTION=5
DAP_GITHUB_BACKUP_VERIFY_SSL=true

# ================================
# 数据库配置
# ================================
DAP_DB_PATH=data/dap_data.db
DAP_DB_POOL_SIZE=10
DAP_DB_WAL_MODE=true
DAP_DB_CACHE_SIZE=10000
DAP_DB_TIMEOUT=30.0

# ================================
# 数据接入配置
# ================================
DAP_MAX_FILES_BATCH=100
DAP_PARALLEL_PROCESSING=true
DAP_MAX_WORKERS=4
DAP_CHUNK_SIZE=10000

# ================================
# 处理配置
# ================================
DAP_MEMORY_THRESHOLD=0.8
DAP_ENABLE_CACHING=true
DAP_CACHE_TTL=3600
DAP_TEMP_DIR=temp

# ================================
# 安全配置
# ================================
DAP_PATH_VALIDATION=true
DAP_MAX_FILE_SIZE=1073741824
DAP_SQL_PROTECTION=true

# ================================
# API 配置
# ================================
DAP_API_HOST=127.0.0.1
DAP_API_PORT=8000
DAP_API_DEBUG=false

# ================================
# 日志配置
# ================================
DAP_LOG_LEVEL=INFO
DAP_LOG_FILE=logs/dap.log
DAP_LOG_CONSOLE=true

# ================================
# 运行时配置
# ================================
DAP_PREFER_LIGHTWEIGHT=1
"""
    
    with open(".env.example", "w", encoding="utf-8") as f:
        f.write(env_example_content)
    
    print("✅ 已创建安全的 .env.example 模板")

def main():
    """主函数"""
    print("=" * 60)
    print(" DAP GitHub Token 安全修复工具")
    print("=" * 60)
    print()
    
    # 清理敏感信息
    clean_sensitive_files()
    
    # 创建安全模板
    create_secure_env_template()
    
    print()
    print("✅ GitHub Token 安全修复完成！")
    print()
    print("💡 下一步操作建议:")
    print("   1. 运行以下命令提交清理后的文件:")
    print("      git add .")
    print("      git commit -m \"Security: Clean sensitive information and update env template\"")
    print()
    print("   2. 然后可以安全地推送代码:")
    print("      git push origin master")
    print()
    print("   3. 配置有效的GitHub Token:")
    print("      python setup_github_token.py")
    print()
    print("   4. 测试备份功能:")
    print("      python trigger_github_backup.py")
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()