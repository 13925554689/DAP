#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部服务健康检查工具
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from layer3.external_services import ExternalServiceManager
from config.external_services_config import EXTERNAL_SERVICES


def main():
    """健康检查主函数"""
    print("=" * 70)
    print(" DAP外部服务健康检查")
    print("=" * 70)
    print()
    
    # 创建服务管理器
    print("🔧 初始化服务管理器...")
    from layer3.external_services.service_manager import ServiceConfig
    
    configs = {}
    for name, config in EXTERNAL_SERVICES.items():
        configs[name] = ServiceConfig(
            enabled=config["enabled"],
            host=config["host"],
            port=config["port"]
        )
    
    manager = ExternalServiceManager(configs)
    print()
    
    # 执行健康检查
    print("🏥 执行健康检查...")
    print("-" * 70)
    status = manager.health_check_all()
    print("-" * 70)
    print()
    
    # 显示结果
    print("📊 检查结果:")
    print()
    
    healthy_count = 0
    total_count = 0
    
    for service_name, service_info in EXTERNAL_SERVICES.items():
        total_count += 1
        is_healthy = status.get(service_name, False)
        
        if is_healthy:
            healthy_count += 1
            status_icon = "✅"
            status_text = "运行正常"
        else:
            status_icon = "❌"
            status_text = "服务不可用"
        
        print(f"{status_icon} {service_info['name']:20s} (端口{service_info['port']:5d}) - {status_text}")
        print(f"   {service_info['description']}")
        print()
    
    print("-" * 70)
    print(f"总计: {healthy_count}/{total_count} 个服务正常运行")
    print("=" * 70)
    
    # 返回状态
    return healthy_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
