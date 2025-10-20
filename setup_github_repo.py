#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并创建 GitHub 仓库
"""

import os
import sys
from pathlib import Path

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DAP_GITHUB_TOKEN')
REPO_OWNER = '13925554689'
REPO_NAME = 'DAP'

print("="*60)
print("GitHub 仓库检查和创建")
print("="*60)
print()

if not TOKEN:
    print("✗ 未找到 GitHub Token")
    sys.exit(1)

print(f"Token: {TOKEN[:10]}...")
print(f"仓库: {REPO_OWNER}/{REPO_NAME}")
print()

# 检查仓库是否存在
print("-"*60)
print("检查仓库是否存在...")

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Accept': 'application/vnd.github+json'
}

try:
    response = requests.get(
        f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}',
        headers=headers,
        verify=False
    )

    if response.status_code == 200:
        print("✓ 仓库已存在")
        repo_data = response.json()
        print(f"  - 名称: {repo_data['full_name']}")
        print(f"  - 私有: {repo_data['private']}")
        print(f"  - URL: {repo_data['html_url']}")
        print()
        print("可以直接开始备份！")
        sys.exit(0)

    elif response.status_code == 404:
        print("⚠ 仓库不存在")
        print()

        # 询问是否创建
        create = input("是否创建仓库? (y/n) [y]: ").strip().lower()

        if create == 'n':
            print("操作已取消")
            sys.exit(1)

        print()
        print("-"*60)
        print("创建仓库...")

        # 创建仓库
        create_data = {
            'name': REPO_NAME,
            'description': 'DAP (Data Processing & Auditing Intelligence Agent) - 五层智能审计数据处理系统',
            'private': False,  # 可以改为 True 创建私有仓库
            'auto_init': True  # 自动初始化 README
        }

        create_response = requests.post(
            'https://api.github.com/user/repos',
            headers=headers,
            json=create_data,
            verify=False
        )

        if create_response.status_code == 201:
            repo_data = create_response.json()
            print("✓ 仓库创建成功!")
            print(f"  - URL: {repo_data['html_url']}")
            print(f"  - Clone URL: {repo_data['clone_url']}")
            print()
            print("可以开始备份了！")
            sys.exit(0)
        else:
            print(f"✗ 创建失败: {create_response.status_code}")
            print(create_response.text)
            sys.exit(1)

    else:
        print(f"✗ 检查失败: {response.status_code}")
        print(response.text)
        sys.exit(1)

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
