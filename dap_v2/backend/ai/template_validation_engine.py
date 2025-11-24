"""
DAP v2.0 - Template Validation Engine
模板验证和应用引擎
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
from decimal import Decimal
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class TemplateValidationEngine:
    """模板验证引擎"""

    def __init__(self):
        # 字段类型验证器
        self.type_validators = {
            'string': self._validate_string,
            'number': self._validate_number,
            'integer': self._validate_integer,
            'date': self._validate_date,
            'datetime': self._validate_datetime,
            'boolean': self._validate_boolean,
            'email': self._validate_email,
            'phone': self._validate_phone,
            'url': self._validate_url,
            'currency': self._validate_currency
        }

    def validate_evidence(
        self,
        evidence_data: Dict[str, Any],
        template: Dict[str, Any],
        strict: bool = False
    ) -> Dict[str, Any]:
        """
        根据模板验证证据数据

        Args:
            evidence_data: 证据数据
            template: 模板定义
            strict: 严格模式(不允许额外字段)

        Returns:
            验证结果
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'missing_required': [],
            'missing_optional': [],
            'validation_details': {}
        }

        # 1. 验证必填字段
        required_fields = template.get('required_fields', [])
        for field_def in required_fields:
            field_name = field_def.get('name')
            field_result = self._validate_field(
                field_name,
                evidence_data.get(field_name),
                field_def,
                required=True
            )

            result['validation_details'][field_name] = field_result

            if not field_result['valid']:
                result['valid'] = False
                result['errors'].extend(field_result['errors'])
                if field_result.get('missing'):
                    result['missing_required'].append(field_name)

        # 2. 验证可选字段
        optional_fields = template.get('optional_fields', [])
        for field_def in optional_fields:
            field_name = field_def.get('name')
            field_value = evidence_data.get(field_name)

            if field_value is not None:
                field_result = self._validate_field(
                    field_name,
                    field_value,
                    field_def,
                    required=False
                )
                result['validation_details'][field_name] = field_result

                if not field_result['valid']:
                    result['warnings'].extend(field_result['errors'])
            else:
                result['missing_optional'].append(field_name)

        # 3. 检查额外字段(严格模式)
        if strict:
            all_template_fields = set(
                f.get('name') for f in required_fields + optional_fields
            )
            extra_fields = set(evidence_data.keys()) - all_template_fields

            if extra_fields:
                result['warnings'].append(f"包含额外字段: {', '.join(extra_fields)}")

        # 4. 自定义验证规则
        field_validations = template.get('field_validations', {})
        for field_name, rules in field_validations.items():
            if field_name in evidence_data:
                validation_result = self._apply_validation_rules(
                    field_name,
                    evidence_data[field_name],
                    rules
                )

                if not validation_result['valid']:
                    result['valid'] = False
                    result['errors'].extend(validation_result['errors'])

        return result

    def _validate_field(
        self,
        field_name: str,
        field_value: Any,
        field_def: Dict[str, Any],
        required: bool
    ) -> Dict[str, Any]:
        """验证单个字段"""
        result = {
            'valid': True,
            'errors': [],
            'missing': False
        }

        # 检查必填字段
        if required and (field_value is None or field_value == ''):
            result['valid'] = False
            result['missing'] = True
            result['errors'].append(f"缺少必填字段: {field_name}")
            return result

        # 如果字段为空且非必填,跳过验证
        if field_value is None or field_value == '':
            return result

        # 类型验证
        field_type = field_def.get('type', 'string')
        validator = self.type_validators.get(field_type)

        if validator:
            type_result = validator(field_value, field_def)
            if not type_result['valid']:
                result['valid'] = False
                result['errors'].extend(type_result['errors'])
        else:
            logger.warning(f"Unknown field type: {field_type}")

        return result

    def _apply_validation_rules(
        self,
        field_name: str,
        field_value: Any,
        rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """应用自定义验证规则"""
        result = {
            'valid': True,
            'errors': []
        }

        # 最小值
        if 'min' in rules:
            try:
                if float(field_value) < float(rules['min']):
                    result['valid'] = False
                    result['errors'].append(
                        f"{field_name}值({field_value})小于最小值{rules['min']}"
                    )
            except (ValueError, TypeError):
                pass

        # 最大值
        if 'max' in rules:
            try:
                if float(field_value) > float(rules['max']):
                    result['valid'] = False
                    result['errors'].append(
                        f"{field_name}值({field_value})大于最大值{rules['max']}"
                    )
            except (ValueError, TypeError):
                pass

        # 最小长度
        if 'min_length' in rules:
            if len(str(field_value)) < rules['min_length']:
                result['valid'] = False
                result['errors'].append(
                    f"{field_name}长度({len(str(field_value))})小于最小长度{rules['min_length']}"
                )

        # 最大长度
        if 'max_length' in rules:
            if len(str(field_value)) > rules['max_length']:
                result['valid'] = False
                result['errors'].append(
                    f"{field_name}长度({len(str(field_value))})大于最大长度{rules['max_length']}"
                )

        # 正则表达式
        if 'pattern' in rules:
            if not re.match(rules['pattern'], str(field_value)):
                result['valid'] = False
                result['errors'].append(
                    f"{field_name}格式不符合要求(pattern: {rules['pattern']})"
                )

        # 枚举值
        if 'enum' in rules:
            if field_value not in rules['enum']:
                result['valid'] = False
                result['errors'].append(
                    f"{field_name}值({field_value})不在允许的枚举值中: {rules['enum']}"
                )

        return result

    # 类型验证器
    def _validate_string(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证字符串"""
        result = {'valid': True, 'errors': []}

        if not isinstance(value, str):
            try:
                value = str(value)
            except:
                result['valid'] = False
                result['errors'].append("无法转换为字符串")
                return result

        return result

    def _validate_number(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证数字"""
        result = {'valid': True, 'errors': []}

        try:
            float(value)
        except (ValueError, TypeError):
            result['valid'] = False
            result['errors'].append("不是有效的数字")

        return result

    def _validate_integer(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证整数"""
        result = {'valid': True, 'errors': []}

        try:
            int(value)
        except (ValueError, TypeError):
            result['valid'] = False
            result['errors'].append("不是有效的整数")

        return result

    def _validate_date(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证日期"""
        result = {'valid': True, 'errors': []}

        if isinstance(value, date):
            return result

        if isinstance(value, str):
            # 尝试常见日期格式
            formats = ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y']
            for fmt in formats:
                try:
                    datetime.strptime(value, fmt)
                    return result
                except ValueError:
                    continue

        result['valid'] = False
        result['errors'].append("不是有效的日期格式")
        return result

    def _validate_datetime(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证日期时间"""
        result = {'valid': True, 'errors': []}

        if isinstance(value, datetime):
            return result

        if isinstance(value, str):
            # 尝试ISO格式
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return result
            except ValueError:
                pass

        result['valid'] = False
        result['errors'].append("不是有效的日期时间格式")
        return result

    def _validate_boolean(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证布尔值"""
        result = {'valid': True, 'errors': []}

        if isinstance(value, bool):
            return result

        if isinstance(value, str):
            if value.lower() in ['true', 'false', '1', '0', 'yes', 'no']:
                return result

        result['valid'] = False
        result['errors'].append("不是有效的布尔值")
        return result

    def _validate_email(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证电子邮件"""
        result = {'valid': True, 'errors': []}

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, str(value)):
            result['valid'] = False
            result['errors'].append("不是有效的电子邮件地址")

        return result

    def _validate_phone(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证电话号码"""
        result = {'valid': True, 'errors': []}

        # 中国手机号
        phone_pattern = r'^1[3-9]\d{9}$'
        if not re.match(phone_pattern, str(value).replace('-', '').replace(' ', '')):
            result['valid'] = False
            result['errors'].append("不是有效的电话号码")

        return result

    def _validate_url(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证URL"""
        result = {'valid': True, 'errors': []}

        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, str(value)):
            result['valid'] = False
            result['errors'].append("不是有效的URL")

        return result

    def _validate_currency(self, value: Any, field_def: Dict) -> Dict[str, Any]:
        """验证货币金额"""
        result = {'valid': True, 'errors': []}

        try:
            # 移除货币符号和逗号
            clean_value = str(value).replace('¥', '').replace('$', '').replace(',', '')
            float(clean_value)

            # 检查小数位数
            if '.' in clean_value:
                decimal_places = len(clean_value.split('.')[1])
                if decimal_places > 2:
                    result['valid'] = False
                    result['errors'].append("货币金额最多保留2位小数")

        except (ValueError, TypeError):
            result['valid'] = False
            result['errors'].append("不是有效的货币金额")

        return result

    def auto_fill_template(
        self,
        evidence_data: Dict[str, Any],
        template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据证据数据自动填充模板

        Args:
            evidence_data: 原始证据数据
            template: 模板定义

        Returns:
            填充后的数据
        """
        filled_data = {}
        suggestions = []

        # 所有字段(必填+可选)
        all_fields = template.get('required_fields', []) + template.get('optional_fields', [])

        for field_def in all_fields:
            field_name = field_def.get('name')

            # 直接匹配
            if field_name in evidence_data:
                filled_data[field_name] = evidence_data[field_name]
                continue

            # 模糊匹配
            matched_value = self._fuzzy_match_field(field_name, evidence_data)
            if matched_value is not None:
                filled_data[field_name] = matched_value
                suggestions.append({
                    'field': field_name,
                    'value': matched_value,
                    'confidence': 0.8,
                    'method': 'fuzzy_match'
                })

        return {
            'filled_data': filled_data,
            'suggestions': suggestions,
            'completion_rate': len(filled_data) / len(all_fields) if all_fields else 0
        }

    def _fuzzy_match_field(
        self,
        target_field: str,
        source_data: Dict[str, Any]
    ) -> Optional[Any]:
        """模糊匹配字段"""
        # 简单的模糊匹配规则
        field_aliases = {
            '银行名称': ['bank_name', 'bank', '银行'],
            '账号': ['account', 'account_number', '账户号'],
            '金额': ['amount', 'money', '金额', 'total'],
            '日期': ['date', '日期', 'time'],
            '发票号码': ['invoice_no', 'invoice_number', '发票号'],
            '发票代码': ['invoice_code', '代码']
        }

        # 检查别名
        if target_field in field_aliases:
            for alias in field_aliases[target_field]:
                if alias in source_data:
                    return source_data[alias]

        # 部分匹配
        for key in source_data.keys():
            if target_field in key or key in target_field:
                return source_data[key]

        return None


# 全局实例
_validation_engine = None


def get_validation_engine() -> TemplateValidationEngine:
    """获取验证引擎单例"""
    global _validation_engine
    if _validation_engine is None:
        _validation_engine = TemplateValidationEngine()
    return _validation_engine
