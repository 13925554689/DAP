"""
财务报表查看器测试脚本
快速测试新增的财务报表功能
"""

import os
import sys

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_report_generator():
    """测试财务报表生成器"""
    print("=" * 60)
    print("测试 1: 财务报表生成器基础功能")
    print("=" * 60)

    try:
        from layer2.financial_reports import FinancialReportsGenerator

        generator = FinancialReportsGenerator('data/dap_data.db', 'exports')
        print("✓ 财务报表生成器初始化成功")

        # 测试科目余额表
        print("\n测试科目余额表生成...")
        result = generator.generate_account_balance_report('2024年度', 'excel')

        if result.get('success'):
            print(f"✓ 科目余额表生成成功: {result.get('output_path')}")
            print(f"  - 记录数: {result.get('record_count')}")
            print(f"  - 文件大小: {result.get('file_size')} 字节")
        else:
            print(f"✗ 科目余额表生成失败: {result.get('error')}")

        # 测试资产负债表
        print("\n测试资产负债表生成...")
        result = generator.generate_balance_sheet_report('2024年度', 'excel')

        if result.get('success'):
            print(f"✓ 资产负债表生成成功: {result.get('output_path')}")
        else:
            print(f"✗ 资产负债表生成失败: {result.get('error')}")

        # 测试利润表
        print("\n测试利润表生成...")
        result = generator.generate_income_statement_report('2024年度', 'excel')

        if result.get('success'):
            print(f"✓ 利润表生成成功: {result.get('output_path')}")
        else:
            print(f"✗ 利润表生成失败: {result.get('error')}")

        # 测试现金流量表
        print("\n测试现金流量表生成...")
        result = generator.generate_cash_flow_report('2024年度', 'excel')

        if result.get('success'):
            print(f"✓ 现金流量表生成成功: {result.get('output_path')}")
        else:
            print(f"✗ 现金流量表生成失败: {result.get('error')}")

        generator.close()

        print("\n" + "=" * 60)
        print("测试完成!请检查 exports/ 目录下的生成文件")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gui_viewer():
    """测试GUI财务报表查看器"""
    print("\n" + "=" * 60)
    print("测试 2: GUI财务报表查看器")
    print("=" * 60)

    try:
        import tkinter as tk
        from gui_financial_viewer import FinancialReportViewer
        from layer1.storage_manager import StorageManager

        print("✓ 模块导入成功")

        # 检查数据库
        db_path = 'data/dap_data.db'
        if os.path.exists(db_path):
            print(f"✓ 数据库文件存在: {db_path}")
        else:
            print(f"⚠ 数据库文件不存在: {db_path}")
            print("  建议先导入数据后再测试GUI")

        # 创建测试窗口
        print("\n启动GUI测试窗口...")
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口

        storage_manager = StorageManager(db_path)

        # 创建报表查看器
        viewer = FinancialReportViewer(
            master=root,
            storage_manager=storage_manager,
            db_path=db_path
        )

        print("✓ 财务报表查看器窗口已打开")
        print("  - 窗口标题: 财务报表查看器")
        print("  - 默认报表: 科目余额表")
        print("  - 默认期间: 2024年度")
        print("\n请在GUI窗口中:")
        print("  1. 选择不同的报表类型")
        print("  2. 选择不同的会计期间")
        print("  3. 点击'刷新'按钮")
        print("  4. 点击'导出Excel'测试导出功能")
        print("  5. 关闭窗口完成测试")

        root.mainloop()

        print("\n✓ GUI测试完成")
        return True

    except ImportError as e:
        print(f"✗ 模块导入失败: {e}")
        print("  请确保 gui_financial_viewer.py 文件存在")
        return False
    except Exception as e:
        print(f"✗ GUI测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """测试与主界面的集成"""
    print("\n" + "=" * 60)
    print("测试 3: 主界面集成测试")
    print("=" * 60)

    try:
        from dap_launcher import DAPLauncher
        import tkinter as tk

        print("✓ 主界面模块导入成功")

        # 检查是否有 open_financial_viewer 方法
        if hasattr(DAPLauncher, 'open_financial_viewer'):
            print("✓ open_financial_viewer 方法存在")
        else:
            print("✗ open_financial_viewer 方法不存在")
            return False

        print("\n建议完整测试:")
        print("  1. 运行 start_gui.bat 启动主界面")
        print("  2. 切换到'数据管理'标签页")
        print("  3. 点击'📊 财务报表查看'按钮")
        print("  4. 验证报表查看器正常打开")

        return True

    except Exception as e:
        print(f"✗ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("DAP 财务报表查看器 - 测试套件")
    print("=" * 60)

    results = []

    # 测试1: 报表生成器
    print("\n[1/3] 测试财务报表生成器...")
    results.append(test_report_generator())

    # 测试2: GUI查看器
    print("\n[2/3] 测试GUI查看器...")
    user_choice = input("\n是否测试GUI界面? (y/n, 默认y): ").strip().lower()
    if user_choice != 'n':
        results.append(test_gui_viewer())
    else:
        print("跳过GUI测试")
        results.append(None)

    # 测试3: 集成测试
    print("\n[3/3] 集成测试...")
    results.append(test_integration())

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    test_names = ["财务报表生成器", "GUI查看器", "主界面集成"]
    for i, (name, result) in enumerate(zip(test_names, results), 1):
        if result is None:
            status = "跳过"
            symbol = "⊗"
        elif result:
            status = "通过"
            symbol = "✓"
        else:
            status = "失败"
            symbol = "✗"

        print(f"{i}. {symbol} {name}: {status}")

    print("\n" + "=" * 60)

    # 给出建议
    success_count = sum(1 for r in results if r is True)
    total_count = len([r for r in results if r is not None])

    if success_count == total_count and total_count > 0:
        print("✓ 所有测试通过!")
        print("\n下一步:")
        print("  1. 运行 start_gui.bat 启动完整界面")
        print("  2. 导入您的数据文件")
        print("  3. 使用'财务报表查看'功能")
    else:
        print(f"⚠ {total_count - success_count}/{total_count} 个测试失败")
        print("\n请检查:")
        print("  1. 是否已运行 pip install -r requirements.txt")
        print("  2. 数据库文件是否存在 (data/dap_data.db)")
        print("  3. 查看详细错误信息")

    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试已中断")
    except Exception as e:
        print(f"\n\n测试过程发生错误: {e}")
        import traceback
        traceback.print_exc()
