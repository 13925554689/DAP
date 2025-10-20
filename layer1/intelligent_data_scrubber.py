#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intelligent Data Scrubber - 智能数据清洗器
基于AI和审计规则的智能数据清洗与标准化

核心功能：
1. 智能数据清洗
2. 审计专用规则
3. 数据标准化
4. 质量评估
5. 自动修复
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, date
import json

# 导入基础数据清洗器
try:
    from .data_scrubber import DataScrubber
except ImportError:
    from data_scrubber import DataScrubber

logger = logging.getLogger(__name__)

class AuditDataValidator:
    """审计数据验证器"""

    def __init__(self):
        # 审计专用验证规则
        self.audit_rules = {
            'debit_credit_balance': {
                'description': '借贷平衡规则',
                'rule': lambda df: abs(df['debit_amount'].sum() - df['credit_amount'].sum()) < 0.01,
                'severity': 'error'
            },
            'amount_reasonableness': {
                'description': '金额合理性检查',
                'rule': lambda series: (series >= 0).all() if series.dtype in ['float64', 'int64'] else True,
                'severity': 'warning'
            },
            'date_range_validation': {
                'description': '日期范围验证',
                'rule': lambda series: self._validate_date_range(series),
                'severity': 'warning'
            },
            'account_code_format': {
                'description': '科目编码格式验证',
                'rule': lambda series: series.str.match(r'^[0-9A-Z]{2,}$', na=False).all(),
                'severity': 'error'
            },
            'voucher_uniqueness': {
                'description': '凭证号唯一性检查',
                'rule': lambda series: series.nunique() == len(series.dropna()),
                'severity': 'error'
            }
        }

        # 数据质量阈值
        self.quality_thresholds = {
            'completeness_threshold': 0.9,  # 完整性阈值
            'accuracy_threshold': 0.95,     # 准确性阈值
            'consistency_threshold': 0.9,   # 一致性阈值
            'validity_threshold': 0.95      # 有效性阈值
        }

    def _validate_date_range(self, date_series: pd.Series) -> bool:
        """验证日期范围合理性"""
        try:
            date_series = pd.to_datetime(date_series, errors='coerce')
            min_date = datetime(1900, 1, 1)
            max_date = datetime.now()
            return ((date_series >= min_date) & (date_series <= max_date)).all()
        except:
            return False

    def validate_audit_rules(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """执行审计规则验证"""
        validation_results = {
            'passed_rules': [],
            'failed_rules': [],
            'warnings': [],
            'overall_score': 0.0
        }

        total_rules = 0
        passed_rules = 0

        for rule_name, rule_info in self.audit_rules.items():
            try:
                total_rules += 1

                # 根据规则类型选择验证方法
                if rule_name == 'debit_credit_balance':
                    result = self._validate_debit_credit_balance(data, schema_info)
                elif rule_name == 'amount_reasonableness':
                    result = self._validate_amount_columns(data, schema_info)
                elif rule_name == 'date_range_validation':
                    result = self._validate_date_columns(data, schema_info)
                elif rule_name == 'account_code_format':
                    result = self._validate_account_code_columns(data, schema_info)
                elif rule_name == 'voucher_uniqueness':
                    result = self._validate_voucher_uniqueness(data, schema_info)
                else:
                    result = {'passed': True, 'message': 'Rule not implemented'}

                if result['passed']:
                    validation_results['passed_rules'].append(rule_name)
                    passed_rules += 1
                else:
                    validation_results['failed_rules'].append({
                        'rule': rule_name,
                        'severity': rule_info['severity'],
                        'message': result['message']
                    })

                    if rule_info['severity'] == 'warning':
                        validation_results['warnings'].append(result['message'])

            except Exception as e:
                logger.warning(f"Rule validation failed for {rule_name}: {e}")
                validation_results['warnings'].append(f"Rule {rule_name} validation failed: {e}")

        validation_results['overall_score'] = passed_rules / total_rules if total_rules > 0 else 0.0

        return validation_results

    def _validate_debit_credit_balance(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证借贷平衡"""
        debit_cols = self._find_columns_by_semantic_type(schema_info, 'debit_amount')
        credit_cols = self._find_columns_by_semantic_type(schema_info, 'credit_amount')

        if not debit_cols or not credit_cols:
            return {'passed': True, 'message': 'No debit/credit columns found'}

        try:
            total_debit = data[debit_cols].sum().sum()
            total_credit = data[credit_cols].sum().sum()
            difference = abs(total_debit - total_credit)

            if difference < 0.01:  # 允许0.01的误差
                return {'passed': True, 'message': 'Debit/Credit balance verified'}
            else:
                return {
                    'passed': False,
                    'message': f'Debit/Credit imbalance detected: {difference:.2f}'
                }

        except Exception as e:
            return {'passed': False, 'message': f'Balance validation error: {e}'}

    def _validate_amount_columns(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证金额列的合理性"""
        amount_cols = self._find_columns_by_semantic_type(schema_info, 'amount')
        amount_cols.extend(self._find_columns_by_semantic_type(schema_info, 'debit_amount'))
        amount_cols.extend(self._find_columns_by_semantic_type(schema_info, 'credit_amount'))

        if not amount_cols:
            return {'passed': True, 'message': 'No amount columns found'}

        issues = []
        for col in amount_cols:
            if col in data.columns:
                # 检查负值
                negative_count = (data[col] < 0).sum()
                if negative_count > 0:
                    issues.append(f'Column {col} has {negative_count} negative values')

                # 检查异常大值
                q99 = data[col].quantile(0.99)
                extreme_count = (data[col] > q99 * 10).sum()
                if extreme_count > 0:
                    issues.append(f'Column {col} has {extreme_count} extremely large values')

        if issues:
            return {'passed': False, 'message': '; '.join(issues)}
        else:
            return {'passed': True, 'message': 'Amount columns validation passed'}

    def _validate_date_columns(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证日期列"""
        date_cols = self._find_columns_by_semantic_type(schema_info, 'date')

        if not date_cols:
            return {'passed': True, 'message': 'No date columns found'}

        issues = []
        for col in date_cols:
            if col in data.columns:
                try:
                    date_series = pd.to_datetime(data[col], errors='coerce')
                    invalid_count = date_series.isnull().sum() - data[col].isnull().sum()

                    if invalid_count > 0:
                        issues.append(f'Column {col} has {invalid_count} invalid dates')

                    # 检查日期范围
                    min_date = datetime(1900, 1, 1)
                    max_date = datetime.now()
                    out_of_range = ((date_series < min_date) | (date_series > max_date)).sum()

                    if out_of_range > 0:
                        issues.append(f'Column {col} has {out_of_range} dates out of reasonable range')

                except Exception as e:
                    issues.append(f'Date validation error for {col}: {e}')

        if issues:
            return {'passed': False, 'message': '; '.join(issues)}
        else:
            return {'passed': True, 'message': 'Date columns validation passed'}

    def _validate_account_code_columns(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证科目编码列"""
        account_cols = self._find_columns_by_semantic_type(schema_info, 'account_code')

        if not account_cols:
            return {'passed': True, 'message': 'No account code columns found'}

        issues = []
        for col in account_cols:
            if col in data.columns:
                # 检查格式
                invalid_format = ~data[col].astype(str).str.match(r'^[0-9A-Z]{2,}$', na=False)
                invalid_count = invalid_format.sum()

                if invalid_count > 0:
                    issues.append(f'Column {col} has {invalid_count} invalid format codes')

        if issues:
            return {'passed': False, 'message': '; '.join(issues)}
        else:
            return {'passed': True, 'message': 'Account code validation passed'}

    def _validate_voucher_uniqueness(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证凭证号唯一性"""
        voucher_cols = self._find_columns_by_semantic_type(schema_info, 'voucher_no')

        if not voucher_cols:
            return {'passed': True, 'message': 'No voucher number columns found'}

        issues = []
        for col in voucher_cols:
            if col in data.columns:
                duplicate_count = data[col].duplicated().sum()
                if duplicate_count > 0:
                    issues.append(f'Column {col} has {duplicate_count} duplicate voucher numbers')

        if issues:
            return {'passed': False, 'message': '; '.join(issues)}
        else:
            return {'passed': True, 'message': 'Voucher uniqueness validation passed'}

    def _find_columns_by_semantic_type(self, schema_info: Dict[str, Any], semantic_type: str) -> List[str]:
        """根据语义类型查找列"""
        matching_columns = []

        if 'columns' in schema_info:
            for col_name, col_info in schema_info['columns'].items():
                if col_info.get('semantic_type') == semantic_type:
                    matching_columns.append(col_name)

        return matching_columns

class DataQualityAssessor:
    """数据质量评估器"""

    def __init__(self):
        self.quality_dimensions = {
            'completeness': self._assess_completeness,
            'accuracy': self._assess_accuracy,
            'consistency': self._assess_consistency,
            'validity': self._assess_validity,
            'uniqueness': self._assess_uniqueness
        }

    def assess_quality(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """全面评估数据质量"""
        assessment = {
            'overall_score': 0.0,
            'dimension_scores': {},
            'issues': [],
            'recommendations': []
        }

        dimension_scores = []

        for dimension, assess_func in self.quality_dimensions.items():
            try:
                score, issues = assess_func(data, schema_info)
                assessment['dimension_scores'][dimension] = score
                dimension_scores.append(score)

                if issues:
                    assessment['issues'].extend(issues)

            except Exception as e:
                logger.warning(f"Quality assessment failed for {dimension}: {e}")
                assessment['dimension_scores'][dimension] = 0.0
                dimension_scores.append(0.0)

        assessment['overall_score'] = np.mean(dimension_scores) if dimension_scores else 0.0

        # 生成改进建议
        assessment['recommendations'] = self._generate_quality_recommendations(assessment)

        return assessment

    def _assess_completeness(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估完整性"""
        if data.empty:
            return 0.0, ['Dataset is empty']

        total_cells = data.shape[0] * data.shape[1]
        missing_cells = data.isnull().sum().sum()
        completeness_score = 1 - (missing_cells / total_cells)

        issues = []
        if completeness_score < 0.9:
            missing_ratio = missing_cells / total_cells
            issues.append(f'High missing data ratio: {missing_ratio:.1%}')

        # 检查关键字段的完整性
        critical_columns = self._identify_critical_columns(schema_info)
        for col in critical_columns:
            if col in data.columns:
                col_missing_ratio = data[col].isnull().sum() / len(data)
                if col_missing_ratio > 0.05:  # 5%阈值
                    issues.append(f'Critical column {col} has {col_missing_ratio:.1%} missing values')

        return completeness_score, issues

    def _assess_accuracy(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估准确性"""
        accuracy_score = 1.0
        issues = []

        # 检查数据类型一致性
        for col_name, col_info in schema_info.get('columns', {}).items():
            if col_name in data.columns:
                expected_type = col_info.get('data_type', 'object')
                actual_type = str(data[col_name].dtype)

                if expected_type != actual_type:
                    type_mismatch_ratio = 0.1  # 简化计算
                    accuracy_score -= type_mismatch_ratio
                    issues.append(f'Column {col_name} type mismatch: expected {expected_type}, got {actual_type}')

        # 检查数值范围合理性
        for col in data.select_dtypes(include=[np.number]).columns:
            outlier_ratio = self._calculate_outlier_ratio(data[col])
            if outlier_ratio > 0.05:  # 5%异常值阈值
                accuracy_score -= outlier_ratio * 0.2
                issues.append(f'Column {col} has {outlier_ratio:.1%} outliers')

        return max(0.0, accuracy_score), issues

    def _assess_consistency(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估一致性"""
        consistency_score = 1.0
        issues = []

        # 检查格式一致性
        for col_name, col_info in schema_info.get('columns', {}).items():
            if col_name in data.columns:
                semantic_type = col_info.get('semantic_type')

                if semantic_type == 'date':
                    format_consistency = self._check_date_format_consistency(data[col_name])
                    if format_consistency < 0.9:
                        consistency_score -= (1 - format_consistency) * 0.3
                        issues.append(f'Column {col_name} has inconsistent date formats')

                elif semantic_type == 'account_code':
                    pattern_consistency = self._check_pattern_consistency(data[col_name], r'^[0-9A-Z]+$')
                    if pattern_consistency < 0.9:
                        consistency_score -= (1 - pattern_consistency) * 0.3
                        issues.append(f'Column {col_name} has inconsistent account code patterns')

        return max(0.0, consistency_score), issues

    def _assess_validity(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估有效性"""
        validity_score = 1.0
        issues = []

        # 检查业务规则有效性
        validator = AuditDataValidator()
        validation_result = validator.validate_audit_rules(data, schema_info)

        validity_score = validation_result['overall_score']
        issues.extend([rule['message'] for rule in validation_result['failed_rules']])

        return validity_score, issues

    def _assess_uniqueness(self, data: pd.DataFrame, schema_info: Dict[str, Any]) -> Tuple[float, List[str]]:
        """评估唯一性"""
        uniqueness_score = 1.0
        issues = []

        # 检查应该唯一的字段
        unique_columns = []
        for col_name, col_info in schema_info.get('columns', {}).items():
            if col_info.get('semantic_type') in ['voucher_no', 'account_code']:
                unique_columns.append(col_name)

        for col in unique_columns:
            if col in data.columns:
                duplicate_ratio = data[col].duplicated().sum() / len(data)
                if duplicate_ratio > 0:
                    uniqueness_score -= duplicate_ratio * 0.5
                    issues.append(f'Column {col} has {duplicate_ratio:.1%} duplicate values')

        return max(0.0, uniqueness_score), issues

    def _identify_critical_columns(self, schema_info: Dict[str, Any]) -> List[str]:
        """识别关键列"""
        critical_types = ['account_code', 'amount', 'debit_amount', 'credit_amount', 'voucher_no', 'date']
        critical_columns = []

        for col_name, col_info in schema_info.get('columns', {}).items():
            if col_info.get('semantic_type') in critical_types:
                critical_columns.append(col_name)

        return critical_columns

    def _calculate_outlier_ratio(self, series: pd.Series) -> float:
        """计算异常值比例"""
        try:
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            outliers = ((series < lower_bound) | (series > upper_bound)).sum()
            return outliers / len(series)

        except:
            return 0.0

    def _check_date_format_consistency(self, date_series: pd.Series) -> float:
        """检查日期格式一致性"""
        try:
            date_series = date_series.dropna().astype(str)
            if date_series.empty:
                return 1.0

            # 常见日期格式
            formats = [
                r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
                r'^\d{4}/\d{2}/\d{2}$',  # YYYY/MM/DD
                r'^\d{2}-\d{2}-\d{4}$',  # DD-MM-YYYY
                r'^\d{8}$'               # YYYYMMDD
            ]

            format_matches = {}
            for fmt in formats:
                matches = date_series.str.match(fmt, na=False).sum()
                format_matches[fmt] = matches

            max_matches = max(format_matches.values())
            return max_matches / len(date_series)

        except:
            return 0.0

    def _check_pattern_consistency(self, series: pd.Series, pattern: str) -> float:
        """检查模式一致性"""
        try:
            series = series.dropna().astype(str)
            if series.empty:
                return 1.0

            matches = series.str.match(pattern, na=False).sum()
            return matches / len(series)

        except:
            return 0.0

    def _generate_quality_recommendations(self, assessment: Dict[str, Any]) -> List[str]:
        """生成质量改进建议"""
        recommendations = []

        # 基于维度分数的建议
        for dimension, score in assessment['dimension_scores'].items():
            if score < 0.8:
                if dimension == 'completeness':
                    recommendations.append("Implement data collection improvements to reduce missing values")
                elif dimension == 'accuracy':
                    recommendations.append("Add data validation rules to improve accuracy")
                elif dimension == 'consistency':
                    recommendations.append("Standardize data formats and entry procedures")
                elif dimension == 'validity':
                    recommendations.append("Review and strengthen business rule validations")
                elif dimension == 'uniqueness':
                    recommendations.append("Implement unique constraints for key identifier fields")

        # 基于整体分数的建议
        if assessment['overall_score'] < 0.7:
            recommendations.append("Consider comprehensive data quality improvement initiative")

        return recommendations

class IntelligentDataScrubber:
    """智能数据清洗器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 审计数据验证器
        self.validator = AuditDataValidator()

        # 数据质量评估器
        self.quality_assessor = DataQualityAssessor()

        # 基础数据清洗器
        try:
            self.base_scrubber = DataScrubber()
        except:
            self.base_scrubber = None

        # 清洗配置
        self.cleaning_config = {
            'auto_fix_enabled': self.config.get('auto_fix', True),
            'validation_enabled': self.config.get('validation', True),
            'quality_threshold': self.config.get('quality_threshold', 0.8),
            'preserve_original': self.config.get('preserve_original', True)
        }

        self.logger.info("Intelligent Data Scrubber initialized")

    async def clean_with_intelligence(self, raw_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能数据清洗主入口

        Args:
            raw_data: 原始数据
            schema: 数据模式信息

        Returns:
            清洗后的数据和质量报告
        """
        self.logger.info("Starting intelligent data cleaning")

        try:
            result = {
                'cleaned_data': {},
                'quality_reports': {},
                'cleaning_actions': {},
                'overall_quality_score': 0.0,
                'recommendations': []
            }

            quality_scores = []

            # 处理每个表
            for table_name, table_data in raw_data.items():
                if isinstance(table_data, pd.DataFrame) and not table_data.empty:
                    table_schema = schema.get('tables', {}).get(table_name, {})

                    # 清洗单表
                    table_result = await self._clean_table_intelligent(table_name, table_data, table_schema)

                    result['cleaned_data'][table_name] = table_result['cleaned_data']
                    result['quality_reports'][table_name] = table_result['quality_report']
                    result['cleaning_actions'][table_name] = table_result['cleaning_actions']

                    quality_scores.append(table_result['quality_report']['overall_score'])

            # 计算整体质量分数
            result['overall_quality_score'] = np.mean(quality_scores) if quality_scores else 0.0

            # 生成整体建议
            result['recommendations'] = await self._generate_overall_recommendations(result)

            self.logger.info(f"Intelligent data cleaning completed. Overall quality score: {result['overall_quality_score']:.2f}")
            return result

        except Exception as e:
            self.logger.error(f"Intelligent data cleaning failed: {e}")
            raise

    async def _clean_table_intelligent(self, table_name: str, table_data: pd.DataFrame,
                                     table_schema: Dict[str, Any]) -> Dict[str, Any]:
        """智能清洗单个表"""
        self.logger.info(f"Cleaning table: {table_name}")

        result = {
            'cleaned_data': table_data.copy(),
            'quality_report': {},
            'cleaning_actions': []
        }

        original_data = table_data.copy()

        try:
            # 1. 数据质量评估（清洗前）
            pre_quality = self.quality_assessor.assess_quality(table_data, table_schema)
            self.logger.info(f"Pre-cleaning quality score for {table_name}: {pre_quality['overall_score']:.2f}")

            # 2. 基础清洗
            result['cleaned_data'] = await self._apply_basic_cleaning(result['cleaned_data'], table_schema)

            # 3. 智能类型转换
            result['cleaned_data'] = await self._apply_intelligent_type_conversion(result['cleaned_data'], table_schema)

            # 4. 审计专用清洗
            result['cleaned_data'] = await self._apply_audit_specific_cleaning(result['cleaned_data'], table_schema)

            # 5. 自动修复
            if self.cleaning_config['auto_fix_enabled']:
                result['cleaned_data'], fix_actions = await self._apply_auto_fixes(result['cleaned_data'], table_schema)
                result['cleaning_actions'].extend(fix_actions)

            # 6. 数据质量评估（清洗后）
            post_quality = self.quality_assessor.assess_quality(result['cleaned_data'], table_schema)
            self.logger.info(f"Post-cleaning quality score for {table_name}: {post_quality['overall_score']:.2f}")

            # 7. 验证审计规则
            if self.cleaning_config['validation_enabled']:
                validation_result = self.validator.validate_audit_rules(result['cleaned_data'], table_schema)
                post_quality['audit_validation'] = validation_result

            result['quality_report'] = {
                'pre_cleaning': pre_quality,
                'post_cleaning': post_quality,
                'improvement': post_quality['overall_score'] - pre_quality['overall_score'],
                'overall_score': post_quality['overall_score']
            }

            # 记录清洗统计
            self._log_cleaning_statistics(table_name, original_data, result['cleaned_data'], result['cleaning_actions'])

        except Exception as e:
            self.logger.error(f"Table cleaning failed for {table_name}: {e}")
            result['cleaned_data'] = original_data
            result['quality_report'] = {'overall_score': 0.0, 'error': str(e)}

        return result

    async def _apply_basic_cleaning(self, data: pd.DataFrame, schema: Dict[str, Any]) -> pd.DataFrame:
        """应用基础清洗"""
        cleaned_data = data.copy()

        # 1. 移除完全空白的行和列
        cleaned_data = cleaned_data.dropna(how='all', axis=0)  # 移除全空行
        cleaned_data = cleaned_data.dropna(how='all', axis=1)  # 移除全空列

        # 2. 清理字符串字段
        for col in cleaned_data.select_dtypes(include=['object']).columns:
            # 去除前后空格
            cleaned_data[col] = cleaned_data[col].astype(str).str.strip()

            # 替换空字符串为NaN
            cleaned_data[col] = cleaned_data[col].replace('', np.nan)

            # 统一空值表示
            cleaned_data[col] = cleaned_data[col].replace(['NULL', 'null', 'None', 'none', 'N/A', 'n/a'], np.nan)

        # 3. 处理重复行
        duplicate_count = cleaned_data.duplicated().sum()
        if duplicate_count > 0:
            cleaned_data = cleaned_data.drop_duplicates()
            self.logger.info(f"Removed {duplicate_count} duplicate rows")

        return cleaned_data

    async def _apply_intelligent_type_conversion(self, data: pd.DataFrame, schema: Dict[str, Any]) -> pd.DataFrame:
        """应用智能类型转换"""
        converted_data = data.copy()

        for col_name, col_info in schema.get('columns', {}).items():
            if col_name not in converted_data.columns:
                continue

            semantic_type = col_info.get('semantic_type', 'unknown')
            current_dtype = str(converted_data[col_name].dtype)

            try:
                if semantic_type == 'date' and current_dtype == 'object':
                    # 转换日期
                    converted_data[col_name] = pd.to_datetime(converted_data[col_name], errors='coerce')

                elif semantic_type in ['amount', 'debit_amount', 'credit_amount'] and current_dtype == 'object':
                    # 转换金额
                    # 移除货币符号和千位分隔符
                    cleaned_amounts = converted_data[col_name].astype(str).str.replace(r'[￥$,]', '', regex=True)
                    converted_data[col_name] = pd.to_numeric(cleaned_amounts, errors='coerce')

                elif semantic_type == 'account_code' and current_dtype != 'object':
                    # 确保科目编码为字符串
                    converted_data[col_name] = converted_data[col_name].astype(str)

            except Exception as e:
                self.logger.warning(f"Type conversion failed for column {col_name}: {e}")

        return converted_data

    async def _apply_audit_specific_cleaning(self, data: pd.DataFrame, schema: Dict[str, Any]) -> pd.DataFrame:
        """应用审计专用清洗规则"""
        cleaned_data = data.copy()

        # 1. 标准化科目编码
        account_code_cols = [col for col, info in schema.get('columns', {}).items()
                           if info.get('semantic_type') == 'account_code']

        for col in account_code_cols:
            if col in cleaned_data.columns:
                # 转换为大写
                cleaned_data[col] = cleaned_data[col].astype(str).str.upper()
                # 移除特殊字符
                cleaned_data[col] = cleaned_data[col].str.replace(r'[^A-Z0-9]', '', regex=True)

        # 2. 标准化金额格式
        amount_cols = [col for col, info in schema.get('columns', {}).items()
                      if info.get('semantic_type') in ['amount', 'debit_amount', 'credit_amount']]

        for col in amount_cols:
            if col in cleaned_data.columns and pd.api.types.is_numeric_dtype(cleaned_data[col]):
                # 四舍五入到分
                cleaned_data[col] = cleaned_data[col].round(2)
                # 确保非负（除非明确允许负值）
                if col != 'amount':  # amount字段可能为负
                    cleaned_data[col] = cleaned_data[col].abs()

        # 3. 标准化日期格式
        date_cols = [col for col, info in schema.get('columns', {}).items()
                    if info.get('semantic_type') == 'date']

        for col in date_cols:
            if col in cleaned_data.columns and pd.api.types.is_datetime64_any_dtype(cleaned_data[col]):
                # 移除时间部分，只保留日期
                cleaned_data[col] = cleaned_data[col].dt.date

        return cleaned_data

    async def _apply_auto_fixes(self, data: pd.DataFrame, schema: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
        """应用自动修复"""
        fixed_data = data.copy()
        fix_actions = []

        # 1. 修复明显的数据录入错误
        for col_name, col_info in schema.get('columns', {}).items():
            if col_name not in fixed_data.columns:
                continue

            semantic_type = col_info.get('semantic_type', 'unknown')

            # 修复金额字段的明显错误
            if semantic_type in ['amount', 'debit_amount', 'credit_amount']:
                original_count = len(fixed_data)

                # 修复明显过大的金额（可能是录入错误）
                q99 = fixed_data[col_name].quantile(0.99)
                extreme_threshold = q99 * 100  # 99分位数的100倍作为阈值

                extreme_mask = fixed_data[col_name] > extreme_threshold
                extreme_count = extreme_mask.sum()

                if extreme_count > 0 and extreme_count < original_count * 0.01:  # 少于1%的数据
                    # 可能的修复：去掉多余的零
                    fixed_data.loc[extreme_mask, col_name] = fixed_data.loc[extreme_mask, col_name] / 100
                    fix_actions.append(f"Auto-fixed {extreme_count} extreme values in {col_name} by dividing by 100")

        # 2. 修复借贷不平衡
        debit_cols = [col for col, info in schema.get('columns', {}).items()
                     if info.get('semantic_type') == 'debit_amount']
        credit_cols = [col for col, info in schema.get('columns', {}).items()
                      if info.get('semantic_type') == 'credit_amount']

        if debit_cols and credit_cols:
            total_debit = fixed_data[debit_cols].sum().sum()
            total_credit = fixed_data[credit_cols].sum().sum()
            difference = abs(total_debit - total_credit)

            if 0.01 < difference < 100:  # 小额不平衡，可能是录入错误
                # 简单修复：调整最大金额的记录
                if total_debit > total_credit:
                    max_debit_idx = fixed_data[debit_cols[0]].idxmax()
                    fixed_data.loc[max_debit_idx, debit_cols[0]] -= difference
                else:
                    max_credit_idx = fixed_data[credit_cols[0]].idxmax()
                    fixed_data.loc[max_credit_idx, credit_cols[0]] -= difference

                fix_actions.append(f"Auto-fixed debit/credit imbalance: {difference:.2f}")

        return fixed_data, fix_actions

    async def _generate_overall_recommendations(self, cleaning_result: Dict[str, Any]) -> List[str]:
        """生成整体改进建议"""
        recommendations = []

        # 基于整体质量分数
        overall_score = cleaning_result['overall_quality_score']

        if overall_score < 0.7:
            recommendations.append("Data quality is below acceptable threshold - consider data source review")
        elif overall_score < 0.9:
            recommendations.append("Data quality is good but has room for improvement")

        # 基于表级质量分析
        poor_quality_tables = []
        for table_name, quality_report in cleaning_result['quality_reports'].items():
            if quality_report['overall_score'] < 0.8:
                poor_quality_tables.append(table_name)

        if poor_quality_tables:
            recommendations.append(f"Focus quality improvement efforts on: {', '.join(poor_quality_tables)}")

        # 基于清洗效果
        improvements = []
        for table_name, quality_report in cleaning_result['quality_reports'].items():
            improvement = quality_report.get('improvement', 0)
            if improvement > 0.1:
                improvements.append((table_name, improvement))

        if improvements:
            improvements.sort(key=lambda x: x[1], reverse=True)
            best_improved = improvements[0]
            recommendations.append(f"Significant quality improvement achieved in {best_improved[0]} (+{best_improved[1]:.1%})")

        return recommendations

    def _log_cleaning_statistics(self, table_name: str, original_data: pd.DataFrame,
                               cleaned_data: pd.DataFrame, actions: List[str]):
        """记录清洗统计信息"""
        original_rows = len(original_data)
        cleaned_rows = len(cleaned_data)
        rows_removed = original_rows - cleaned_rows

        original_nulls = original_data.isnull().sum().sum()
        cleaned_nulls = cleaned_data.isnull().sum().sum()
        nulls_handled = original_nulls - cleaned_nulls

        self.logger.info(f"Cleaning statistics for {table_name}:")
        self.logger.info(f"  Rows: {original_rows} -> {cleaned_rows} (removed: {rows_removed})")
        self.logger.info(f"  Null values: {original_nulls} -> {cleaned_nulls} (handled: {nulls_handled})")
        self.logger.info(f"  Actions performed: {len(actions)}")

        for action in actions:
            self.logger.info(f"    - {action}")

    def get_quality_score(self) -> float:
        """获取最近一次清洗的质量分数"""
        return getattr(self, '_last_quality_score', 0.0)

# 测试函数
async def test_intelligent_scrubber():
    """测试智能数据清洗器"""
    print("Testing Intelligent Data Scrubber...")

    # 创建测试数据
    test_data = {
        'general_ledger': pd.DataFrame({
            '科目编码': ['1001', '1002', '2001', '2002', ''],
            '科目名称': ['现金', '银行存款', '应付账款', '预收账款', None],
            '借方金额': ['1000.0', '2000', '0', '0.0', 'invalid'],
            '贷方金额': [0.0, 0.0, 1500.0, 500.0, np.nan],
            '凭证号': ['GL001', 'GL002', 'GL003', 'GL004', 'GL001'],  # 重复
            '日期': ['2024-01-01', '2024/01/02', '01-03-2024', '2024-01-04', 'invalid']
        })
    }

    test_schema = {
        'tables': {
            'general_ledger': {
                'columns': {
                    '科目编码': {'semantic_type': 'account_code'},
                    '科目名称': {'semantic_type': 'account_name'},
                    '借方金额': {'semantic_type': 'debit_amount'},
                    '贷方金额': {'semantic_type': 'credit_amount'},
                    '凭证号': {'semantic_type': 'voucher_no'},
                    '日期': {'semantic_type': 'date'}
                }
            }
        }
    }

    scrubber = IntelligentDataScrubber()
    result = await scrubber.clean_with_intelligence(test_data, test_schema)

    print(f"Cleaning result: {json.dumps(result, indent=2, ensure_ascii=False, default=str)}")

if __name__ == "__main__":
    asyncio.run(test_intelligent_scrubber())