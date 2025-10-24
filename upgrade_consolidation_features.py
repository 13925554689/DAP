"""Upgrade script for consolidation features.

This script:
1. Upgrades the database schema with new consolidation tables
2. Provides instructions for GUI integration
3. Tests basic functionality
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.database_upgrade_consolidation import upgrade_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('consolidation_upgrade.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main upgrade function."""
    print("\n" + "="*70)
    print(" DAP系统 - 合并报表功能升级")
    print("="*70 + "\n")

    # Step 1: Database upgrade
    print("步骤 1/4: 数据库架构升级")
    print("-" * 70)

    db_path = "data/dap.db"

    if not Path(db_path).parent.exists():
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created data directory")

    print(f"目标数据库: {db_path}")
    print("开始升级...")

    try:
        success = upgrade_database(db_path)
        if success:
            print("✅ 数据库升级成功!\n")
        else:
            print("❌ 数据库升级失败! 请查看日志文件.\n")
            return False
    except Exception as e:
        print(f"❌ 数据库升级异常: {e}\n")
        logger.error(f"Database upgrade failed", exc_info=True)
        return False

    # Step 2: Test imports
    print("\n步骤 2/4: 测试核心模块导入")
    print("-" * 70)

    modules_to_test = [
        ("layer2.group_hierarchy_manager", "GroupHierarchyManager"),
        ("layer2.consolidation_engine", "ConsolidationEngine"),
        ("layer4.nl_query_engine", "NLQueryEngine"),
        ("gui_consolidation_tabs", "EnhancedProjectManagementTab"),
        ("gui_consolidation_tabs", "ConsolidationReportTab"),
        ("gui_consolidation_tabs", "NLQueryTab"),
    ]

    all_imports_ok = True

    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✅ {module_name}.{class_name}")
        except Exception as e:
            print(f"❌ {module_name}.{class_name} - 错误: {e}")
            all_imports_ok = False

    if not all_imports_ok:
        print("\n⚠️  部分模块导入失败,请检查依赖和代码\n")
        return False

    print("\n✅ 所有模块导入成功!\n")

    # Step 3: GUI Integration Instructions
    print("\n步骤 3/4: GUI集成说明")
    print("-" * 70)
    print("""
要在 dap_launcher.py 中集成新功能,请按以下步骤操作:

1. 在 dap_launcher.py 文件顶部添加导入:

   from gui_consolidation_tabs import (
       EnhancedProjectManagementTab,
       ConsolidationReportTab,
       NLQueryTab
   )

2. 在 create_main_area() 方法中,添加新标签页:

   def create_main_area(self, parent):
       # ... 现有代码 ...

       # 添加增强的项目管理标签页
       enhanced_pm_tab = EnhancedProjectManagementTab(notebook, self.dap_engine)

       # 添加合并报表标签页
       consolidation_tab = ConsolidationReportTab(notebook, self.dap_engine)

       # 添加自然语言查询标签页
       nl_query_tab = NLQueryTab(notebook, self.dap_engine)

3. 保存并重启 DAP 系统

或者运行快速集成脚本:
   python integrate_new_tabs.py
    """)

    # Step 4: Create quick integration script
    print("\n步骤 4/4: 创建快速集成脚本")
    print("-" * 70)

    integration_script = '''"""Quick integration script for new GUI tabs."""

import re
from pathlib import Path

def integrate_tabs():
    """Integrate new tabs into dap_launcher.py."""
    launcher_path = Path("dap_launcher.py")

    if not launcher_path.exists():
        print("❌ 找不到 dap_launcher.py")
        return False

    # Read current content
    content = launcher_path.read_text(encoding='utf-8')

    # Check if already integrated
    if "EnhancedProjectManagementTab" in content:
        print("⚠️  新标签页似乎已经集成")
        return True

    # Add import at top
    import_line = """from gui_consolidation_tabs import (
    EnhancedProjectManagementTab,
    ConsolidationReportTab,
    NLQueryTab
)
"""

    # Find import section and add
    import_pattern = r"(from main_engine import get_dap_engine)"
    content = re.sub(
        import_pattern,
        r"\\1\\n\\n" + import_line,
        content
    )

    # Add tabs in create_main_area
    # This is a simplified approach - may need manual adjustment
    tab_code = """
        # Enhanced consolidation features
        try:
            enhanced_pm_tab = EnhancedProjectManagementTab(notebook, self.dap_engine)
            consolidation_tab = ConsolidationReportTab(notebook, self.dap_engine)
            nl_query_tab = NLQueryTab(notebook, self.dap_engine)
        except Exception as e:
            import logging
            logging.error(f"Failed to create consolidation tabs: {e}")
"""

    # Find the create_ai_tab line and add after it
    ai_tab_pattern = r"(self\\.create_ai_tab\\(notebook\\))"
    content = re.sub(
        ai_tab_pattern,
        r"\\1" + tab_code,
        content
    )

    # Write back
    launcher_path.write_text(content, encoding='utf-8')

    print("✅ 新标签页已集成到 dap_launcher.py")
    print("   请检查文件并测试运行")
    return True

if __name__ == "__main__":
    print("\\n开始集成新标签页...")
    integrate_tabs()
'''

    script_path = Path("integrate_new_tabs.py")
    script_path.write_text(integration_script, encoding='utf-8')
    print(f"✅ 已创建集成脚本: {script_path}")

    # Final summary
    print("\n" + "="*70)
    print(" 升级完成!")
    print("="*70)
    print("""
✅ 数据库升级完成
✅ 核心模块测试通过
✅ GUI集成脚本已创建

下一步:
1. 运行 integrate_new_tabs.py 自动集成GUI标签页
2. 或者手动按照上述说明集成
3. 运行 start_gui.bat 启动系统
4. 测试新功能:
   - 项目与实体管理
   - 合并报表生成
   - 自然语言查询

享受新功能! 🎉
    """)

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Upgrade script failed", exc_info=True)
        print(f"\n❌ 升级失败: {e}")
        sys.exit(1)
