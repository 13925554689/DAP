#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Schema Inferrer - AI增强的模式推断器
使用机器学习和业务上下文进行智能数据模式推断

核心功能：
1. 智能数据类型推断
2. 业务语义识别
3. 表间关系推断
4. 审计字段识别
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json

# ML和NLP相关导入
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity
    import jieba  # 中文分词
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# 导入基础模式推断器
try:
    from .schema_inferrer import SchemaInferrer
except ImportError:
    from schema_inferrer import SchemaInferrer

logger = logging.getLogger(__name__)

class BusinessSemanticRecognizer:
    """业务语义识别器"""

    def __init__(self):
        # 审计业务词典
        self.audit_patterns = {
            'account_code': [
                '科目编码', '科目代码', '会计科目编码', 'account_code', 'account_id',
                '科目号', 'subject_code', 'gl_code'
            ],
            'account_name': [
                '科目名称', '会计科目', 'account_name', 'subject_name',
                '科目', 'account', 'subject'
            ],
            'amount': [
                '金额', '数额', '余额', 'amount', 'balance', 'money',
                '本期金额', '期末余额', '发生额', '累计金额'
            ],
            'debit_amount': [
                '借方金额', '借方', '借方发生额', 'debit', 'debit_amount',
                '借方余额', 'dr_amount', 'debit_balance'
            ],
            'credit_amount': [
                '贷方金额', '贷方', '贷方发生额', 'credit', 'credit_amount',
                '贷方余额', 'cr_amount', 'credit_balance'
            ],
            'date': [
                '日期', '时间', 'date', 'time', '会计期间', '期间',
                '凭证日期', '业务日期', '记账日期', 'voucher_date'
            ],
            'voucher_no': [
                '凭证号', '凭证编号', '单据号', 'voucher_no', 'voucher_id',
                '记账凭证号', 'document_no', 'doc_no'
            ],
            'description': [
                '摘要', '说明', '备注', '描述', 'description', 'memo',
                '业务描述', 'summary', 'remark', 'comment'
            ],
            'customer': [
                '客户', '客户名称', 'customer', 'client', '往来单位',
                '供应商', 'vendor', 'supplier'
            ],
            'department': [
                '部门', '科室', '中心', 'department', 'dept', 'division',
                '成本中心', 'cost_center'
            ],
            'project': [
                '项目', '工程', 'project', 'job', '项目编号', 'project_code'
            ]
        }

        # 数据类型模式
        self.data_type_patterns = {
            'currency': {
                'patterns': [r'^\-?\d+\.?\d*$', r'^\-?\d{1,3}(,\d{3})*\.?\d*$'],
                'keywords': ['金额', '余额', 'amount', 'balance', '价格', 'price']
            },
            'percentage': {
                'patterns': [r'^\d+\.?\d*%$', r'^0\.\d+$'],
                'keywords': ['率', '比例', 'rate', 'ratio', 'percent']
            },
            'date': {
                'patterns': [
                    r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
                    r'^\d{4}/\d{2}/\d{2}$',  # YYYY/MM/DD
                    r'^\d{2}-\d{2}-\d{4}$',  # DD-MM-YYYY
                    r'^\d{8}$'               # YYYYMMDD
                ],
                'keywords': ['日期', 'date', '时间', 'time']
            },
            'code': {
                'patterns': [r'^[A-Z0-9]{2,}$', r'^\d{4,}$'],
                'keywords': ['编码', '代码', 'code', '编号', 'id']
            }
        }

        if ML_AVAILABLE:
            self.vectorizer = TfidfVectorizer(
                stop_words='english',
                max_features=1000,
                tokenizer=self._chinese_tokenize
            )
            self._train_semantic_model()

    def _chinese_tokenize(self, text: str) -> List[str]:
        """中文分词"""
        if ML_AVAILABLE:
            return list(jieba.cut(text.lower()))
        else:
            return text.lower().split()

    def _train_semantic_model(self):
        """训练语义识别模型"""
        if not ML_AVAILABLE:
            return

        try:
            # 准备训练文本
            texts = []
            labels = []

            for category, keywords in self.audit_patterns.items():
                text = ' '.join(keywords)
                texts.append(text)
                labels.append(category)

            # 训练向量化器
            self.semantic_vectors = self.vectorizer.fit_transform(texts)
            self.semantic_labels = labels

            logger.info("Semantic recognition model trained successfully")

        except Exception as e:
            logger.warning(f"Failed to train semantic model: {e}")

    def recognize_semantic_type(self, column_name: str, sample_data: pd.Series) -> Dict[str, Any]:
        """
        识别列的业务语义类型

        Args:
            column_name: 列名
            sample_data: 样本数据

        Returns:
            识别结果
        """
        result = {
            'semantic_type': 'unknown',
            'confidence': 0.0,
            'data_type': 'object',
            'business_meaning': None,
            'validation_rules': []
        }

        # 基于名称的语义识别
        name_result = self._recognize_by_name(column_name)

        # 基于数据模式的类型识别
        data_result = self._recognize_by_data_pattern(sample_data)

        # 综合判断
        if name_result['confidence'] > 0.7:
            result.update(name_result)
        elif data_result['confidence'] > 0.6:
            result.update(data_result)
        else:
            # 使用置信度更高的结果
            if name_result['confidence'] > data_result['confidence']:
                result.update(name_result)
            else:
                result.update(data_result)

        # 生成验证规则
        result['validation_rules'] = self._generate_validation_rules(result)

        return result

    def _recognize_by_name(self, column_name: str) -> Dict[str, Any]:
        """基于列名识别语义类型"""
        column_name_lower = column_name.lower()

        best_match = None
        best_score = 0

        # 规则匹配
        for semantic_type, keywords in self.audit_patterns.items():
            for keyword in keywords:
                if keyword.lower() in column_name_lower:
                    score = len(keyword) / len(column_name_lower)  # 匹配度
                    if score > best_score:
                        best_score = score
                        best_match = semantic_type

        # ML匹配 (如果可用)
        if ML_AVAILABLE and hasattr(self, 'semantic_vectors') and best_score < 0.8:
            ml_result = self._ml_semantic_recognition(column_name)
            if ml_result['confidence'] > best_score:
                return ml_result

        if best_match:
            return {
                'semantic_type': best_match,
                'confidence': min(1.0, best_score * 2),  # 增强置信度
                'method': 'name_matching'
            }

        return {'semantic_type': 'unknown', 'confidence': 0.0, 'method': 'name_matching'}

    def _ml_semantic_recognition(self, column_name: str) -> Dict[str, Any]:
        """基于ML的语义识别"""
        if not ML_AVAILABLE or not hasattr(self, 'semantic_vectors'):
            return {'semantic_type': 'unknown', 'confidence': 0.0, 'method': 'ml'}

        try:
            query_vector = self.vectorizer.transform([column_name])
            similarities = cosine_similarity(query_vector, self.semantic_vectors)[0]

            best_idx = np.argmax(similarities)
            best_similarity = similarities[best_idx]
            best_semantic_type = self.semantic_labels[best_idx]

            return {
                'semantic_type': best_semantic_type,
                'confidence': float(best_similarity),
                'method': 'ml'
            }

        except Exception as e:
            logger.warning(f"ML semantic recognition failed: {e}")
            return {'semantic_type': 'unknown', 'confidence': 0.0, 'method': 'ml'}

    def _recognize_by_data_pattern(self, sample_data: pd.Series) -> Dict[str, Any]:
        """基于数据模式识别类型"""
        if sample_data.empty:
            return {'semantic_type': 'unknown', 'confidence': 0.0, 'method': 'data_pattern'}

        # 获取非空样本
        non_null_data = sample_data.dropna()
        if non_null_data.empty:
            return {'semantic_type': 'unknown', 'confidence': 0.0, 'method': 'data_pattern'}

        # 转换为字符串进行模式匹配
        str_data = non_null_data.astype(str)

        best_type = 'unknown'
        best_score = 0

        for data_type, type_info in self.data_type_patterns.items():
            score = 0
            match_count = 0

            # 模式匹配
            for pattern in type_info['patterns']:
                matches = str_data.str.match(pattern, na=False).sum()
                match_ratio = matches / len(str_data)
                if match_ratio > 0.5:  # 至少50%匹配
                    score = max(score, match_ratio)
                    match_count += matches

            if score > best_score:
                best_score = score
                best_type = data_type

        return {
            'semantic_type': best_type,
            'confidence': best_score,
            'data_type': self._infer_pandas_dtype(sample_data, best_type),
            'method': 'data_pattern'
        }

    def _infer_pandas_dtype(self, sample_data: pd.Series, semantic_type: str) -> str:
        """推断pandas数据类型"""
        if semantic_type == 'currency':
            return 'float64'
        elif semantic_type == 'percentage':
            return 'float64'
        elif semantic_type == 'date':
            return 'datetime64[ns]'
        elif semantic_type == 'code':
            return 'object'
        else:
            # 使用pandas自动推断
            return str(pd.api.types.infer_dtype(sample_data))

    def _generate_validation_rules(self, recognition_result: Dict[str, Any]) -> List[str]:
        """生成数据验证规则"""
        rules = []
        semantic_type = recognition_result.get('semantic_type', 'unknown')

        if semantic_type == 'amount' or semantic_type == 'debit_amount' or semantic_type == 'credit_amount':
            rules.extend([
                'must_be_numeric',
                'can_be_negative',
                'precision_2_decimal'
            ])
        elif semantic_type == 'date':
            rules.extend([
                'must_be_valid_date',
                'reasonable_date_range'
            ])
        elif semantic_type == 'account_code':
            rules.extend([
                'not_null',
                'alphanumeric_only',
                'min_length_2'
            ])
        elif semantic_type == 'voucher_no':
            rules.extend([
                'not_null',
                'unique_per_period'
            ])

        return rules

