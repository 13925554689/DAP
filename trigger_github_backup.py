#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
立即触发 GitHub 备份脚本
"""

import os
import sys
from pathlib import Path
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from config.settings import get_config
from layer5.github_backup_manager import GitHubBackupManager

def main():
    """立即触发备份"""
    print("=" * 70)
    print(" DAP GitHub 自动备份 - 立即执行")
    print("=" * 70)
    print()
    
    # 加载配置
    config = get_config()
    backup_config = config.github_backup
    
    # 检查配置
    if not backup_config.enabled:
        print("❌ GitHub 备份未启用")
        print("   请在 .env 文件中设置 DAP_GITHUB_BACKUP_ENABLED=true")
        return False
    
    if not backup_config.repository:
        print("❌ 未配置 GitHub 仓库")
        print("   请在 .env 文件中设置 DAP_GITHUB_BACKUP_REPO")
        return False
    
    token = os.getenv(backup_config.token_env_var)
    if not token:
        print(f"❌ 未找到 GitHub Token")
        print(f"   请在 .env 文件中设置 {backup_config.token_env_var}")
        return False
    
    print(f"✅ 配置检查通过")
    print(f"   仓库: {backup_config.repository}")
    print(f"   分支: {backup_config.branch}")
    print(f"   备份路径: {backup_config.backup_paths}")
    print()
    
    # 创建备份管理器
    print("📦 初始化备份管理器...")
    try:
        manager = GitHubBackupManager(backup_config)
        print("✅ 备份管理器初始化成功")
        print()
    except Exception as e:
        print(f"❌ 备份管理器初始化失败: {e}")
        return False
    
    # 执行备份
    print("🚀 开始执行备份...")
    print("-" * 70)
    try:
        success = manager.run_backup(triggered_by="manual")
        print("-" * 70)
        print()
        
        if success:
            print("✅ 备份成功完成！")
            print(f"   仓库: {backup_config.repository}")
            print(f"   分支: {backup_config.branch}")
            print(f"   远程路径: {backup_config.remote_path}")
            print(f"   查看备份: https://github.com/{backup_config.repository}/tree/{backup_config.branch}/{backup_config.remote_path}")
            return True
        else:
            print("❌ 备份失败")
            print("   请查看日志获取详细信息")
            return False
            
    except Exception as e:
        print(f"❌ 备份执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print()
        print("=" * 70)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)