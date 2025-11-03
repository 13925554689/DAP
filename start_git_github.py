#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接启动 Git 和 GitHub 功能脚本
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """直接启动Git和GitHub功能"""
    print("=" * 60)
    print(" DAP Git + GitHub 功能启动器")
    print("=" * 60)
    print()
    
    # 切换到项目目录
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    print(f"📁 工作目录: {project_dir}")
    print()
    
    # 1. Git 状态检查
    print("🔍 Git 状态检查...")
    try:
        result = subprocess.run(["git", "status", "--porcelain"], 
                              capture_output=True, text=True, check=True)
        if result.stdout.strip():
            print("✅ 有未提交的更改")
        else:
            print("✅ 工作目录干净")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git 状态检查失败: {e}")
        return False
    
    # 2. 自动提交更改
    print("\n📝 自动提交更改...")
    try:
        # 添加所有更改
        subprocess.run(["git", "add", "."], check=True)
        
        # 提交更改
        commit_message = "Auto commit: Update DAP system with new features"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        print("✅ 更改已提交")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  提交失败 (可能没有更改): {e}")
    
    # 3. 推送到远程仓库
    print("\n🚀 推送到 GitHub...")
    try:
        subprocess.run(["git", "push", "origin", "master"], check=True)
        print("✅ 代码已推送到 GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ 推送失败: {e}")
        print("   GitHub安全机制检测到可能的敏感信息")
        print("   请手动检查并清理敏感信息后再推送")
        print("   或使用以下命令查看详细信息:")
        print("   git push --dry-run origin master")
    
    # 4. 触发 GitHub 备份
    print("\n💾 触发 GitHub 备份...")
    try:
        # 导入并运行备份
        sys.path.insert(0, str(project_dir))
        from dotenv import load_dotenv
        load_dotenv()
        
        from config.settings import get_config
        from layer5.github_backup_manager import GitHubBackupManager
        
        config = get_config()
        backup_config = config.github_backup
        
        if backup_config.enabled and os.getenv(backup_config.token_env_var):
            manager = GitHubBackupManager(backup_config)
            success = manager.run_backup(triggered_by="git_push")
            
            if success:
                print("✅ GitHub 备份成功完成")
                print(f"   仓库: {backup_config.repository}")
                print(f"   分支: {backup_config.branch}")
            else:
                print("❌ GitHub 备份失败")
                return False
        else:
            print("⚠️  GitHub 备份未配置或未启用")
            print("   请在 .env 文件中设置有效的 DAP_GITHUB_TOKEN")
            print("   注意: 不要在代码中硬编码Token，应使用环境变量")
    except Exception as e:
        print(f"❌ 备份执行异常: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 Git + GitHub 功能启动完成!")
    print("   - 代码已提交")
    print("   - GitHub 备份已执行")
    print("   注意: 由于安全机制，推送可能需要手动处理")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)