class AISchemaInferrer:
    """AI增强的模式推断器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 语义识别器
        self.semantic_recognizer = BusinessSemanticRecognizer()

        # 基础模式推断器
        try:
            self.base_inferrer = SchemaInferrer()
        except:
            self.base_inferrer = None

        # 关系推断配置
        self.relationship_config = {
            'similarity_threshold': 0.8,
            'foreign_key_threshold': 0.7,
            'max_unique_ratio': 0.9  # 外键字段的唯一值比例阈值
        }

        self.logger.info("AI Schema Inferrer initialized")

    async def infer_with_ai(self, raw_data: Dict[str, Any], business_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用AI进行智能模式推断

        Args:
            raw_data: 原始数据
            business_context: 业务上下文

        Returns:
            推断的模式
        """
        self.logger.info("Starting AI-enhanced schema inference")

        try:
            schema = {
                'tables': {},
                'relationships': [],
                'business_metadata': {},
                'data_quality_assessment': {},
                'recommendations': []
            }

            # 处理每个表
            for table_name, table_data in raw_data.items():
                if isinstance(table_data, pd.DataFrame):
                    table_schema = await self._infer_table_schema(table_name, table_data)
                    schema['tables'][table_name] = table_schema

            # 推断表间关系
            schema['relationships'] = await self._infer_relationships(schema['tables'])

            # 生成业务元数据
            schema['business_metadata'] = await self._generate_business_metadata(schema['tables'])

            # 数据质量评估
            schema['data_quality_assessment'] = await self._assess_data_quality(raw_data, schema)

            # 生成改进建议
            schema['recommendations'] = await self._generate_recommendations(schema)

            self.logger.info("AI-enhanced schema inference completed")
            return schema

        except Exception as e:
            self.logger.error(f"AI schema inference failed: {e}")
            raise

    async def _infer_table_schema(self, table_name: str, table_data: pd.DataFrame) -> Dict[str, Any]:
        """推断单个表的模式"""
        schema = {
            'table_name': table_name,
            'row_count': len(table_data),
            'column_count': len(table_data.columns),
            'columns': {},
            'primary_key_candidates': [],
            'foreign_key_candidates': [],
            'business_classification': None,
            'quality_score': 0.0
        }

        # 推断列模式
        for column_name in table_data.columns:
            column_data = table_data[column_name]
            column_schema = await self._infer_column_schema(column_name, column_data)
            schema['columns'][column_name] = column_schema

        # 识别主键候选
        schema['primary_key_candidates'] = self._identify_primary_key_candidates(table_data, schema['columns'])

        # 识别外键候选
        schema['foreign_key_candidates'] = self._identify_foreign_key_candidates(table_data, schema['columns'])

        # 业务分类
        schema['business_classification'] = self._classify_table_business_type(table_name, schema['columns'])

        # 质量评分
        schema['quality_score'] = self._calculate_table_quality_score(table_data, schema['columns'])

        return schema

    async def _infer_column_schema(self, column_name: str, column_data: pd.Series) -> Dict[str, Any]:
        """推断列的模式"""
        # 基础统计信息
        basic_stats = {
            'data_type': str(column_data.dtype),
            'null_count': column_data.isnull().sum(),
            'null_ratio': column_data.isnull().sum() / len(column_data),
            'unique_count': column_data.nunique(),
            'unique_ratio': column_data.nunique() / len(column_data),
            'sample_values': column_data.dropna().head(5).tolist()
        }

        # AI语义识别
        semantic_info = self.semantic_recognizer.recognize_semantic_type(column_name, column_data)

        # 数据分布分析
        distribution_info = self._analyze_data_distribution(column_data)

        # 合并结果
        column_schema = {
            **basic_stats,
            **semantic_info,
            'distribution': distribution_info,
            'constraints': self._infer_column_constraints(column_data, semantic_info),
            'recommendations': self._generate_column_recommendations(column_name, column_data, semantic_info)
        }

        return column_schema

    def _analyze_data_distribution(self, column_data: pd.Series) -> Dict[str, Any]:
        """分析数据分布"""
        distribution = {
            'type': 'unknown',
            'statistics': {},
            'outliers': []
        }

        try:
            if pd.api.types.is_numeric_dtype(column_data):
                # 数值型数据
                stats = column_data.describe()
                distribution['type'] = 'numeric'
                distribution['statistics'] = {
                    'mean': float(stats['mean']) if not pd.isna(stats['mean']) else None,
                    'median': float(column_data.median()) if not pd.isna(column_data.median()) else None,
                    'std': float(stats['std']) if not pd.isna(stats['std']) else None,
                    'min': float(stats['min']) if not pd.isna(stats['min']) else None,
                    'max': float(stats['max']) if not pd.isna(stats['max']) else None,
                    'q25': float(stats['25%']) if not pd.isna(stats['25%']) else None,
                    'q75': float(stats['75%']) if not pd.isna(stats['75%']) else None
                }

                # 识别异常值
                Q1 = stats['25%']
                Q3 = stats['75%']
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                outliers = column_data[(column_data < lower_bound) | (column_data > upper_bound)]
                distribution['outliers'] = outliers.tolist()[:10]  # 最多显示10个异常值

            elif pd.api.types.is_datetime64_any_dtype(column_data):
                # 日期时间型数据
                distribution['type'] = 'datetime'
                distribution['statistics'] = {
                    'min_date': str(column_data.min()),
                    'max_date': str(column_data.max()),
                    'date_range_days': (column_data.max() - column_data.min()).days
                }

            else:
                # 分类型数据
                value_counts = column_data.value_counts()
                distribution['type'] = 'categorical'
                distribution['statistics'] = {
                    'most_frequent': str(value_counts.index[0]) if len(value_counts) > 0 else None,
                    'most_frequent_count': int(value_counts.iloc[0]) if len(value_counts) > 0 else 0,
                    'category_count': len(value_counts),
                    'top_categories': value_counts.head(5).to_dict()
                }

        except Exception as e:
            self.logger.warning(f"Failed to analyze distribution: {e}")

        return distribution

    def _infer_column_constraints(self, column_data: pd.Series, semantic_info: Dict[str, Any]) -> List[str]:
        """推断列约束"""
        constraints = []

        # 基于语义类型的约束
        semantic_type = semantic_info.get('semantic_type', 'unknown')

        if semantic_type in ['account_code', 'voucher_no']:
            constraints.append('NOT NULL')

        if semantic_type == 'voucher_no':
            constraints.append('UNIQUE')

        if semantic_type in ['amount', 'debit_amount', 'credit_amount']:
            constraints.append('CHECK (value >= 0 OR value IS NULL)')

        # 基于数据分析的约束
        if column_data.isnull().sum() == 0:
            constraints.append('NOT NULL')

        if column_data.nunique() == len(column_data.dropna()):
            constraints.append('UNIQUE')

        return constraints

    def _generate_column_recommendations(self, column_name: str, column_data: pd.Series,
                                       semantic_info: Dict[str, Any]) -> List[str]:
        """生成列改进建议"""
        recommendations = []

        # 数据质量建议
        null_ratio = column_data.isnull().sum() / len(column_data)
        if null_ratio > 0.1:
            recommendations.append(f"High null ratio ({null_ratio:.1%}), consider data quality improvement")

        # 语义建议
        if semantic_info.get('confidence', 0) < 0.5:
            recommendations.append("Low semantic recognition confidence, manual review recommended")

        # 数据类型建议
        if semantic_info.get('semantic_type') == 'date' and not pd.api.types.is_datetime64_any_dtype(column_data):
            recommendations.append("Consider converting to datetime type")

        if semantic_info.get('semantic_type') in ['amount', 'debit_amount', 'credit_amount'] and not pd.api.types.is_numeric_dtype(column_data):
            recommendations.append("Consider converting to numeric type")

        return recommendations

    def _identify_primary_key_candidates(self, table_data: pd.DataFrame, columns_schema: Dict[str, Any]) -> List[str]:
        """识别主键候选"""
        candidates = []

        for column_name, column_schema in columns_schema.items():
            # 主键候选条件
            conditions = [
                column_schema['null_count'] == 0,  # 无空值
                column_schema['unique_ratio'] == 1.0,  # 完全唯一
                column_schema.get('semantic_type') in ['account_code', 'voucher_no', 'id']  # 语义类型
            ]

            if all(conditions):
                candidates.append(column_name)

        return candidates

    def _identify_foreign_key_candidates(self, table_data: pd.DataFrame, columns_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别外键候选"""
        candidates = []

        for column_name, column_schema in columns_schema.items():
            # 外键候选条件
            if (column_schema['unique_ratio'] < self.relationship_config['max_unique_ratio'] and
                column_schema.get('semantic_type') in ['account_code', 'customer', 'department', 'project']):

                candidates.append({
                    'column': column_name,
                    'referenced_table': self._guess_referenced_table(column_schema['semantic_type']),
                    'confidence': column_schema.get('confidence', 0.5)
                })

        return candidates

    def _guess_referenced_table(self, semantic_type: str) -> str:
        """猜测被引用的表"""
        reference_mapping = {
            'account_code': 'chart_of_accounts',
            'customer': 'customers',
            'department': 'departments',
            'project': 'projects'
        }
        return reference_mapping.get(semantic_type, 'unknown')

    def _classify_table_business_type(self, table_name: str, columns_schema: Dict[str, Any]) -> str:
        """分类表的业务类型"""
        # 基于表名和列的语义类型判断业务类型
        semantic_types = [col.get('semantic_type', 'unknown') for col in columns_schema.values()]

        if 'voucher_no' in semantic_types and 'amount' in semantic_types:
            return 'transaction_table'
        elif 'account_code' in semantic_types and 'account_name' in semantic_types:
            return 'master_data_table'
        elif 'customer' in semantic_types:
            return 'customer_table'
        elif 'project' in semantic_types:
            return 'project_table'
        else:
            return 'unknown'

    def _calculate_table_quality_score(self, table_data: pd.DataFrame, columns_schema: Dict[str, Any]) -> float:
        """计算表的质量分数"""
        if table_data.empty:
            return 0.0

        scores = []

        # 完整性分数
        completeness = 1 - (table_data.isnull().sum().sum() / (table_data.shape[0] * table_data.shape[1]))
        scores.append(completeness * 0.4)

        # 一致性分数（基于语义识别置信度）
        confidences = [col.get('confidence', 0) for col in columns_schema.values()]
        consistency = np.mean(confidences) if confidences else 0
        scores.append(consistency * 0.3)

        # 唯一性分数
        uniqueness_scores = []
        for col in columns_schema.values():
            if col.get('semantic_type') in ['account_code', 'voucher_no']:
                uniqueness_scores.append(col.get('unique_ratio', 0))
        uniqueness = np.mean(uniqueness_scores) if uniqueness_scores else 1.0
        scores.append(uniqueness * 0.3)

        return sum(scores)

    async def _infer_relationships(self, tables_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """推断表间关系"""
        relationships = []

        table_names = list(tables_schema.keys())

        for i, table1_name in enumerate(table_names):
            for j, table2_name in enumerate(table_names):
                if i >= j:  # 避免重复比较
                    continue

                table1_schema = tables_schema[table1_name]
                table2_schema = tables_schema[table2_name]

                # 寻找潜在关系
                potential_relations = self._find_potential_relations(table1_schema, table2_schema)

                for relation in potential_relations:
                    relationships.append({
                        'from_table': table1_name,
                        'to_table': table2_name,
                        'from_column': relation['from_column'],
                        'to_column': relation['to_column'],
                        'relationship_type': relation['type'],
                        'confidence': relation['confidence']
                    })

        return relationships

    def _find_potential_relations(self, table1_schema: Dict[str, Any], table2_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """寻找两个表之间的潜在关系"""
        relations = []

        table1_columns = table1_schema['columns']
        table2_columns = table2_schema['columns']

        for col1_name, col1_schema in table1_columns.items():
            for col2_name, col2_schema in table2_columns.items():
                # 检查列名相似度
                name_similarity = self._calculate_column_name_similarity(col1_name, col2_name)

                # 检查语义类型匹配
                semantic_match = col1_schema.get('semantic_type') == col2_schema.get('semantic_type')

                if name_similarity > self.relationship_config['similarity_threshold'] or semantic_match:
                    confidence = max(name_similarity, 0.8 if semantic_match else 0.0)

                    if confidence > self.relationship_config['foreign_key_threshold']:
                        relation_type = self._determine_relationship_type(col1_schema, col2_schema)

                        relations.append({
                            'from_column': col1_name,
                            'to_column': col2_name,
                            'type': relation_type,
                            'confidence': confidence
                        })

        return relations

    def _calculate_column_name_similarity(self, name1: str, name2: str) -> float:
        """计算列名相似度"""
        # 简单的编辑距离相似度
        import difflib
        return difflib.SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

    def _determine_relationship_type(self, col1_schema: Dict[str, Any], col2_schema: Dict[str, Any]) -> str:
        """确定关系类型"""
        # 简化实现：基于唯一性判断
        if col1_schema.get('unique_ratio', 0) == 1.0:
            return 'one_to_many'
        elif col2_schema.get('unique_ratio', 0) == 1.0:
            return 'many_to_one'
        else:
            return 'many_to_many'

    async def _generate_business_metadata(self, tables_schema: Dict[str, Any]) -> Dict[str, Any]:
        """生成业务元数据"""
        metadata = {
            'data_warehouse_layer': self._classify_data_warehouse_layer(tables_schema),
            'audit_significance': self._assess_audit_significance(tables_schema),
            'business_processes': self._identify_business_processes(tables_schema),
            'compliance_requirements': self._identify_compliance_requirements(tables_schema)
        }

        return metadata

    def _classify_data_warehouse_layer(self, tables_schema: Dict[str, Any]) -> Dict[str, str]:
        """分类数据仓库层次"""
        layer_classification = {}

        for table_name, schema in tables_schema.items():
            if schema.get('business_classification') == 'transaction_table':
                layer_classification[table_name] = 'fact_table'
            elif schema.get('business_classification') == 'master_data_table':
                layer_classification[table_name] = 'dimension_table'
            else:
                layer_classification[table_name] = 'staging_table'

        return layer_classification

    def _assess_audit_significance(self, tables_schema: Dict[str, Any]) -> Dict[str, str]:
        """评估审计重要性"""
        significance = {}

        for table_name, schema in tables_schema.items():
            semantic_types = [col.get('semantic_type', 'unknown') for col in schema['columns'].values()]

            if any(st in semantic_types for st in ['amount', 'debit_amount', 'credit_amount']):
                significance[table_name] = 'high'
            elif 'voucher_no' in semantic_types:
                significance[table_name] = 'medium'
            else:
                significance[table_name] = 'low'

        return significance

    def _identify_business_processes(self, tables_schema: Dict[str, Any]) -> List[str]:
        """识别业务流程"""
        processes = set()

        for table_name, schema in tables_schema.items():
            semantic_types = [col.get('semantic_type', 'unknown') for col in schema['columns'].values()]

            if 'customer' in semantic_types:
                processes.add('accounts_receivable')
            if 'vendor' in table_name.lower() or 'supplier' in table_name.lower():
                processes.add('accounts_payable')
            if 'payroll' in table_name.lower() or 'salary' in table_name.lower():
                processes.add('payroll')
            if any(st in semantic_types for st in ['amount', 'debit_amount', 'credit_amount']):
                processes.add('general_ledger')

        return list(processes)

    def _identify_compliance_requirements(self, tables_schema: Dict[str, Any]) -> List[str]:
        """识别合规要求"""
        requirements = set()

        for table_name, schema in tables_schema.items():
            semantic_types = [col.get('semantic_type', 'unknown') for col in schema['columns'].values()]

            if any(st in semantic_types for st in ['amount', 'debit_amount', 'credit_amount']):
                requirements.add('SOX_compliance')
                requirements.add('financial_reporting')

            if 'customer' in semantic_types:
                requirements.add('data_privacy')

        return list(requirements)

    async def _assess_data_quality(self, raw_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """评估数据质量"""
        assessment = {
            'overall_score': 0.0,
            'table_scores': {},
            'quality_issues': [],
            'improvement_suggestions': []
        }

        table_scores = []

        for table_name, table_schema in schema['tables'].items():
            score = table_schema.get('quality_score', 0.0)
            table_scores.append(score)
            assessment['table_scores'][table_name] = score

            # 识别质量问题
            if score < 0.7:
                assessment['quality_issues'].append(f"Table {table_name} has low quality score: {score:.2f}")

        assessment['overall_score'] = np.mean(table_scores) if table_scores else 0.0

        return assessment

    async def _generate_recommendations(self, schema: Dict[str, Any]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 基于数据质量的建议
        overall_quality = schema.get('data_quality_assessment', {}).get('overall_score', 0.0)

        if overall_quality < 0.8:
            recommendations.append("Consider data quality improvement initiatives")

        # 基于关系的建议
        relationships = schema.get('relationships', [])
        if not relationships:
            recommendations.append("No clear relationships detected - consider adding foreign key constraints")

        # 基于业务元数据的建议
        audit_significance = schema.get('business_metadata', {}).get('audit_significance', {})
        high_significance_tables = [table for table, sig in audit_significance.items() if sig == 'high']

        if high_significance_tables:
            recommendations.append(f"Focus audit attention on high-significance tables: {', '.join(high_significance_tables)}")

        return recommendations

# 测试函数
async def test_ai_schema_inferrer():
    """测试AI模式推断器"""
    print("Testing AI Schema Inferrer...")

    # 创建测试数据
    test_data = {
        'general_ledger': pd.DataFrame({
            '科目编码': ['1001', '1002', '2001', '2002'],
            '科目名称': ['现金', '银行存款', '应付账款', '预收账款'],
            '借方金额': [1000.0, 2000.0, 0.0, 0.0],
            '贷方金额': [0.0, 0.0, 1500.0, 500.0],
            '凭证号': ['GL001', 'GL002', 'GL003', 'GL004'],
            '日期': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']
        })
    }

    inferrer = AISchemaInferrer()
    result = await inferrer.infer_with_ai(test_data)

    print(f"Schema inference result: {json.dumps(result, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    asyncio.run(test_ai_schema_inferrer())