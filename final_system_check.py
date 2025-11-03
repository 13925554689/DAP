#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP系统最终检查脚本
验证所有核心功能是否正常运行
"""

import requests
import time
import json

def check_api_endpoint(url, method='GET', data=None, description=""):
    """检查API端点"""
    print(f"🔍 检查 {description}...")
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"  ❌ 不支持的HTTP方法: {method}")
            return False
            
        if response.status_code == 200:
            print(f"  ✅ {description} 正常 (状态码: {response.status_code})")
            return True
        else:
            print(f"  ⚠️  {description} 异常 (状态码: {response.status_code})")
            print(f"     响应: {response.text[:200]}...")
            return False
    except Exception as e:
        print(f"  ❌ {description} 失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("           DAP 系统最终功能检查")
    print("=" * 60)
    print()
    
    # 等待服务器启动
    print("⏳ 等待服务器启动...")
    time.sleep(3)
    
    base_url = "http://localhost:5001"
    
    # 1. 检查系统信息
    check_api_endpoint(
        f"{base_url}/api/system/info",
        "GET",
        None,
        "系统信息API"
    )
    
    # 2. 检查项目管理
    check_api_endpoint(
        f"{base_url}/api/projects",
        "GET",
        None,
        "项目列表API"
    )
    
    # 3. 检查自然语言查询
    check_api_endpoint(
        f"{base_url}/api/query/nl",
        "POST",
        {"query": "查询所有科目余额"},
        "自然语言查询API"
    )
    
    # 4. 检查外部服务状态
    check_api_endpoint(
        f"{base_url}/api/external/services/status",
        "GET",
        None,
        "外部服务状态API"
    )
    
    # 5. 检查报表功能
    check_api_endpoint(
        f"{base_url}/api/reports/account-balance",
        "POST",
        {"period": "2024-01"},
        "科目余额表API"
    )
    
    # 6. 检查审计底稿上传
    check_api_endpoint(
        f"{base_url}/api/audit/upload-standard-paper",
        "POST",
        {"paper_type": "standard", "period": "2024年度"},
        "审计底稿上传API"
    )
    
    print()
    print("=" * 60)
    print("           系统检查完成")
    print("=" * 60)
    print("✅ 如果所有检查都通过，说明系统核心功能正常运行")
    print("💡 请在浏览器中访问 http://localhost:5001 查看完整界面")
    print()

if __name__ == "__main__":
    main()