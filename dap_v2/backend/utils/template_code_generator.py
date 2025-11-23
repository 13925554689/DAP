"""
DAP v2.0 - Template Code Generator & Management Utilities
模板编号生成与管理工具
"""
from typing import Optional, Tuple
from datetime import datetime
import re


class TemplateCodeGenerator:
    """模板编号生成器"""

    # 来源代码映射
    SOURCE_CODES = {
        'SYSTEM': 'SYS',
        'DINGXINNUO': 'DXN',
        'ZHONGPU': 'ZP',
        'PWC': 'PWC',
        'DELOITTE': 'DTT',
        'EY': 'EY',
        'KPMG': 'KPMG',
        'RSM': 'RSM',
        'CUSTOM': 'CST'
    }

    # 模板类型代码
    TEMPLATE_TYPES = {
        'WORKPAPER': 'WP',
        'AUDIT_REPORT': 'AR',
        'MANAGEMENT_LETTER': 'ML',
        'TECHNICAL_COMMITTEE': 'TC'
    }

    # 底稿分类代码
    WORKPAPER_CATEGORIES = {
        'ASSET': 'A',                    # 资产类
        'SPECIAL_ASSET': 'B',            # 特殊资产
        'LIABILITY': 'L',                # 负债类
        'EQUITY': 'E',                   # 权益类
        'PL': 'PL',                      # 损益类
        'CASH_FLOW': 'CF',               # 现金流量
        'CONSOLIDATION': 'C',            # 合并类
        'MEMO': 'M',                     # 备忘录
        'TEST': 'T'                      # 测试类
    }

    # 报告分类代码
    REPORT_CATEGORIES = {
        'STANDARD': 'STD',               # 标准审计报告
        'MODIFIED': 'MOD',               # 保留意见
        'IPO': 'IPO',                    # IPO审计报告
        'TAX': 'TAX',                    # 税务审计报告
        'SPECIAL': 'SPC'                 # 专项审计报告
    }

    @staticmethod
    def generate_template_code(
        source_code: str,
        template_type: str,
        category: str,
        sequence: int,
        version_major: int = 1,
        version_minor: int = 0,
        version_year: Optional[int] = None
    ) -> str:
        """
        生成完整模板编号

        Args:
            source_code: 来源代码 (SYS/DXN/ZP...)
            template_type: 模板类型 (WP/AR/ML/TC)
            category: 分类代码 (A/B/L/PL/STD/IPO...)
            sequence: 序号
            version_major: 主版本号
            version_minor: 次版本号
            version_year: 年度版本(可选)

        Returns:
            str: 完整模板编号 如 SYS-WP-A-01-V1.0 或 DXN-AR-IPO-01-V2.0.2024
        """
        # 版本字符串
        if version_year:
            version_str = f"V{version_major}.{version_minor}.{version_year}"
        else:
            version_str = f"V{version_major}.{version_minor}"

        # 完整编号
        return f"{source_code}-{template_type}-{category}-{sequence:02d}-{version_str}"

    @staticmethod
    def generate_instance_code(
        project_code: str,
        template_type: str,
        category: str,
        sequence: int,
        parent_code: Optional[str] = None
    ) -> str:
        """
        生成底稿/报告实例编号

        Args:
            project_code: 项目编号
            template_type: 模板类型 (WP/AR)
            category: 分类代码
            sequence: 实例序号
            parent_code: 父底稿编号(用于子底稿)

        Returns:
            str: 实例编号 如 IPO-2024-001-WP-A-01
        """
        if parent_code:
            # 子底稿: 父编号-子序号
            return f"{parent_code}-{sequence:02d}"
        else:
            # 主底稿/报告
            return f"{project_code}-{template_type}-{category}-{sequence:02d}"

    @staticmethod
    def parse_template_code(template_code: str) -> dict:
        """
        解析模板编号

        Args:
            template_code: 模板编号 如 SYS-WP-A-01-V1.0

        Returns:
            dict: 解析结果
        """
        # 正则匹配: {来源}-{类型}-{分类}-{序号}-V{版本}
        pattern = r'^([A-Z]+)-([A-Z]+)-([A-Z]+)-(\d+)-V(\d+)\.(\d+)(?:\.(\d+))?$'
        match = re.match(pattern, template_code)

        if not match:
            raise ValueError(f"Invalid template code format: {template_code}")

        source, type_, category, seq, v_major, v_minor, v_year = match.groups()

        return {
            'source_code': source,
            'template_type': type_,
            'category': category,
            'sequence': int(seq),
            'version_major': int(v_major),
            'version_minor': int(v_minor),
            'version_year': int(v_year) if v_year else None,
            'version_string': match.group(5)  # 完整版本字符串
        }

    @staticmethod
    def increment_version(
        current_version: Tuple[int, int, Optional[int]],
        increment_type: str = 'minor'
    ) -> Tuple[int, int, Optional[int]]:
        """
        版本号递增

        Args:
            current_version: 当前版本 (major, minor, year)
            increment_type: 递增类型 major/minor/year

        Returns:
            tuple: 新版本号
        """
        major, minor, year = current_version

        if increment_type == 'major':
            return (major + 1, 0, None)
        elif increment_type == 'minor':
            return (major, minor + 1, year)
        elif increment_type == 'year':
            current_year = datetime.now().year
            return (major, minor, current_year)
        else:
            raise ValueError(f"Invalid increment_type: {increment_type}")


