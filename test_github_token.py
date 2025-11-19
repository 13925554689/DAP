#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试GitHub Token是否有效
"""

import os
import requests
import urllib3
from dotenv import load_dotenv

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def main():
    """测试GitHub Token"""
    print("=" * 60)
    print(" GitHub Token 有效性测试")
    print("=" * 60)
    print()
    
    # 加载环境变量
    load_dotenv()
    
    # 获取Token
    token = os.getenv('DAP_GITHUB_TOKEN')
    if not token:
        print("❌ 未找到GitHub Token")
        return False
    
    if 'YOUR_TOKEN' in token or 'REPLACE_ME' in token:
        print("❌ Token仍然是占位符")
        print(f"   当前Token: {token}")
        return False
    
    print(f"✅ 找到Token (长度: {len(token)} 字符)")
    print(f"   格式正确: {token.startswith('ghp_')}")
    print()
    
    # 测试Token
    print("🔍 测试Token有效性...")
    headers = {
        'Authorization': f'token {token}',
        'User-Agent': 'DAP-Backup-Manager'
    }
    
    try:
        # 测试用户信息API
        response = requests.get(
            'https://api.github.com/user',
            headers=headers,
            verify=False  # 禁用SSL验证
        )
        
        if response.status_code == 200:
            user_data = response.json()
            print("✅ Token有效!")
            print(f"   用户名: {user_data.get('login')}")
            print(f"   ID: {user_data.get('id')}")
        elif response.status_code == 401:
            print("❌ Token无效 (401 Unauthorized)")
            print("   可能的原因:")
            print("   1. Token已过期")
            print("   2. Token权限不足")
            print("   3. Token已被撤销")
            print(f"   详细信息: {response.json()}")
            return False
        else:
            print(f"❌ API调用失败 (状态码: {response.status_code})")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False
    
    # 测试仓库访问权限
    print("\n🔍 测试仓库访问权限...")
    repo = os.getenv('DAP_GITHUB_BACKUP_REPO', '13925554689/DAP')
    try:
        response = requests.get(
            f'https://api.github.com/repos/{repo}',
            headers=headers,
            verify=False
        )
        
        if response.status_code == 200:
            repo_data = response.json()
            print("✅ 仓库访问权限正常!")
            print(f"   仓库名: {repo_data.get('full_name')}")
            print(f"   权限: {repo_data.get('permissions')}")
        elif response.status_code == 401:
            print("❌ 仓库访问权限不足 (401 Unauthorized)")
            return False
        elif response.status_code == 403:
            print("❌ 仓库访问被拒绝 (403 Forbidden)")
            return False
        elif response.status_code == 404:
            print("❌ 仓库不存在 (404 Not Found)")
            return False
        else:
            print(f"❌ 仓库API调用失败 (状态码: {response.status_code})")
            return False
            
    except Exception as e:
        print(f"❌ 仓库访问异常: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 Token测试完成!")
    print("   如果以上测试都通过，但备份仍然失败，")
    print("   请检查Token是否具有repo权限")
    print("=" * 60)
    return True

if __name__ == "__main__":
    main()