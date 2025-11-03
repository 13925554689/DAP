#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部服务集成使用示例
演示如何在DAP中调用5个外部智能体服务
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from layer3.external_services import ExternalServiceManager
from layer3.external_services.service_manager import ServiceConfig


def example_1_basic_query():
    """示例1: 基础查询"""
    print("\n" + "="*70)
    print(" 示例1: 基础查询 - 查询会计准则")
    print("="*70 + "\n")
    
    # 创建服务管理器
    manager = ExternalServiceManager({
        "asks": ServiceConfig(enabled=True, host="localhost", port=8001)
    })
    
    # 查询会计准则
    result = manager.query_accounting_standard("收入确认")
    print(f"查询结果: {result}")


def example_2_comprehensive_query():
    """示例2: 综合查询 - 跨多个服务查询"""
    print("\n" + "="*70)
    print(" 示例2: 综合查询 - 跨服务并行查询")
    print("="*70 + "\n")
    
    # 创建完整配置
    configs = {
        "asks": ServiceConfig(enabled=True, port=8001),
        "taxkb": ServiceConfig(enabled=True, port=8002),
        "regkb": ServiceConfig(enabled=True, port=8003)
    }
    
    manager = ExternalServiceManager(configs)
    
    # 并行查询
    query = "研发费用加计扣除"
    results = manager.comprehensive_query(query, parallel=True)
    
    print(f"查询关键词: {query}")
    print("\n查询结果:")
    for service, result in results.items():
        print(f"\n{service}:")
        print(f"  成功: {result.get('success')}")
        if result.get('success'):
            print(f"  数据: {result.get('data', [])[0] if result.get('data') else 'N/A'}")


def example_3_risk_assessment():
    """示例3: 风险评估 - 内控风险评估"""
    print("\n" + "="*70)
    print(" 示例3: 内控风险评估")
    print("="*70 + "\n")
    
    manager = ExternalServiceManager({
        "internal_control": ServiceConfig(enabled=True, port=8004)
    })
    
    # 评估风险
    result = manager.assess_internal_control_risk(
        business_scenario="大额现金支付业务",
        risk_factors=["缺少审批流程", "未定期盘点", "职责未分离"]
    )
    
    print(f"评估结果: {result}")


def example_4_ipo_assessment():
    """示例4: IPO准备度评估"""
    print("\n" + "="*70)
    print(" 示例4: IPO准备度评估")
    print("="*70 + "\n")
    
    manager = ExternalServiceManager({
        "ipo": ServiceConfig(enabled=True, port=8005)
    })
    
    # IPO评估
    company_info = {
        "name": "示例科技股份有限公司",
        "industry": "软件和信息技术服务业",
        "established_year": 2018
    }
    
    financial_data = {
        "revenue_2023": 50000000,
        "profit_2023": 8000000,
        "growth_rate": 0.35
    }
    
    result = manager.assess_ipo_readiness(company_info, financial_data)
    print(f"IPO准备度评估结果: {result}")


def example_5_integrated_analysis():
    """示例5: DAP集成分析 - 在审计过程中综合调用"""
    print("\n" + "="*70)
    print(" 示例5: DAP集成分析 - 审计场景综合应用")
    print("="*70 + "\n")
    
    # 完整服务配置
    configs = {
        "asks": ServiceConfig(enabled=True, port=8001),
        "taxkb": ServiceConfig(enabled=True, port=8002),
        "regkb": ServiceConfig(enabled=True, port=8003),
        "internal_control": ServiceConfig(enabled=True, port=8004),
        "ipo": ServiceConfig(enabled=True, port=8005)
    }
    
    manager = ExternalServiceManager(configs)
    
    # 模拟审计场景
    print("场景: 审计某上市公司的研发费用资本化处理\n")
    
    # 1. 查询会计准则
    print("1️⃣ 查询会计准则...")
    accounting_result = manager.query_accounting_standard("研发费用资本化")
    print(f"   准则查询: {'成功' if accounting_result.get('success') else '失败'}")
    
    # 2. 查询税务处理
    print("\n2️⃣ 查询税务处理...")
    tax_result = manager.query_tax_regulation("研发费用加计扣除")
    print(f"   税务查询: {'成功' if tax_result.get('success') else '失败'}")
    
    # 3. 检查监管要求
    print("\n3️⃣ 检查监管要求...")
    reg_result = manager.query_regulatory_rule("研发费用披露", source="csrc")
    print(f"   监管查询: {'成功' if reg_result.get('success') else '失败'}")
    
    # 4. 内控评估
    print("\n4️⃣ 内控风险评估...")
    ic_result = manager.assess_internal_control_risk(
        "研发项目立项和费用归集",
        ["项目界定不清", "支出分类不当"]
    )
    print(f"   内控评估: {'成功' if ic_result.get('success') else '失败'}")
    
    print("\n✅ 综合分析完成!")


def main():
    """主函数"""
    print("="*70)
    print(" DAP外部服务集成使用示例")
    print("="*70)
    
    print("\n请选择示例:")
    print("1. 基础查询 - 会计准则")
    print("2. 综合查询 - 跨服务并行")
    print("3. 风险评估 - 内控评估")
    print("4. IPO评估 - 准备度分析")
    print("5. 集成分析 - 完整审计场景")
    print("0. 运行所有示例")
    
    choice = input("\n请输入选项(0-5): ").strip()
    
    examples = {
        "1": example_1_basic_query,
        "2": example_2_comprehensive_query,
        "3": example_3_risk_assessment,
        "4": example_4_ipo_assessment,
        "5": example_5_integrated_analysis
    }
    
    if choice == "0":
        for func in examples.values():
            func()
    elif choice in examples:
        examples[choice]()
    else:
        print("无效选项!")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
