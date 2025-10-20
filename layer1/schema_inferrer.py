"""
DAP - 模式推断器
智能推断数据结构、类型和关系
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class SchemaInferrer:
    """智能模式推断器"""

    def __init__(self):
        # 常见的业务字段模式
        self.business_patterns = {
            "company": ["公司", "company", "corp", "enterprise", "企业", "单位"],
            "project": ["项目", "project", "proj", "工程", "工程项目"],
            "date": ["日期", "date", "time", "时间", "datetime", "创建时间", "更新时间"],
            "amount": ["金额", "amount", "money", "数量", "quantity", "价格", "price"],
            "account": ["科目", "account", "subject", "会计科目", "账户"],
            "customer": ["客户", "customer", "client", "客户名称"],
            "vendor": ["供应商", "vendor", "supplier", "供货商"],
            "employee": ["员工", "employee", "staff", "职员", "人员"],
        }

        # 数据类型推断的置信度阈值
        self.confidence_threshold = 0.8

    def infer_schema(self, tables_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """推断完整的数据模式"""
        logger.info("开始推断数据模式")

        schema = {}

        for table_name, data in tables_data.items():
            logger.info(f"推断表结构: {table_name}")

            table_schema = {
                "columns": self.infer_column_types(data),
                "relationships": {},  # 将在后面填充
                "primary_keys": self.infer_primary_keys(data),
                "business_meaning": self.infer_business_meaning(table_name, data),
                "data_quality": self.analyze_data_quality(data),
                "statistics": self.generate_statistics(data),
            }

            schema[table_name] = table_schema

        # 推断表间关系
        for table_name in schema.keys():
            schema[table_name]["relationships"] = self.infer_relationships(
                table_name, tables_data[table_name], tables_data
            )

        logger.info("数据模式推断完成")
        return schema

    def infer_column_types(self, data: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """推断列数据类型"""
        column_types = {}

        for column in data.columns:
            sample_data = data[column].dropna()

            if sample_data.empty:
                column_types[column] = {
                    "type": "unknown",
                    "confidence": 0.0,
                    "nullable": True,
                    "unique_values": 0,
                }
                continue

            # 取样分析（最多1000条记录）
            sample = sample_data.head(1000)

            # 推断类型
            inferred_type = self._infer_single_column_type(sample, column)

            column_types[column] = {
                "type": inferred_type["type"],
                "confidence": inferred_type["confidence"],
                "nullable": data[column].isnull().any(),
                "unique_values": data[column].nunique(),
                "sample_values": sample.head(5).tolist(),
                "null_ratio": data[column].isnull().sum() / len(data),
            }

        return column_types

    def _infer_single_column_type(
        self, sample: pd.Series, column_name: str
    ) -> Dict[str, Any]:
        """推断单个列的数据类型"""
        # 首先检查是否为日期类型
        date_confidence = self._check_date_type(sample)
        if date_confidence > self.confidence_threshold:
            return {"type": "date", "confidence": date_confidence}

        # 检查是否为货币/金额类型
        currency_confidence = self._check_currency_type(sample, column_name)
        if currency_confidence > self.confidence_threshold:
            return {"type": "currency", "confidence": currency_confidence}

        # 检查是否为整数类型
        integer_confidence = self._check_integer_type(sample)
        if integer_confidence > self.confidence_threshold:
            return {"type": "integer", "confidence": integer_confidence}

        # 检查是否为浮点数类型
        float_confidence = self._check_float_type(sample)
        if float_confidence > self.confidence_threshold:
            return {"type": "float", "confidence": float_confidence}

        # 检查是否为布尔类型
        boolean_confidence = self._check_boolean_type(sample)
        if boolean_confidence > self.confidence_threshold:
            return {"type": "boolean", "confidence": boolean_confidence}

        # 检查是否为分类类型
        categorical_confidence = self._check_categorical_type(sample)
        if categorical_confidence > self.confidence_threshold:
            return {"type": "categorical", "confidence": categorical_confidence}

        # 默认为文本类型
        return {"type": "text", "confidence": 0.9}

    def _check_date_type(self, sample: pd.Series) -> float:
        """检查是否为日期类型"""
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{2}/\d{2}/\d{4}",  # MM/DD/YYYY
            r"\d{4}/\d{2}/\d{2}",  # YYYY/MM/DD
            r"\d{2}-\d{2}-\d{4}",  # MM-DD-YYYY
            r"\d{4}\d{2}\d{2}",  # YYYYMMDD
        ]

        total_count = len(sample)
        if total_count == 0:
            return 0.0

        # 尝试用pandas解析日期
        try:
            parsed = pd.to_datetime(sample, errors="coerce", dayfirst=False)
            valid_dates = parsed.notna().sum()
            pandas_confidence = valid_dates / total_count

            if pandas_confidence > 0.8:
                return pandas_confidence
        except Exception:
            pass

        # 使用正则表达式检查
        pattern_matches = 0
        for value in sample.astype(str):
            for pattern in date_patterns:
                if re.match(pattern, str(value).strip()):
                    pattern_matches += 1
                    break

        return pattern_matches / total_count

    def _check_currency_type(self, sample: pd.Series, column_name: str) -> float:
        """检查是否为货币/金额类型"""
        # 列名检查
        currency_keywords = [
            "金额",
            "amount",
            "money",
            "价格",
            "price",
            "费用",
            "cost",
            "收入",
            "revenue",
        ]
        name_match = any(
            keyword in column_name.lower() for keyword in currency_keywords
        )

        # 数值检查
        numeric_confidence = self._check_numeric_with_currency_symbols(sample)

        # 综合评分
        if name_match and numeric_confidence > 0.7:
            return min(0.95, numeric_confidence + 0.2)
        elif name_match or numeric_confidence > 0.8:
            return max(numeric_confidence, 0.8)
        else:
            return numeric_confidence

    def _check_numeric_with_currency_symbols(self, sample: pd.Series) -> float:
        """检查带货币符号的数值"""
        total_count = len(sample)
        if total_count == 0:
            return 0.0

        numeric_count = 0
        for value in sample:
            str_value = str(value).strip()
            # 移除货币符号和逗号
            cleaned_value = re.sub(r"[￥$,¥]", "", str_value)
            try:
                float(cleaned_value)
                numeric_count += 1
            except ValueError:
                continue

        return numeric_count / total_count

    def _check_integer_type(self, sample: pd.Series) -> float:
        """检查是否为整数类型"""
        total_count = len(sample)
        if total_count == 0:
            return 0.0

        integer_count = 0
        for value in sample:
            try:
                if isinstance(value, (int, np.integer)):
                    integer_count += 1
                elif isinstance(value, (float, np.floating)):
                    if value.is_integer():
                        integer_count += 1
                else:
                    int(str(value).strip())
                    integer_count += 1
            except (ValueError, TypeError):
                continue

        return integer_count / total_count

    def _check_float_type(self, sample: pd.Series) -> float:
        """检查是否为浮点数类型"""
        total_count = len(sample)
        if total_count == 0:
            return 0.0

        float_count = 0
        for value in sample:
            try:
                float(str(value).strip())
                float_count += 1
            except (ValueError, TypeError):
                continue

        return float_count / total_count

    def _check_boolean_type(self, sample: pd.Series) -> float:
        """检查是否为布尔类型"""
        unique_values = set(str(v).lower().strip() for v in sample.unique())

        boolean_patterns = [
            {"true", "false"},
            {"是", "否"},
            {"yes", "no"},
            {"y", "n"},
            {"1", "0"},
            {"启用", "禁用"},
            {"有效", "无效"},
        ]

        for pattern in boolean_patterns:
            if unique_values.issubset(pattern) and len(unique_values) == 2:
                return 0.95

        return 0.0

    def _check_categorical_type(self, sample: pd.Series) -> float:
        """检查是否为分类类型"""
        total_count = len(sample)
        unique_count = sample.nunique()

        if total_count == 0:
            return 0.0

        # 如果唯一值比例小于30%，可能是分类变量
        unique_ratio = unique_count / total_count

        if unique_ratio < 0.1:  # 重复度很高
            return 0.9
        elif unique_ratio < 0.3:  # 中等重复度
            return 0.7
        else:
            return 0.0

    def infer_primary_keys(self, data: pd.DataFrame) -> List[str]:
        """推断主键"""
        potential_keys = []

        for column in data.columns:
            # 检查唯一性
            if data[column].nunique() == len(data):
                # 检查列名模式
                if any(
                    pattern in column.lower() for pattern in ["id", "key", "编号", "代码"]
                ):
                    potential_keys.append(column)

        return potential_keys

    def infer_business_meaning(
        self, table_name: str, data: pd.DataFrame
    ) -> Dict[str, Any]:
        """推断业务含义"""
        business_meaning = {
            "table_type": self._classify_table_type(table_name, data),
            "column_meanings": {},
            "business_domain": self._infer_business_domain(table_name, data),
        }

        # 为每列推断业务含义
        for column in data.columns:
            meaning = self._classify_column_meaning(column)
            if meaning:
                business_meaning["column_meanings"][column] = meaning

        return business_meaning

    def _classify_table_type(self, table_name: str, data: pd.DataFrame) -> str:
        """分类表类型"""
        name_lower = table_name.lower()

        if any(keyword in name_lower for keyword in ["general_ledger", "总账", "科目余额"]):
            return "general_ledger"
        elif any(keyword in name_lower for keyword in ["customer", "客户", "client"]):
            return "customer_master"
        elif any(keyword in name_lower for keyword in ["vendor", "供应商", "supplier"]):
            return "vendor_master"
        elif any(keyword in name_lower for keyword in ["employee", "员工", "staff"]):
            return "employee_master"
        elif any(keyword in name_lower for keyword in ["sales", "销售", "order"]):
            return "sales_transaction"
        elif any(
            keyword in name_lower for keyword in ["purchase", "采购", "procurement"]
        ):
            return "purchase_transaction"
        elif any(keyword in name_lower for keyword in ["inventory", "库存", "stock"]):
            return "inventory_master"
        else:
            return "unknown"

    def _classify_column_meaning(self, column_name: str) -> Optional[str]:
        """分类列的业务含义"""
        name_lower = column_name.lower()

        for meaning, patterns in self.business_patterns.items():
            if any(pattern in name_lower for pattern in patterns):
                return meaning

        return None

    def _infer_business_domain(self, table_name: str, data: pd.DataFrame) -> str:
        """推断业务领域"""
        # 基于表名和列名推断业务领域
        financial_keywords = ["account", "ledger", "balance", "科目", "余额", "金额"]
        hr_keywords = ["employee", "staff", "员工", "人事", "薪资"]
        sales_keywords = ["customer", "sales", "order", "客户", "销售", "订单"]

        text_content = f"{table_name} {' '.join(data.columns)}".lower()

        if any(keyword in text_content for keyword in financial_keywords):
            return "financial"
        elif any(keyword in text_content for keyword in hr_keywords):
            return "human_resources"
        elif any(keyword in text_content for keyword in sales_keywords):
            return "sales"
        else:
            return "general"

    def infer_relationships(
        self,
        current_table: str,
        current_data: pd.DataFrame,
        all_tables: Dict[str, pd.DataFrame],
    ) -> List[Dict[str, Any]]:
        """推断表间关系"""
        relationships = []

        for other_table, other_data in all_tables.items():
            if other_table == current_table:
                continue

            # 寻找外键关系
            foreign_keys = self._find_foreign_keys(
                current_data, other_data, other_table
            )
            relationships.extend(foreign_keys)

        return relationships

    def _find_foreign_keys(
        self, table1: pd.DataFrame, table2: pd.DataFrame, table2_name: str
    ) -> List[Dict[str, Any]]:
        """寻找外键关系"""
        foreign_keys = []

        for col1 in table1.columns:
            for col2 in table2.columns:
                # 名称相似度检查
                name_similarity = self._calculate_name_similarity(col1, col2)

                if name_similarity > 0.8:
                    # 值匹配度检查
                    value_match_ratio = self._calculate_value_match_ratio(
                        table1[col1], table2[col2]
                    )

                    if value_match_ratio > 0.7:
                        foreign_keys.append(
                            {
                                "from_column": col1,
                                "to_table": table2_name,
                                "to_column": col2,
                                "confidence": min(name_similarity, value_match_ratio),
                                "match_ratio": value_match_ratio,
                            }
                        )

        return foreign_keys

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """计算列名相似度"""
        name1_clean = name1.lower().strip()
        name2_clean = name2.lower().strip()

        # 完全匹配
        if name1_clean == name2_clean:
            return 1.0

        # 包含关系
        if name1_clean in name2_clean or name2_clean in name1_clean:
            return 0.9

        # Jaccard相似度
        set1 = set(name1_clean)
        set2 = set(name2_clean)

        if len(set1) == 0 and len(set2) == 0:
            return 1.0

        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))

        return intersection / union if union > 0 else 0.0

    def _calculate_value_match_ratio(
        self, series1: pd.Series, series2: pd.Series
    ) -> float:
        """计算值匹配比例"""
        # 移除空值
        clean_series1 = series1.dropna()
        clean_series2 = series2.dropna()

        if len(clean_series1) == 0 or len(clean_series2) == 0:
            return 0.0

        # 转换为字符串集合
        set1 = set(str(v) for v in clean_series1.unique())
        set2 = set(str(v) for v in clean_series2.unique())

        # 计算交集比例
        if len(set1) == 0:
            return 0.0

        intersection = len(set1.intersection(set2))
        return intersection / len(set1)

    def analyze_data_quality(self, data: pd.DataFrame) -> Dict[str, Any]:
        """分析数据质量"""
        total_rows = len(data)
        total_cells = data.size

        quality_metrics = {
            "total_rows": total_rows,
            "total_columns": len(data.columns),
            "null_cells": data.isnull().sum().sum(),
            "null_ratio": data.isnull().sum().sum() / total_cells
            if total_cells > 0
            else 0,
            "duplicate_rows": data.duplicated().sum(),
            "duplicate_ratio": data.duplicated().sum() / total_rows
            if total_rows > 0
            else 0,
            "column_quality": {},
        }

        # 每列的质量分析
        for column in data.columns:
            col_quality = {
                "null_count": data[column].isnull().sum(),
                "null_ratio": data[column].isnull().sum() / total_rows
                if total_rows > 0
                else 0,
                "unique_count": data[column].nunique(),
                "unique_ratio": data[column].nunique() / total_rows
                if total_rows > 0
                else 0,
            }
            quality_metrics["column_quality"][column] = col_quality

        return quality_metrics

    def generate_statistics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """生成数据统计信息"""
        stats = {
            "shape": data.shape,
            "memory_usage": data.memory_usage(deep=True).sum(),
            "numeric_columns": [],
            "text_columns": [],
            "date_columns": [],
        }

        # 分类列类型
        for column in data.columns:
            if data[column].dtype in ["int64", "float64", "int32", "float32"]:
                stats["numeric_columns"].append(column)
            elif data[column].dtype == "object":
                # 尝试判断是否为日期
                try:
                    pd.to_datetime(
                        data[column].head(10), errors="raise", format="mixed"
                    )
                    stats["date_columns"].append(column)
                except:
                    stats["text_columns"].append(column)

        return stats


# 测试函数
def test_schema_inferrer():
    """测试模式推断器"""
    # 创建测试数据
    test_data = {
        "customers": pd.DataFrame(
            {
                "customer_id": [1, 2, 3, 4, 5],
                "customer_name": ["公司A", "公司B", "公司C", "公司D", "公司E"],
                "registration_date": [
                    "2023-01-01",
                    "2023-01-02",
                    "2023-01-03",
                    "2023-01-04",
                    "2023-01-05",
                ],
                "credit_limit": [100000.00, 200000.00, 150000.00, 300000.00, 250000.00],
                "status": ["有效", "有效", "无效", "有效", "有效"],
            }
        ),
        "sales_orders": pd.DataFrame(
            {
                "order_id": [1001, 1002, 1003, 1004, 1005],
                "customer_id": [1, 2, 1, 3, 2],
                "order_date": [
                    "2023-02-01",
                    "2023-02-02",
                    "2023-02-03",
                    "2023-02-04",
                    "2023-02-05",
                ],
                "order_amount": [50000, 75000, 30000, 120000, 90000],
                "status": ["已完成", "进行中", "已完成", "已取消", "已完成"],
            }
        ),
    }

    # 执行推断
    inferrer = SchemaInferrer()
    schema = inferrer.infer_schema(test_data)

    # 打印结果
    for table_name, table_schema in schema.items():
        print(f"\n表: {table_name}")
        print(f"业务类型: {table_schema['business_meaning']['table_type']}")
        print(f"主键: {table_schema['primary_keys']}")
        print("列信息:")
        for col, col_info in table_schema["columns"].items():
            print(f"  {col}: {col_info['type']} (置信度: {col_info['confidence']:.2f})")


if __name__ == "__main__":
    test_schema_inferrer()
