#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试GitHub备份功能
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from config.settings import get_config
from layer5.github_backup_manager import GitHubBackupManager

def main():
    """测试备份"""
    print("=" * 70)
    print(" DAP GitHub 备份测试")
    print("=" * 70)
    print()
    
    # 加载配置
    config = get_config()
    backup_config = config.github_backup
    
    # 检查配置
    print("配置检查:")
    print(f"  启用状态: {backup_config.enabled}")
    print(f"  仓库: {backup_config.repository}")
    print(f"  分支: {backup_config.branch}")
    
    token = os.getenv(backup_config.token_env_var)
    print(f"  Token设置: {'是' if token and token != 'YOUR_TOKEN_HERE' else '否'}")
    
    if not backup_config.enabled:
        print("❌ GitHub 备份未启用")
        return False
    
    if not backup_config.repository:
        print("❌ 未配置 GitHub 仓库")
        return False
    
    if not token or token == 'YOUR_TOKEN_HERE':
        print(f"❌ 未找到有效的 GitHub Token")
        print("   请在 .env 文件中设置有效的Token")
        return False
    
    print()
    print("✅ 配置检查通过")
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
    print("🚀 开始执行备份测试...")
    print("-" * 70)
    try:
        success = manager.run_backup(triggered_by="test")
        print("-" * 70)
        print()
        
        if success:
            status = manager.get_status()
            print("✅ 备份测试成功完成！")
            print(f"   仓库: {backup_config.repository}")
            print(f"   分支: {backup_config.branch}")
            print(f"   远程路径: {backup_config.remote_path}")
            print(f"   详细信息: {status}")
            return True
        else:
            status = manager.get_status()
            print("❌ 备份测试失败")
            print(f"   错误信息: {status}")
            return False
            
    except Exception as e:
        print(f"❌ 备份执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)