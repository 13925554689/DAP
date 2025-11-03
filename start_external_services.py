#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部服务启动脚本
启动所有配置的外部服务
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path
from config.external_services_config import EXTERNAL_SERVICES, SERVICE_PATHS, SERVICE_START_COMMANDS

def check_service_status(port):
    """检查指定端口的服务状态"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=3)
        return response.status_code == 200
    except:
        return False

def start_service(service_name, config):
    """启动单个服务"""
    print(f"🚀 启动 {config['name']}...")
    print(f"   端口: {config['port']}")
    print(f"   描述: {config['description']}")
    
    # 获取服务路径
    service_path = SERVICE_PATHS.get(service_name)
    if not service_path or not os.path.exists(service_path):
        print(f"❌ 服务路径不存在: {service_path}")
        return False
    
    # 获取启动命令
    start_command = SERVICE_START_COMMANDS.get(service_name)
    if not start_command:
        print(f"❌ 未配置启动命令: {service_name}")
        return False
    
    try:
        # 检查服务是否已经在运行
        if check_service_status(config['port']):
            print(f"  ⚠️  服务已在运行")
            return True
            
        # 设置环境变量指定端口
        env = os.environ.copy()
        env['SERVER_PORT'] = str(config['port'])
        
        # 切换到服务目录并启动
        process = subprocess.Popen(
            start_command,
            cwd=service_path,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )
        print(f"✅ {config['name']} 启动命令已执行 (PID: {process.pid})")
        return True
    except Exception as e:
        print(f"❌ 启动 {config['name']} 失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 70)
    print(" DAP 外部服务启动器")
    print("=" * 70)
    print()
    
    # 检查服务路径配置
    missing_paths = []
    for service_name in EXTERNAL_SERVICES:
        path = SERVICE_PATHS.get(service_name)
        if not path or not os.path.exists(path):
            missing_paths.append(f"{service_name} ({path})")
    
    if missing_paths:
        print("⚠️  警告: 以下服务路径未找到:")
        for path in missing_paths:
            print(f"   - {path}")
        print()
        print("💡 提示: 请确保以下目录存在并包含相应的服务代码:")
        for service_name, path in SERVICE_PATHS.items():
            print(f"   - {service_name}: {path}")
        print()
    
    # 启动所有启用的服务
    started_count = 0
    total_count = 0
    
    for service_name, config in EXTERNAL_SERVICES.items():
        if not config.get("enabled", True):
            print(f"⏭️  跳过未启用的服务: {config['name']}")
            continue
            
        total_count += 1
        if start_service(service_name, config):
            started_count += 1
        print()
    
    print("-" * 70)
    print(f"📊 启动结果: {started_count}/{total_count} 个服务已启动")
    print()
    print("💡 提示:")
    print("   - 服务将在后台运行")
    print("   - 使用 check_external_services.py 检查服务状态")
    print("   - 按 Ctrl+C 停止此脚本 (服务将继续运行)")
    print("=" * 70)
    
    # 等待几秒钟让服务启动
    print("\n⏳ 等待服务启动...")
    time.sleep(5)
    
    # 检查服务状态
    print("\n🏥 检查服务状态:")
    for service_name, config in EXTERNAL_SERVICES.items():
        if not config.get("enabled", True):
            continue
            
        is_healthy = check_service_status(config['port'])
        status_icon = "✅" if is_healthy else "❌"
        print(f"  {status_icon} {config['name']} (端口 {config['port']})")

if __name__ == "__main__":
    try:
        main()
        print("\n按 Enter 键退出...")
        input()
    except KeyboardInterrupt:
        print("\n\n👋 外部服务启动器已退出")
        sys.exit(0)