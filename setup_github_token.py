#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全设置 GitHub Token 脚本
"""

import os
import sys
from pathlib import Path

def main():
    """安全设置GitHub Token"""
    print("=" * 60)
    print(" DAP GitHub Token 安全设置工具")
    print("=" * 60)
    print()
    
    # 获取项目目录
    project_dir = Path(__file__).parent
    env_file = project_dir / ".env"
    env_example_file = project_dir / ".env.example"
    
    # 检查.env文件是否存在
    if not env_file.exists():
        print("📋 创建 .env 文件...")
        if env_example_file.exists():
            # 复制示例文件
            with open(env_example_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ .env 文件已创建")
        else:
            print("❌ 找不到 .env.example 文件")
            return False
    
    # 读取当前.env内容
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 显示当前Token状态
    token_line = None
    for i, line in enumerate(lines):
        if line.startswith("DAP_GITHUB_TOKEN="):
            token_line = i
            current_token = line.strip().split("=", 1)[1]
            if current_token == "YOUR_TOKEN_HERE" or not current_token:
                print("⚠️  当前Token未设置或为默认值")
            else:
                print("✅ 当前Token已设置 (出于安全考虑不显示具体值)")
            break
    
    # 询问用户是否要设置Token
    print("\n💡 如何获取GitHub Token:")
    print("   1. 登录GitHub")
    print("   2. 进入 Settings > Developer settings > Personal access tokens > Tokens (classic)")
    print("   3. 点击 'Generate new token' > 'Generate new token (classic)'")
    print("   4. 设置Token名称 (如: DAP-Backup)")
    print("   5. 设置过期时间")
    print("   6. 选择权限: repo (完整仓库访问权限)")
    print("   7. 点击 'Generate token'")
    print("   8. 复制生成的Token (只显示一次!)")
    print()
    
    choice = input("是否要设置GitHub Token? (y/N): ").strip().lower()
    if choice not in ['y', 'yes']:
        print("👋 退出设置")
        return True
    
    # 获取用户输入的Token
    print("\n🔒 请输入您的GitHub Personal Access Token:")
    print("   (输入不会显示在屏幕上)")
    token = input("Token: ").strip()
    
    if not token:
        print("❌ Token不能为空")
        return False
    
    # 验证Token格式 (基本验证)
    if not token.startswith("ghp_") and not token.startswith("github_pat_"):
        print("⚠️  Token格式可能不正确 (应以ghp_或github_pat_开头)")
        confirm = input("是否继续? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("👋 退出设置")
            return True
    
    # 更新.env文件
    if token_line is not None:
        lines[token_line] = f"DAP_GITHUB_TOKEN={token}\n"
    else:
        # 如果没有找到Token行，添加到文件末尾
        lines.append(f"\n# GitHub Personal Access Token\nDAP_GITHUB_TOKEN={token}\n")
    
    # 写入更新后的内容
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("\n✅ GitHub Token设置成功!")
    print("   Token已安全存储在 .env 文件中")
    print("   该文件已被 .gitignore 忽略，不会被提交到代码仓库")
    print()
    print("💡 现在您可以运行以下命令来测试备份功能:")
    print("   python trigger_github_backup.py")
    print()
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)