class TemplateValidator:
    """模板验证器"""

    @staticmethod
    def validate_edit_permissions(template_data: dict, user_role: str) -> dict:
        """
        验证编辑权限

        Args:
            template_data: 模板数据
            user_role: 用户角色

        Returns:
            dict: 权限检查结果
        """
        result = {
            'can_edit_content': False,
            'can_edit_structure': False,
            'can_delete': False,
            'can_copy': True,  # 所有用户都可以复制
            'can_create_version': False,
            'reason': None
        }

        # 系统锁定检查
        if template_data.get('is_system_locked'):
            result['reason'] = '系统内置模板已锁定,请复制后编辑'
            return result

        # 编辑权限检查
        if not template_data.get('is_editable'):
            result['reason'] = '该模板不允许编辑'
            return result

        # 根据角色分配权限
        if user_role in ['PARTNER', 'MANAGER']:
            result['can_edit_content'] = template_data.get('allow_content_edit', True)
            result['can_edit_structure'] = template_data.get('allow_structure_edit', False)
            result['can_delete'] = template_data.get('is_deletable', True)
            result['can_create_version'] = True
        elif user_role in ['SENIOR', 'STAFF']:
            result['can_edit_content'] = template_data.get('allow_content_edit', True)
            result['can_edit_structure'] = False
            result['can_delete'] = False
            result['can_create_version'] = False

        return result


class TemplateEditTracker:
    """模板编辑追踪器"""

    @staticmethod
    def create_edit_record(
        template_id: str,
        edit_type: str,
        field_changed: str,
        old_value: any,
        new_value: any,
        edited_by: str,
        edit_reason: str = None
    ) -> dict:
        """
        创建编辑记录

        Args:
            template_id: 模板ID
            edit_type: 编辑类型 (CREATE/UPDATE/DELETE/COPY)
            field_changed: 变更字段
            old_value: 旧值
            new_value: 新值
            edited_by: 编辑人ID
            edit_reason: 编辑原因

        Returns:
            dict: 编辑记录
        """
        return {
            'template_id': template_id,
            'edit_type': edit_type,
            'field_changed': field_changed,
            'old_value': str(old_value),
            'new_value': str(new_value),
            'edited_by': edited_by,
            'edit_reason': edit_reason,
            'edited_at': datetime.utcnow()
        }


# 示例使用
if __name__ == "__main__":
    gen = TemplateCodeGenerator()

    # 生成模板编号
    code1 = gen.generate_template_code("SYS", "WP", "A", 1, 1, 0)
    print(f"系统内置资产类底稿: {code1}")
    # 输出: SYS-WP-A-01-V1.0

    code2 = gen.generate_template_code("DXN", "AR", "IPO", 1, 2, 0, 2024)
    print(f"鼎信诺IPO报告2024版: {code2}")
    # 输出: DXN-AR-IPO-01-V2.0.2024

    # 生成实例编号
    instance1 = gen.generate_instance_code("IPO-2024-001", "WP", "A", 1)
    print(f"项目底稿实例: {instance1}")
    # 输出: IPO-2024-001-WP-A-01

    # 子底稿
    instance2 = gen.generate_instance_code("IPO-2024-001", "WP", "A", 1, instance1)
    print(f"子底稿: {instance2}")
    # 输出: IPO-2024-001-WP-A-01-01

    # 解析编号
    parsed = gen.parse_template_code(code1)
    print(f"解析结果: {parsed}")

    # 版本递增
    new_version = gen.increment_version((1, 0, None), 'minor')
    print(f"版本递增: V1.0 -> V{new_version[0]}.{new_version[1]}")
    # 输出: V1.0 -> V1.1
