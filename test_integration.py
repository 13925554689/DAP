#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP集成功能测试脚本
测试新增的所有功能
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from main_engine import get_dap_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_1_project_required_logic():
    """测试1: 项目强制逻辑"""
    print("\n" + "="*70)
    print(" 测试1: 项目强制逻辑")
    print("="*70)
    
    engine = get_dap_engine()
    
    # 测试1.1: 不提供项目应该失败
    print("\n1.1 测试不提供项目信息...")
    result = engine.process("test_data.xlsx", options={})
    
    if not result.get("success"):
        print(f"✅ 正确拦截: {result.get('error')}")
        print(f"   错误代码: {result.get('error_code')}")
    else:
        print("❌ 未能拦截缺少项目的请求")
    
    # 测试1.2: 提供项目名称应该成功创建
    print("\n1.2 测试提供项目名称...")
    result = engine.process("test_data.xlsx", options={
        "project_name": "测试项目2024",
        "project_code": "TEST2024",
        "skip_project_check": False  # 明确不跳过检查
    })
    
    if result.get("project"):
        print(f"✅ 项目创建成功: {result['project']}")
    else:
        print(f"⚠️ 项目信息: {result.get('project', 'N/A')}")
    
    # 测试1.3: 测试模式跳过检查
    print("\n1.3 测试跳过项目检查(测试模式)...")
    result = engine.process("test_data.xlsx", options={
        "skip_project_check": True  # 测试模式
    })
    
    print(f"   结果: {'成功' if result.get('success') else '失败'}")


def test_2_external_services():
    """测试2: 外部服务集成"""
    print("\n" + "="*70)
    print(" 测试2: 外部服务集成")
    print("="*70)
    
    from layer3.external_services import ExternalServiceManager
    from layer3.external_services.service_manager import ServiceConfig
    
    # 创建服务管理器
    print("\n2.1 初始化外部服务管理器...")
    configs = {
        "asks": ServiceConfig(enabled=True, port=8001),
        "taxkb": ServiceConfig(enabled=True, port=8002),
        "regkb": ServiceConfig(enabled=True, port=8003),
        "internal_control": ServiceConfig(enabled=True, port=8004),
        "ipo": ServiceConfig(enabled=True, port=8005)
    }
    
    manager = ExternalServiceManager(configs)
    print("✅ 服务管理器初始化成功")
    
    # 健康检查
    print("\n2.2 执行健康检查...")
    status = manager.health_check_all()
    
    for service, is_healthy in status.items():
        icon = "✅" if is_healthy else "❌"
        print(f"   {icon} {service}: {'健康' if is_healthy else '不可用'}")
    
    # 测试查询(如果服务可用)
    print("\n2.3 测试查询功能...")
    if any(status.values()):
        print("   至少有一个服务可用,测试查询...")
        
        # 测试会计准则查询
        if status.get("asks"):
            result = manager.query_accounting_standard("收入确认")
            print(f"   ASKS查询: {'成功' if result.get('success') else '失败'}")
        
        # 测试税务查询
        if status.get("taxkb"):
            result = manager.query_tax_regulation("增值税")
            print(f"   TAXKB查询: {'成功' if result.get('success') else '失败'}")
    else:
        print("   ⚠️ 所有外部服务不可用,跳过查询测试")


def test_3_enhanced_nl_query():
    """测试3: 增强的自然语言查询"""
    print("\n" + "="*70)
    print(" 测试3: 增强的自然语言查询引擎")
    print("="*70)
    
    from layer4.enhanced_nl_query_engine import EnhancedNLQueryEngine
    from layer3.external_services.service_manager import ServiceConfig
    
    # 初始化引擎
    print("\n3.1 初始化增强查询引擎...")
    engine = EnhancedNLQueryEngine(
        "data/dap_data.db",
        enable_external_services=True
    )
    print("✅ 引擎初始化成功")
    
    # 测试数据库查询
    print("\n3.2 测试数据库查询...")
    result = engine.process_query("查询所有凭证")
    print(f"   意图: {result.get('intent')}")
    print(f"   成功: {result.get('success')}")
    
    # 测试外部服务查询(如果启用)
    print("\n3.3 测试外部知识库查询...")
    queries = [
        ("查询收入确认准则", "查询准则"),
        ("查询研发费用税务处理", "查询税务"),
        ("查询证监会披露要求", "查询法规")
    ]
    
    for query, expected_intent in queries:
        result = engine.process_query(query)
        detected_intent = result.get('intent')
        print(f"   '{query}'")
        print(f"      意图: {detected_intent} (期望: {expected_intent})")
        print(f"      成功: {result.get('success')}")


def test_4_api_integration():
    """测试4: API集成"""
    print("\n" + "="*70)
    print(" 测试4: API集成测试")
    print("="*70)
    
    print("\n4.1 检查API路由集成...")
    try:
        from layer3.extended_api_server import external_router
        print(f"✅ 外部服务API路由加载成功")
        print(f"   路由前缀: {external_router.prefix}")
        print(f"   路由数量: {len(external_router.routes)}")
        
        # 列出所有路由
        print("\n4.2 可用的API端点:")
        for route in external_router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = ', '.join(route.methods) if route.methods else 'N/A'
                print(f"   {methods:8s} {route.path}")
    except Exception as e:
        print(f"❌ API路由加载失败: {e}")


def main():
    """主测试函数"""
    print("="*70)
    print(" DAP 集成功能测试套件")
    print("="*70)
    
    tests = [
        ("项目强制逻辑", test_1_project_required_logic),
        ("外部服务集成", test_2_external_services),
        ("增强NL查询", test_3_enhanced_nl_query),
        ("API集成", test_4_api_integration)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ 测试失败: {name}")
            print(f"   错误: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # 总结
    print("\n" + "="*70)
    print(" 测试总结")
    print("="*70)
    print(f"通过: {passed}/{len(tests)}")
    print(f"失败: {failed}/{len(tests)}")
    print("="*70)


if __name__ == "__main__":
    main()
