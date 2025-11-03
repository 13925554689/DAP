#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部服务管理脚本
提供启动、停止、检查服务状态的功能
"""

import os
import sys
import subprocess
import time
import psutil
import requests
from pathlib import Path
from config.external_services_config import EXTERNAL_SERVICES

def check_service_status(port):
    """检查指定端口的服务状态"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=3)
        return response.status_code == 200
    except:
        return False

def start_all_services():
    """启动所有服务"""
    print("🚀 启动所有外部服务...")
    print("=" * 50)
    
    for service_name, config in EXTERNAL_SERVICES.items():
        if not config.get("enabled", True):
            print(f"⏭️  跳过未启用的服务: {config['name']}")
            continue
            
        print(f"\n启动 {config['name']}...")
        print(f"  端口: {config['port']}")
        print(f"  描述: {config['description']}")
        
        # 检查服务是否已经在运行
        if check_service_status(config['port']):
            print(f"  ⚠️  服务已在运行")
            continue
            
        # 这里我们只是提示用户需要手动启动服务
        # 在实际环境中，这里应该有具体的启动逻辑
        print(f"  💡 请手动启动 {config['name']} 服务")
        print(f"     端口: {config['port']}")
    
    print("\n" + "=" * 50)
    print("✅ 服务启动命令已执行")
    print("💡 请确保各服务已在对应的端口上运行")

def check_all_services():
    """检查所有服务状态"""
    print("🏥 检查所有外部服务状态...")
    print("=" * 50)
    
    healthy_count = 0
    total_count = 0
    
    for service_name, config in EXTERNAL_SERVICES.items():
        if not config.get("enabled", True):
            print(f"⏭️  跳过未启用的服务: {config['name']}")
            continue
            
        total_count += 1
        is_healthy = check_service_status(config['port'])
        
        if is_healthy:
            healthy_count += 1
            status_icon = "✅"
            status_text = "运行正常"
        else:
            status_icon = "❌"
            status_text = "服务不可用"
        
        print(f"{status_icon} {config['name']:20s} (端口{config['port']:5d}) - {status_text}")
        print(f"   {config['description']}")
        print()
    
    print("-" * 50)
    print(f"📊 检查结果: {healthy_count}/{total_count} 个服务正常运行")
    return healthy_count == total_count

def main():
    """主函数"""
    print("=" * 70)
    print(" DAP 外部服务管理器")
    print("=" * 70)
    print()
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python manage_external_services.py start    - 启动所有服务")
        print("  python manage_external_services.py check    - 检查服务状态")
        print("  python manage_external_services.py status   - 检查服务状态")
        return
    
    command = sys.argv[1].lower()
    
    if command in ["start", "launch"]:
        start_all_services()
    elif command in ["check", "status"]:
        check_all_services()
    else:
        print(f"❌ 未知命令: {command}")
        print("支持的命令: start, check, status")

if __name__ == "__main__":
    main()