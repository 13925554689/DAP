#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
执行首次备份
"""

import os
import sys
from pathlib import Path

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 导入模块
sys.path.insert(0, str(Path(__file__).parent))
from layer5.github_backup_manager import GitHubBackupManager
from config.settings import get_config

print("="*60)
print("DAP GitHub 首次备份")
print("="*60)
print()

# 验证配置
config = get_config()
github_config = config.github_backup

print("配置信息:")
print(f"  - 备份启用: {github_config.enabled}")
print(f"  - 目标仓库: {github_config.repository}")
print(f"  - 分支: {github_config.branch}")
print(f"  - 备份路径: {len(github_config.backup_paths)} 个")
print(f"  - Token: {'已配置' if os.getenv(github_config.token_env_var) else '未配置'}")
print()

if not github_config.enabled:
    print("✗ GitHub备份未启用")
    sys.exit(1)

if not github_config.repository:
    print("✗ 仓库未配置")
    sys.exit(1)

token = os.getenv(github_config.token_env_var)
if not token:
    print("✗ Token未找到")
    sys.exit(1)

print("-"*60)
print("开始执行备份...")
print()

try:
    manager = GitHubBackupManager(github_config)
    success = manager.run_backup(triggered_by="manual-first")

    print()
    print("-"*60)

    if success:
        status = manager.get_status()
        print("✓ 备份成功！")
        print()
        print("详细信息:")
        details = status.get('details', {})
        print(f"  - 文件数量: {details.get('files', 'N/A')}")
        print(f"  - 远程路径: {details.get('remote_path', 'N/A')}")
        print(f"  - Commit SHA: {details.get('commit_sha', 'N/A')}")
        print(f"  - 触发方式: {details.get('trigger', 'N/A')}")
        print()
        print(f"查看备份: https://github.com/{github_config.repository}/tree/{github_config.branch}/{github_config.remote_path}")
    else:
        status = manager.get_status()
        print("✗ 备份失败")
        print(f"  原因: {status.get('message', '未知')}")
        sys.exit(1)

except Exception as e:
    print(f"✗ 备份异常: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("="*60)
print("备份完成！")
print("="*60)
