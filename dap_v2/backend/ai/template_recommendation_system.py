"""
DAP v2.0 - Template Recommendation System
智能模板推荐系统
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import Counter
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class TemplateRecommendationSystem:
    """模板推荐系统"""

    def __init__(self):
        # 证据类型关键词映射
        self.evidence_type_keywords = {
            'BANK_STATEMENT': ['银行', '对账单', 'bank', 'statement', '账户', '存款'],
            'INVOICE': ['发票', 'invoice', '增值税', 'VAT', '开票'],
            'CONTRACT': ['合同', 'contract', '协议', 'agreement', '签订'],
            'VOUCHER': ['凭证', 'voucher', '记账', 'accounting'],
            'RECEIPT': ['收据', 'receipt', '收款', 'payment'],
            'PAYSLIP': ['工资单', 'payslip', '薪资', 'salary', '工资'],
            'TAX_DOCUMENT': ['税务', 'tax', '纳税', '完税', '税单'],
            'FINANCIAL_STATEMENT': ['财务报表', 'financial statement', '资产负债', '利润表'],
            'ASSET_CERTIFICATE': ['资产证明', 'asset', '产权', 'property'],
            'OTHER': []
        }

        # 字段名称规范化映射
        self.field_normalization = {
            '银行名称': ['bank_name', 'bank', '银行', '开户行'],
            '账号': ['account', 'account_number', 'account_no', '账户', '账户号'],
            '金额': ['amount', 'money', 'sum', '金额', '总额', 'total'],
            '日期': ['date', 'time', '日期', '时间'],
            '发票号码': ['invoice_no', 'invoice_number', '发票号'],
            '发票代码': ['invoice_code', 'code', '代码'],
            '开票日期': ['invoice_date', 'issue_date', '开票日期'],
            '购买方': ['buyer', 'purchaser', '购方', '购买方'],
            '销售方': ['seller', 'vendor', '销方', '销售方']
        }

    def recommend_templates(
        self,
        evidence_data: Dict[str, Any],
        available_templates: List[Dict[str, Any]],
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        推荐适合的模板

        Args:
            evidence_data: 证据数据
            available_templates: 可用模板列表
            top_n: 返回前N个推荐

        Returns:
            推荐的模板列表(按匹配度排序)
        """
        recommendations = []

        for template in available_templates:
            # 跳过不活跃的模板
            if not template.get('is_active', True):
                continue

            # 计算匹配分数
            score, reasons = self._calculate_match_score(evidence_data, template)

            if score > 0:
                recommendations.append({
                    'template_id': template.get('id'),
                    'template_name': template.get('template_name'),
                    'evidence_type': template.get('evidence_type'),
                    'match_score': score,
                    'match_reasons': reasons,
                    'confidence': min(score / 100, 1.0)
                })

        # 按分数排序
        recommendations.sort(key=lambda x: x['match_score'], reverse=True)

        return recommendations[:top_n]

    def _calculate_match_score(
        self,
        evidence_data: Dict[str, Any],
        template: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """
        计算证据与模板的匹配分数

        Returns:
            (分数, 匹配原因列表)
        """
        score = 0.0
        reasons = []

        # 1. 证据类型关键词匹配 (权重: 40分)
        type_score = self._match_evidence_type(evidence_data, template)
        if type_score > 0:
            score += type_score
            reasons.append(f"证据类型匹配 (+{type_score:.0f}分)")

        # 2. 字段名称匹配 (权重: 35分)
        field_score, field_matches = self._match_fields(evidence_data, template)
        if field_score > 0:
            score += field_score
            reasons.append(f"字段匹配: {field_matches}个字段 (+{field_score:.0f}分)")

        # 3. 字段类型兼容性 (权重: 15分)
        type_compat_score = self._check_type_compatibility(evidence_data, template)
        if type_compat_score > 0:
            score += type_compat_score
            reasons.append(f"字段类型兼容 (+{type_compat_score:.0f}分)")

        # 4. 模板完整性 (权重: 10分)
        completeness_score = self._calculate_completeness(evidence_data, template)
        if completeness_score > 0:
            score += completeness_score
            reasons.append(f"数据完整性 (+{completeness_score:.0f}分)")

        return score, reasons

    def _match_evidence_type(
        self,
        evidence_data: Dict[str, Any],
        template: Dict[str, Any]
    ) -> float:
        """匹配证据类型"""
        # 获取证据文本内容
        text_content = self._extract_text_content(evidence_data)
        if not text_content:
            return 0.0

        text_lower = text_content.lower()

        # 获取模板证据类型
        evidence_type = template.get('evidence_type', '')
        if isinstance(evidence_type, str):
            type_key = evidence_type
        else:
            # 如果是枚举,获取值
            type_key = getattr(evidence_type, 'value', str(evidence_type))

        # 检查关键词
        keywords = self.evidence_type_keywords.get(type_key, [])
        matched_keywords = sum(1 for kw in keywords if kw in text_lower)

        if matched_keywords > 0:
            # 匹配的关键词越多,分数越高
            return min(40.0, matched_keywords * 15)

        return 0.0

    def _match_fields(
        self,
        evidence_data: Dict[str, Any],
        template: Dict[str, Any]
    ) -> Tuple[float, int]:
        """匹配字段名称"""
        template_fields = []

        # 收集模板所有字段
        for field in template.get('required_fields', []):
            template_fields.append(field.get('name'))
        for field in template.get('optional_fields', []):
            template_fields.append(field.get('name'))

        if not template_fields:
            return 0.0, 0

        # 计算匹配的字段数
        matched_count = 0
        for template_field in template_fields:
            if self._is_field_present(template_field, evidence_data):
                matched_count += 1

        # 匹配率
        match_rate = matched_count / len(template_fields)

        # 分数
        score = match_rate * 35.0

        return score, matched_count

    def _is_field_present(
        self,
        target_field: str,
        evidence_data: Dict[str, Any]
    ) -> bool:
        """检查字段是否存在(支持模糊匹配)"""
        # 直接匹配
        if target_field in evidence_data:
            return True

        # 规范化匹配
        if target_field in self.field_normalization:
            aliases = self.field_normalization[target_field]
            for alias in aliases:
                if alias in evidence_data:
                    return True

        # 部分匹配
        for key in evidence_data.keys():
            if target_field in key or key in target_field:
                return True

        return False

    def _check_type_compatibility(
        self,
        evidence_data: Dict[str, Any],
        template: Dict[str, Any]
    ) -> float:
        """检查字段类型兼容性"""
        compatible_count = 0
        total_checked = 0

        all_fields = template.get('required_fields', []) + template.get('optional_fields', [])

        for field_def in all_fields:
            field_name = field_def.get('name')
            expected_type = field_def.get('type', 'string')

            # 查找对应的数据字段
            field_value = None
            if field_name in evidence_data:
                field_value = evidence_data[field_name]
            else:
                # 尝试模糊匹配
                for key, value in evidence_data.items():
                    if field_name in key or key in field_name:
                        field_value = value
                        break

            if field_value is not None:
                total_checked += 1
                if self._is_type_compatible(field_value, expected_type):
                    compatible_count += 1

        if total_checked == 0:
            return 0.0

        compatibility_rate = compatible_count / total_checked
        return compatibility_rate * 15.0

    def _is_type_compatible(self, value: Any, expected_type: str) -> bool:
        """检查值与期望类型是否兼容"""
        if expected_type == 'string':
            return True  # 任何类型都可以转为字符串

        if expected_type in ['number', 'currency']:
            try:
                float(str(value).replace(',', '').replace('¥', '').replace('$', ''))
                return True
            except:
                return False

        if expected_type == 'integer':
            try:
                int(value)
                return True
            except:
                return False

        if expected_type == 'date':
            # 简单检查日期格式
            date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{2}/\d{2}/\d{4}']
            return any(re.match(p, str(value)) for p in date_patterns)

        if expected_type == 'boolean':
            return isinstance(value, bool) or str(value).lower() in ['true', 'false', 'yes', 'no']

        return True

    def _calculate_completeness(
        self,
        evidence_data: Dict[str, Any],
        template: Dict[str, Any]
    ) -> float:
        """计算数据完整性"""
        required_fields = template.get('required_fields', [])
        if not required_fields:
            return 10.0  # 没有必填字段,给满分

        # 计算有多少必填字段有数据
        filled_count = 0
        for field_def in required_fields:
            field_name = field_def.get('name')
            if self._is_field_present(field_name, evidence_data):
                value = evidence_data.get(field_name)
                if value is not None and value != '':
                    filled_count += 1

        completeness_rate = filled_count / len(required_fields)
        return completeness_rate * 10.0

    def _extract_text_content(self, evidence_data: Dict[str, Any]) -> str:
        """提取证据的文本内容"""
        text_parts = []

        # 常见的文本字段
        text_fields = [
            'content_text', 'ocr_text', 'text', 'content',
            'description', 'summary', 'evidence_name', 'title'
        ]

        for field in text_fields:
            if field in evidence_data and evidence_data[field]:
                text_parts.append(str(evidence_data[field]))

        # 如果没有文本字段,尝试从所有字段提取
        if not text_parts:
            for key, value in evidence_data.items():
                if isinstance(value, str) and len(value) > 5:
                    text_parts.append(value)

        return ' '.join(text_parts)

    def get_template_usage_stats(
        self,
        usage_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析模板使用统计

        Args:
            usage_history: 模板使用历史

        Returns:
            统计信息
        """
        stats = {
            'total_usage': len(usage_history),
            'most_used_templates': Counter(),
            'usage_by_type': Counter(),
            'avg_success_rate': 0.0
        }

        success_count = 0

        for record in usage_history:
            template_id = record.get('template_id')
            evidence_type = record.get('evidence_type')
            success = record.get('success', False)

            if template_id:
                stats['most_used_templates'][template_id] += 1

            if evidence_type:
                stats['usage_by_type'][evidence_type] += 1

            if success:
                success_count += 1

        if usage_history:
            stats['avg_success_rate'] = success_count / len(usage_history)

        # 转换为列表
        stats['most_used_templates'] = stats['most_used_templates'].most_common(5)
        stats['usage_by_type'] = dict(stats['usage_by_type'])

        return stats

    def suggest_template_improvements(
        self,
        template: Dict[str, Any],
        validation_failures: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        根据验证失败记录建议模板改进

        Args:
            template: 模板定义
            validation_failures: 验证失败记录

        Returns:
            改进建议列表
        """
        suggestions = []

        # 统计常见的验证失败
        failure_reasons = Counter()
        for failure in validation_failures:
            for error in failure.get('errors', []):
                failure_reasons[error] += 1

        # 分析并生成建议
        for reason, count in failure_reasons.most_common(3):
            if '缺少必填字段' in reason:
                field_name = reason.split(':')[-1].strip()
                suggestions.append({
                    'type': 'field_adjustment',
                    'suggestion': f"考虑将'{field_name}'改为可选字段",
                    'reason': f"该字段在{count}次验证中缺失"
                })

            elif '格式不符合要求' in reason:
                field_name = reason.split('格式')[0].strip()
                suggestions.append({
                    'type': 'validation_rule',
                    'suggestion': f"放宽'{field_name}'字段的验证规则",
                    'reason': f"该字段在{count}次验证中格式不匹配"
                })

            elif '值小于最小值' in reason or '值大于最大值' in reason:
                suggestions.append({
                    'type': 'range_adjustment',
                    'suggestion': "调整数值范围限制",
                    'reason': f"范围验证失败{count}次"
                })

        return suggestions


# 全局实例
_recommendation_system = None


def get_recommendation_system() -> TemplateRecommendationSystem:
    """获取推荐系统单例"""
    global _recommendation_system
    if _recommendation_system is None:
        _recommendation_system = TemplateRecommendationSystem()
    return _recommendation_system
