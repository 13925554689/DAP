#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新GitHub Token的简单脚本
"""

import os
import sys
from pathlib import Path

def main():
    """更新GitHub Token"""
    print("=" * 60)
    print(" GitHub Token 更新工具")
    print("=" * 60)
    print()
    
    # 获取项目目录
    project_dir = Path(__file__).parent.absolute()
    env_file = project_dir / ".env"
    
    # 检查.env文件是否存在
    if not env_file.exists():
        print("❌ 找不到 .env 文件")
        return False
    
    print("请按照以下步骤操作:")
    print()
    print("1. 登录到 GitHub")
    print("2. 访问: Settings > Developer settings > Personal access tokens > Tokens (classic)")
    print("3. 点击 'Generate new token' > 'Generate new token (classic)'")
    print("4. 填写以下信息:")
    print("   - Note: DAP-Backup-Token")
    print("   - Expiration: 90 days")
    print("   - 选择权限: 勾选 'repo' (完整仓库访问权限)")
    print("5. 点击 'Generate token'")
    print("6. 复制生成的Token (这一步很重要，Token只显示一次!)")
    print()
    
    # 读取当前.env内容
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 显示当前Token状态
    token_line_index = None
    for i, line in enumerate(lines):
        if line.startswith("DAP_GITHUB_TOKEN="):
            token_line_index = i
            current_token = line.strip().split("=", 1)[1].split("#")[0].strip()
            if "YOUR_TOKEN" in current_token or "REPLACE_ME" in current_token:
                print("⚠️  当前Token是占位符，需要替换")
            else:
                print("✅ 当前Token已设置 (出于安全考虑不显示具体值)")
            break
    
    if token_line_index is None:
        print("❌ 未找到Token配置行")
        return False
    
    print()
    choice = input("是否要更新GitHub Token? (y/N): ").strip().lower()
    if choice not in ['y', 'yes']:
        print("👋 退出配置")
        return True
    
    # 获取用户输入的Token
    print("\n🔒 请输入您的GitHub Personal Access Token:")
    print("   (输入不会显示在屏幕上)")
    try:
        token = input("Token: ").strip()
    except KeyboardInterrupt:
        print("\n\n👋 配置已取消")
        return True
    
    if not token:
        print("❌ Token不能为空")
        return False
    
    # 验证Token格式
    if not token.startswith("ghp_"):
        print("⚠️  注意: Token格式可能不正确")
        print("   正常的GitHub Token应以 'ghp_' 开头")
        confirm = input("是否继续配置? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("👋 退出配置")
            return True
    
    # 更新.env文件中的Token
    lines[token_line_index] = f"DAP_GITHUB_TOKEN={token}  # ⚠️ 请设置您的 GitHub Token（请勿提交到代码仓库）\n"
    
    # 写入更新后的内容
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("\n✅ GitHub Token更新成功!")
        print(f"   配置已保存到: {env_file}")
        print("   该文件已被 .gitignore 忽略，不会被提交到代码仓库")
        print()
        print("💡 现在您可以运行以下命令测试备份功能:")
        print("   python trigger_github_backup.py")
        print()
        return True
    except Exception as e:
        print(f"\n❌ 配置保存失败: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n👋 配置已取消")
        sys.exit(0)