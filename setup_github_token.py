#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Token 设置脚本
帮助用户安全地设置 GitHub Token
"""

import os
import sys
from pathlib import Path

def setup_github_token():
    """设置 GitHub Token"""
    print("=" * 60)
    print(" GitHub Token 设置向导")
    print("=" * 60)
    print()
    
    # 检查 .env 文件是否存在
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ 未找到 .env 文件")
        print("💡 请确保在项目根目录运行此脚本")
        return False
    
    # 读取当前 .env 文件内容
    with open(env_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # 查找当前 Token 设置
    token_line_index = None
    for i, line in enumerate(lines):
        if line.startswith("DAP_GITHUB_TOKEN="):
            token_line_index = i
            break
    
    if token_line_index is None:
        print("❌ 未找到 DAP_GITHUB_TOKEN 配置项")
        return False
    
    current_line = lines[token_line_index].strip()
    if "YOUR_TOKEN_HERE" in current_line:
        print("💡 检测到尚未设置 GitHub Token")
    else:
        print("💡 检测到已设置 GitHub Token")
        # 提取当前 Token (如果有的话)
        current_token = current_line.split("=", 1)[1].split("#")[0].strip()
        if current_token and current_token != "YOUR_TOKEN_HERE":
            print(f"   当前 Token: {current_token[:6]}{'*' * (len(current_token) - 6) if len(current_token) > 6 else ''}")
    
    print()
    print("📘 如何获取 GitHub Token:")
    print("   1. 访问 https://github.com/settings/tokens")
    print("   2. 点击 'Generate new token' -> 'Fine-grained tokens'")
    print("   3. 设置 Token 名称: DAP Backup Token")
    print("   4. 设置过期时间: 根据需要设置")
    print("   5. 选择仓库权限: Contents (读写)")
    print("   6. 点击 'Generate token'")
    print("   7. 复制生成的 Token")
    print()
    
    # 获取用户输入
    print("📝 请输入您的 GitHub Token:")
    print("   (直接按回车跳过设置)")
    token = input(">>> ").strip()
    
    if not token:
        print("⏭️  跳过 Token 设置")
        return True
    
    # 验证 Token 格式 (简单验证)
    if len(token) < 10:
        print("❌ Token 格式可能不正确 (长度过短)")
        return False
    
    # 更新 .env 文件
    # 保留注释部分，只更新 Token 值
    token_line_parts = lines[token_line_index].split("#", 1)
    comment = f" # {token_line_parts[1].strip()}" if len(token_line_parts) > 1 else "  # GitHub 访问令牌"
    lines[token_line_index] = f"DAP_GITHUB_TOKEN={token}{comment}\n"
    
    # 写入更新后的内容
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    print()
    print("✅ GitHub Token 设置成功!")
    print(f"   Token: {token[:6]}{'*' * (len(token) - 6)}")
    print()
    print("💡 安全提示:")
    print("   - 请勿将 Token 分享给他人")
    print("   - 如怀疑 Token 泄露，请立即在 GitHub 上撤销")
    print("   - 本文件已添加到 .gitignore，不会被提交到仓库")
    return True

def main():
    """主函数"""
    try:
        success = setup_github_token()
        if success:
            print("\n" + "=" * 60)
            print("🎉 GitHub Token 设置完成!")
            print()
            print("💡 下一步建议:")
            print("   1. 运行 DAP_QUICKSTART.bat 测试备份功能")
            print("   2. 检查备份是否成功上传到 GitHub")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("❌ GitHub Token 设置失败")
            print("=" * 60)
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Token 设置已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 设置过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()