#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置GitHub Token的脚本
"""

import os
import sys
from pathlib import Path

def main():
    """设置GitHub Token"""
    print("设置GitHub Token")
    print("=" * 30)
    
    # 获取项目目录
    project_dir = Path(__file__).parent.absolute()
    env_file = project_dir / ".env"
    
    # 检查.env文件是否存在
    if not env_file.exists():
        print("❌ 找不到 .env 文件")
        return False
    
    # 读取当前.env内容
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找Token行
    token_line_index = None
    for i, line in enumerate(lines):
        if line.startswith("DAP_GITHUB_TOKEN="):
            token_line_index = i
            break
    
    if token_line_index is None:
        print("❌ 未找到Token配置行")
        return False
    
    # 获取当前Token
    current_line = lines[token_line_index]
    current_token = current_line.split('=', 1)[1].split('#')[0].strip()
    
    print(f"当前Token: {current_token}")
    
    # 如果Token已经是有效的（不是占位符），则不需要更改
    if current_token and 'YOUR_TOKEN' not in current_token and 'PLACEHOLDER' not in current_token:
        print("✅ Token已经是有效的")
        return True
    
    # 提示用户输入Token
    print("\n请输入您的GitHub Personal Access Token:")
    print("(输入后按回车，输入不会显示)")
    
    try:
        new_token = input().strip()
    except KeyboardInterrupt:
        print("\n操作已取消")
        return False
    
    if not new_token:
        print("❌ Token不能为空")
        return False
    
    # 更新Token
    lines[token_line_index] = f"DAP_GITHUB_TOKEN={new_token}  # GitHub Personal Access Token\n"
    
    # 写入文件
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("✅ Token已成功更新")
        return True
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)