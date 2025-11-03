#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置GitHub Token的交互式脚本
"""

import os
import sys
from pathlib import Path

def main():
    """配置GitHub Token"""
    print("=" * 60)
    print(" DAP GitHub Token 配置工具")
    print("=" * 60)
    print()
    
    # 获取项目目录
    project_dir = Path(__file__).parent.absolute()
    env_file = project_dir / ".env"
    
    # 检查.env文件是否存在
    if not env_file.exists():
        print("❌ 找不到 .env 文件")
        print("💡 请先运行 setup_github_token.py 创建配置文件")
        return False
    
    print("请按照以下步骤操作:")
    print()
    print("1. 登录到 GitHub")
    print("2. 访问: Settings > Developer settings > Personal access tokens > Tokens (classic)")
    print("3. 点击 'Generate new token' > 'Generate new token (classic)'")
    print("4. 填写以下信息:")
    print("   - Note: DAP-Backup-Token")
    print("   - Expiration: 90 days 或更长时间")
    print("   - 选择权限: 勾选 'repo' (完整仓库访问权限)")
    print("5. 点击 'Generate token'")
    print("6. 复制生成的Token (这一步很重要，Token只显示一次!)")
    print()
    
    # 读取当前.env内容
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查当前Token状态
    if "YOUR_TOKEN_HERE" in content or "YOUR_GITHUB_TOKEN_HERE" in content:
        print("⚠️  检测到默认Token占位符")
    elif "DAP_GITHUB_TOKEN=" in content:
        print("✅ 检测到已配置Token (出于安全考虑不显示具体值)")
    else:
        print("❌ 未找到Token配置项")
    
    print()
    choice = input("是否要配置GitHub Token? (y/N): ").strip().lower()
    if choice not in ['y', 'yes']:
        print("👋 退出配置")
        return True
    
    # 获取用户输入的Token
    print("\n🔒 请输入您的GitHub Personal Access Token:")
    print("   (输入不会显示在屏幕上，这是正常的安全措施)")
    token = input("Token: ").strip()
    
    if not token:
        print("❌ Token不能为空")
        return False
    
    # 验证Token格式
    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        print("⚠️  注意: Token格式可能不正确")
        print("   正常的GitHub Token应以 'ghp_' 或 'github_pat_' 开头")
        confirm = input("是否继续配置? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("👋 退出配置")
            return True
    
    # 更新.env文件中的Token
    lines = content.split('\n')
    token_updated = False
    
    for i, line in enumerate(lines):
        if line.startswith("DAP_GITHUB_TOKEN="):
            lines[i] = f"DAP_GITHUB_TOKEN={token}"
            token_updated = True
            break
    
    # 如果没有找到Token行，添加到适当位置
    if not token_updated:
        # 找到GitHub备份配置部分
        for i, line in enumerate(lines):
            if "GitHub 备份配置" in line or "GitHub Backup Configuration" in line:
                # 在配置部分后插入Token
                for j in range(i, len(lines)):
                    if j+1 < len(lines) and (lines[j+1].startswith("#") or lines[j+1].strip() == ""):
                        continue
                    else:
                        lines.insert(j+1, f"DAP_GITHUB_TOKEN={token}")
                        token_updated = True
                        break
                break
    
    # 如果还是没找到合适位置，添加到文件末尾
    if not token_updated:
        lines.append(f"\n# GitHub Personal Access Token\nDAP_GITHUB_TOKEN={token}\n")
    
    # 写入更新后的内容
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print("\n✅ GitHub Token配置成功!")
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