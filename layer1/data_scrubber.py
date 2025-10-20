"""
DAP - 数据清洗器
智能清洗和标准化数据
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataScrubber:
    """智能数据清洗器"""

    def __init__(self):
        # 清洗规则配置
        self.cleaning_rules = {
            "remove_duplicates": True,
            "standardize_text": True,
            "normalize_dates": True,
            "clean_currency": True,
            "handle_nulls": True,
            "validate_integrity": True,
        }

        # 日期格式模式
        self.date_formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%m-%d-%Y",
            "%m/%d/%Y",
            "%m.%d.%Y",
            "%Y%m%d",
            "%Y-%m-%d %H:%M:%S",
        ]

        # 货币符号模式
        self.currency_pattern = re.compile(r"[￥$¥,，\s]")

        # 文本清理模式
        self.text_patterns = {
            "extra_spaces": re.compile(r"\s+"),
            "special_chars": re.compile(r"[^\w\s\u4e00-\u9fff]"),
            "leading_trailing": re.compile(r"^\s+|\s+$"),
        }

    def clean_data(
        self, raw_data: Dict[str, pd.DataFrame], schema: Dict[str, Any]
    ) -> Dict[str, pd.DataFrame]:
        """清洗所有表的数据"""
        logger.info("开始数据清洗")

        cleaned_data = {}

        for table_name, table_data in raw_data.items():
            logger.info(f"清洗表: {table_name}")

            # 获取表的模式信息
            table_schema = schema.get(table_name, {})

            # 应用清洗规则
            cleaned_table = self.clean_table(table_data, table_schema)

            # 验证清洗结果
            validation_result = self.validate_cleaned_data(cleaned_table, table_schema)

            if validation_result["is_valid"]:
                cleaned_data[table_name] = cleaned_table
                logger.info(f"表 {table_name} 清洗完成，共 {len(cleaned_table)} 行")
            else:
                logger.warning(f"表 {table_name} 清洗后验证失败: {validation_result['errors']}")
                # 即使验证失败也保留数据，但添加标记
                cleaned_table["_data_quality_issues"] = True
                cleaned_data[table_name] = cleaned_table

        logger.info("数据清洗完成")
        return cleaned_data

    def clean_table(
        self, data: pd.DataFrame, table_schema: Dict[str, Any]
    ) -> pd.DataFrame:
        """清洗单个表"""
        # 创建数据副本
        cleaned_data = data.copy()

        # 获取列类型信息
        column_types = table_schema.get("columns", {})

        # 1. 清洗列名
        cleaned_data = self._clean_column_names(cleaned_data)

        # 2. 处理每列数据
        for column in cleaned_data.columns:
            column_info = column_types.get(column, {})
            column_type = column_info.get("type", "text")

            if column_type == "date":
                cleaned_data[column] = self._clean_date_column(cleaned_data[column])
            elif column_type == "currency":
                cleaned_data[column] = self._clean_currency_column(cleaned_data[column])
            elif column_type in ["integer", "float"]:
                cleaned_data[column] = self._clean_numeric_column(
                    cleaned_data[column], column_type
                )
            elif column_type == "text":
                cleaned_data[column] = self._clean_text_column(cleaned_data[column])
            elif column_type == "boolean":
                cleaned_data[column] = self._clean_boolean_column(cleaned_data[column])

        # 3. 处理空值
        cleaned_data = self._handle_null_values(cleaned_data, column_types)

        # 4. 去除重复行
        if self.cleaning_rules["remove_duplicates"]:
            cleaned_data = self._remove_duplicates(cleaned_data)

        # 5. 数据完整性检查
        if self.cleaning_rules["validate_integrity"]:
            cleaned_data = self._validate_data_integrity(cleaned_data, table_schema)

        return cleaned_data

    def _clean_column_names(self, data: pd.DataFrame) -> pd.DataFrame:
        """清洗列名"""
        new_columns = []

        for col in data.columns:
            # 移除前后空格
            clean_col = str(col).strip()

            # 替换特殊字符为下划线
            clean_col = re.sub(r"[^\w\u4e00-\u9fff]", "_", clean_col)

            # 移除连续的下划线
            clean_col = re.sub(r"_+", "_", clean_col)

            # 移除开头和结尾的下划线
            clean_col = clean_col.strip("_")

            new_columns.append(clean_col)

        data.columns = new_columns
        return data

    def _clean_date_column(self, series: pd.Series) -> pd.Series:
        """清洗日期列"""
        if series.empty:
            return series

        cleaned_series = series.copy()

        # 尝试多种日期格式进行解析
        for date_format in self.date_formats:
            try:
                parsed_dates = pd.to_datetime(
                    cleaned_series, format=date_format, errors="coerce"
                )
                valid_count = parsed_dates.notna().sum()

                # 如果大部分日期能被解析，使用此格式
                if valid_count / len(cleaned_series) > 0.8:
                    return parsed_dates.dt.strftime("%Y-%m-%d")
            except Exception:
                continue

        # 如果上述格式都不行，尝试自动推断
        try:
            parsed_dates = pd.to_datetime(
                cleaned_series, errors="coerce", format="mixed"
            )
            return parsed_dates.dt.strftime("%Y-%m-%d")
        except Exception:
            logger.warning(f"无法解析日期列，保持原格式")
            return cleaned_series

    def _clean_currency_column(self, series: pd.Series) -> pd.Series:
        """清洗货币列"""
        if series.empty:
            return series

        cleaned_series = series.copy()

        # 转换为字符串处理
        str_series = cleaned_series.astype(str)

        # 移除货币符号和分隔符
        cleaned_values = []
        for value in str_series:
            if pd.isna(value) or value in ["nan", "None", ""]:
                cleaned_values.append(np.nan)
                continue

            # 移除货币符号和逗号
            clean_value = self.currency_pattern.sub("", str(value))

            try:
                # 转换为浮点数
                numeric_value = float(clean_value)
                cleaned_values.append(numeric_value)
            except ValueError:
                # 如果转换失败，保持原值
                cleaned_values.append(np.nan)

        return pd.Series(cleaned_values, index=series.index)

    def _clean_numeric_column(self, series: pd.Series, numeric_type: str) -> pd.Series:
        """清洗数值列"""
        if series.empty:
            return series

        cleaned_series = series.copy()

        # 转换为字符串处理特殊字符
        str_series = cleaned_series.astype(str)

        cleaned_values = []
        for value in str_series:
            if pd.isna(value) or value in ["nan", "None", ""]:
                cleaned_values.append(np.nan)
                continue

            # 移除非数字字符（保留小数点和负号）
            clean_value = re.sub(r"[^\d.-]", "", str(value))

            try:
                if numeric_type == "integer":
                    numeric_value = int(float(clean_value))
                else:  # float
                    numeric_value = float(clean_value)
                cleaned_values.append(numeric_value)
            except ValueError:
                cleaned_values.append(np.nan)

        return pd.Series(cleaned_values, index=series.index)

    def _clean_text_column(self, series: pd.Series) -> pd.Series:
        """清洗文本列"""
        if series.empty:
            return series

        cleaned_series = series.copy()

        # 转换为字符串
        str_series = cleaned_series.astype(str)

        cleaned_values = []
        for value in str_series:
            if pd.isna(value) or value in ["nan", "None"]:
                cleaned_values.append(np.nan)
                continue

            # 移除前后空格
            clean_value = str(value).strip()

            # 标准化空格（多个空格替换为单个空格）
            clean_value = self.text_patterns["extra_spaces"].sub(" ", clean_value)

            # 如果配置了移除特殊字符
            if self.cleaning_rules.get("clean_special_chars", False):
                clean_value = self.text_patterns["special_chars"].sub("", clean_value)

            cleaned_values.append(clean_value if clean_value else np.nan)

        return pd.Series(cleaned_values, index=series.index)

    def _clean_boolean_column(self, series: pd.Series) -> pd.Series:
        """清洗布尔列"""
        if series.empty:
            return series

        # 布尔值映射
        boolean_mapping = {
            "true": True,
            "false": False,
            "是": True,
            "否": False,
            "yes": True,
            "no": False,
            "y": True,
            "n": False,
            "1": True,
            "0": False,
            "启用": True,
            "禁用": False,
            "有效": True,
            "无效": False,
            "通过": True,
            "失败": False,
        }

        cleaned_values = []
        for value in series:
            if pd.isna(value):
                cleaned_values.append(np.nan)
                continue

            str_value = str(value).lower().strip()
            boolean_value = boolean_mapping.get(str_value)

            if boolean_value is not None:
                cleaned_values.append(boolean_value)
            else:
                # 如果无法映射，尝试直接转换
                try:
                    cleaned_values.append(bool(value))
                except:
                    cleaned_values.append(np.nan)

        return pd.Series(cleaned_values, index=series.index)

    def _handle_null_values(
        self, data: pd.DataFrame, column_types: Dict[str, Any]
    ) -> pd.DataFrame:
        """处理空值"""
        cleaned_data = data.copy()

        for column in cleaned_data.columns:
            column_info = column_types.get(column, {})
            column_type = column_info.get("type", "text")
            null_ratio = column_info.get("null_ratio", 0)

            # 如果空值比例过高（>50%），标记为可选字段
            if null_ratio > 0.5:
                cleaned_data[f"{column}_is_null"] = cleaned_data[column].isnull()
                continue

            # 根据数据类型填充空值
            if column_type == "currency":
                # 金额字段用0填充
                cleaned_data[column] = cleaned_data[column].fillna(0)
            elif column_type in ["integer", "float"]:
                # 数值字段用中位数填充
                median_value = cleaned_data[column].median()
                if not pd.isna(median_value):
                    cleaned_data[column] = cleaned_data[column].fillna(median_value)
            elif column_type == "date":
                # 日期字段用前向填充
                cleaned_data[column] = cleaned_data[column].ffill()
            elif column_type == "boolean":
                # 布尔字段用最常见的值填充
                mode_value = cleaned_data[column].mode()
                if not mode_value.empty:
                    cleaned_data[column] = cleaned_data[column].fillna(mode_value[0])
            elif column_type == "text":
                # 文本字段用"未知"填充
                cleaned_data[column] = cleaned_data[column].fillna("未知")

        return cleaned_data

    def _remove_duplicates(self, data: pd.DataFrame) -> pd.DataFrame:
        """移除重复行"""
        initial_count = len(data)

        # 完全重复的行
        data_no_duplicates = data.drop_duplicates()

        duplicate_count = initial_count - len(data_no_duplicates)
        if duplicate_count > 0:
            logger.info(f"移除了 {duplicate_count} 行重复数据")

        return data_no_duplicates

    def _validate_data_integrity(
        self, data: pd.DataFrame, table_schema: Dict[str, Any]
    ) -> pd.DataFrame:
        """验证数据完整性"""
        # 检查主键唯一性
        primary_keys = table_schema.get("primary_keys", [])

        for pk in primary_keys:
            if pk in data.columns:
                duplicate_pks = data[data[pk].duplicated()]
                if not duplicate_pks.empty:
                    logger.warning(f"主键 {pk} 存在重复值: {len(duplicate_pks)} 行")
                    # 为重复的主键添加后缀
                    data[pk] = self._make_unique_values(data[pk])

        return data

    def _make_unique_values(self, series: pd.Series) -> pd.Series:
        """使重复值唯一"""
        value_counts = {}
        unique_values = []

        for value in series:
            if pd.isna(value):
                unique_values.append(value)
                continue

            if value in value_counts:
                value_counts[value] += 1
                unique_values.append(f"{value}_{value_counts[value]}")
            else:
                value_counts[value] = 0
                unique_values.append(value)

        return pd.Series(unique_values, index=series.index)

    def validate_cleaned_data(
        self, data: pd.DataFrame, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证清洗后的数据质量"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "metrics": {},
        }

        # 检查数据是否为空
        if data.empty:
            validation_result["errors"].append("数据为空")
            validation_result["is_valid"] = False
            return validation_result

        # 检查列类型一致性
        column_types = schema.get("columns", {})
        for column, type_info in column_types.items():
            if column not in data.columns:
                validation_result["warnings"].append(f"预期列 {column} 不存在")
                continue

            expected_type = type_info.get("type")
            actual_type = self._infer_actual_type(data[column])

            if expected_type != actual_type:
                validation_result["warnings"].append(
                    f"列 {column} 类型不匹配: 预期 {expected_type}, 实际 {actual_type}"
                )

        # 计算数据质量指标
        validation_result["metrics"] = {
            "total_rows": len(data),
            "total_columns": len(data.columns),
            "null_ratio": data.isnull().sum().sum() / data.size if data.size > 0 else 0,
            "duplicate_ratio": data.duplicated().sum() / len(data)
            if len(data) > 0
            else 0,
        }

        return validation_result

    def _infer_actual_type(self, series: pd.Series) -> str:
        """推断实际数据类型"""
        if series.dtype in ["int64", "int32"]:
            return "integer"
        elif series.dtype in ["float64", "float32"]:
            return "float"
        elif series.dtype == "bool":
            return "boolean"
        elif series.dtype == "datetime64[ns]":
            return "date"
        else:
            # 尝试推断是否为货币类型
            sample = series.dropna().head(10)
            if sample.empty:
                return "text"

            numeric_count = 0
            for value in sample:
                try:
                    float(value)
                    numeric_count += 1
                except:
                    pass

            if numeric_count / len(sample) > 0.8:
                return "currency"
            else:
                return "text"

    def generate_cleaning_report(
        self,
        original_data: Dict[str, pd.DataFrame],
        cleaned_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, Any]:
        """生成清洗报告"""
        report = {
            "summary": {
                "tables_processed": len(cleaned_data),
                "total_original_rows": sum(len(df) for df in original_data.values()),
                "total_cleaned_rows": sum(len(df) for df in cleaned_data.values()),
            },
            "table_details": {},
        }

        for table_name in cleaned_data.keys():
            if table_name in original_data:
                original_df = original_data[table_name]
                cleaned_df = cleaned_data[table_name]

                table_report = {
                    "original_rows": len(original_df),
                    "cleaned_rows": len(cleaned_df),
                    "rows_removed": len(original_df) - len(cleaned_df),
                    "original_null_count": original_df.isnull().sum().sum(),
                    "cleaned_null_count": cleaned_df.isnull().sum().sum(),
                    "null_reduction": original_df.isnull().sum().sum()
                    - cleaned_df.isnull().sum().sum(),
                }

                report["table_details"][table_name] = table_report

        return report


# 测试函数
def test_data_scrubber():
    """测试数据清洗器"""
    # 创建测试数据（包含各种需要清洗的问题）
    test_data = pd.DataFrame(
        {
            "id": [1, 2, 3, 3, 5],  # 包含重复
            "name": ["  公司A  ", "Company B", "  企业C", None, "单位D"],  # 包含空格和空值
            "amount": ["￥1,000.00", "$2000", "3000", "invalid", "5000.50"],  # 货币格式不统一
            "date": [
                "2023-01-01",
                "01/02/2023",
                "2023.03.01",
                "invalid_date",
                "20230405",
            ],  # 日期格式不统一
            "status": ["是", "否", "true", "false", 1],  # 布尔值格式不统一
            "notes": ["  多个   空格  ", "normal text", "", None, "some@#$%text"],  # 文本需要清理
        }
    )

    # 模式信息
    schema = {
        "test_table": {
            "columns": {
                "id": {"type": "integer"},
                "name": {"type": "text"},
                "amount": {"type": "currency"},
                "date": {"type": "date"},
                "status": {"type": "boolean"},
                "notes": {"type": "text"},
            },
            "primary_keys": ["id"],
        }
    }

    # 执行清洗
    scrubber = DataScrubber()
    cleaned_data = scrubber.clean_data({"test_table": test_data}, schema)

    # 显示结果
    print("原始数据:")
    print(test_data)
    print("\n清洗后数据:")
    print(cleaned_data["test_table"])

    # 生成清洗报告
    report = scrubber.generate_cleaning_report({"test_table": test_data}, cleaned_data)
    print("\n清洗报告:")
    print(report)


if __name__ == "__main__":
    test_data_scrubber()
