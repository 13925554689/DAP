"""
DAP - 输入验证模块
提供统一的数据验证功能
"""

import re
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from .exceptions import ValidationError, SecurityError


class ProcessingRequest(BaseModel):
    """数据处理请求验证模型"""

    data_source_path: str = Field(..., description="数据源路径")
    options: Dict[str, Any] = Field(default_factory=dict, description="处理选项")

    @field_validator("data_source_path")
    def validate_path(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValidationError("数据源路径不能为空")

        path = Path(value)

        if not path.exists():
            raise ValidationError(f"数据源不存在: {value}")

        if not path.is_file() and not path.is_dir():
            raise ValidationError(f"无效的路径类型: {value}")

        if not os.access(path, os.R_OK):
            raise ValidationError(f"数据源无法读取: {value}")

        return str(path.absolute())

    @field_validator("options", mode="before")
    def validate_options(cls, value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError("选项必须是字典类型")

        allowed_options = {
            "start_api_server",
            "auto_ai_analysis",
            "batch_size",
            "parallel_processing",
            "max_workers",
        }

        for key in value.keys():
            if not isinstance(key, str):
                raise ValidationError(f"选项键必须是字符串: {key}")
            if key not in allowed_options:
                print(f"警告: 未知选项 {key}")

        return value


class SQLQueryValidator:
    """SQL查询验证器"""

    # 危险的SQL关键词
    DANGEROUS_KEYWORDS = {
        "drop",
        "delete",
        "truncate",
        "alter",
        "create",
        "insert",
        "update",
        "grant",
        "revoke",
        "exec",
        "execute",
        "sp_",
        "xp_",
    }

    # 允许的表名模式
    TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

    @classmethod
    def validate_table_name(cls, table_name: str) -> str:
        """验证表名安全性"""
        if not table_name or not table_name.strip():
            raise SecurityError("表名不能为空")

        table_name = table_name.strip()

        # 检查表名格式
        if not cls.TABLE_NAME_PATTERN.match(table_name):
            raise SecurityError(f"无效的表名格式: {table_name}")

        # 检查长度
        if len(table_name) > 64:
            raise SecurityError(f"表名过长: {table_name}")

        # 检查是否包含危险关键词
        table_lower = table_name.lower()
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in table_lower:
                raise SecurityError(f"表名包含危险关键词: {table_name}")

        return table_name

    @classmethod
    def validate_column_name(cls, column_name: str) -> str:
        """验证列名安全性"""
        if not column_name or not column_name.strip():
            raise SecurityError("列名不能为空")

        column_name = column_name.strip()

        # 使用相同的模式验证列名
        if not cls.TABLE_NAME_PATTERN.match(column_name):
            raise SecurityError(f"无效的列名格式: {column_name}")

        if len(column_name) > 64:
            raise SecurityError(f"列名过长: {column_name}")

        return column_name

    @classmethod
    def validate_query_safety(cls, query: str) -> str:
        """验证查询语句安全性"""
        if not query or not query.strip():
            raise SecurityError("查询语句不能为空")

        query_lower = query.lower().strip()

        # 检查是否为SELECT语句
        if not query_lower.startswith("select"):
            raise SecurityError("只允许SELECT查询")

        # 检查危险关键词
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in query_lower:
                raise SecurityError(f"查询包含危险关键词: {keyword}")

        # 检查分号（防止SQL注入）
        if ";" in query and not query.strip().endswith(";"):
            raise SecurityError("查询中包含多条语句")

        return query.strip()


class FileValidator:
    """文件验证器"""

    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {
        ".xlsx",
        ".xls",
        ".csv",
        ".zip",
        ".rar",
        ".7z",
        ".mdb",
        ".accdb",
        ".db",
        ".sqlite",
        ".ais",
        ".bak",
        ".sql",
    }

    # 最大文件大小 (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024

    @classmethod
    def validate_file_path(cls, file_path: str) -> str:
        """验证文件路径"""
        if not file_path or not file_path.strip():
            raise ValidationError("文件路径不能为空")

        path = Path(file_path).expanduser()
        resolved_path = path.resolve()

        if not resolved_path.exists():
            raise ValidationError(f"文件不存在: {file_path}")

        if not resolved_path.is_file():
            raise ValidationError(f"路径不是文件: {file_path}")

        if resolved_path.suffix.lower() not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(f"不支持的文件类型: {resolved_path.suffix}")

        try:
            file_size = os.path.getsize(resolved_path)
        except OSError as exc:
            raise ValidationError(f"无法获取文件大小: {exc}") from exc

        if file_size > cls.MAX_FILE_SIZE:
            raise ValidationError(f"文件过大: {file_size / 1024 / 1024:.1f}MB (最大100MB)")

        if not os.access(resolved_path, os.R_OK):
            raise ValidationError(f"文件无法读取: {file_path}")

        try:
            resolved_path.relative_to(Path.cwd().resolve())
        except ValueError:
            allowed_roots = [
                Path.cwd(),
                Path(tempfile.gettempdir()),
                Path("C\\Data"),
                Path("/data"),
            ]
            for root in allowed_roots:
                try:
                    root_resolved = root.resolve()
                except Exception:
                    continue

                if not root_resolved.exists():
                    continue

                try:
                    resolved_path.relative_to(root_resolved)
                    break
                except ValueError:
                    continue
            else:
                raise SecurityError(f"不允许访问此路径: {file_path}")

        return str(resolved_path)

    @classmethod
    def validate_directory_path(cls, dir_path: str) -> str:
        """验证目录路径"""
        if not dir_path or not dir_path.strip():
            raise ValidationError("目录路径不能为空")

        path = Path(dir_path)
        resolved_path = path.resolve()

        if not resolved_path.exists():
            raise ValidationError(f"目录不存在: {dir_path}")

        if not resolved_path.is_dir():
            raise ValidationError(f"路径不是目录: {dir_path}")

        try:
            resolved_path.relative_to(Path.cwd().resolve())
        except ValueError:
            allowed_roots = [
                Path.cwd(),
                Path(tempfile.gettempdir()),
                Path("C\\Data"),
                Path("/data"),
            ]
            for root in allowed_roots:
                try:
                    root_resolved = root.resolve()
                except Exception:
                    continue

                if not root_resolved.exists():
                    continue

                try:
                    resolved_path.relative_to(root_resolved)
                    break
                except ValueError:
                    continue
            else:
                raise SecurityError(f"不允许访问此目录: {dir_path}")

        if not os.access(resolved_path, os.R_OK):
            raise ValidationError(f"目录无法读取: {dir_path}")

        return str(resolved_path)


def validate_api_input(
    data: Dict[str, Any], required_fields: List[str] = None
) -> Dict[str, Any]:
    """验证API输入数据"""
    if not isinstance(data, dict):
        raise ValidationError("输入数据必须是字典类型")

    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f"缺少必需字段: {', '.join(missing_fields)}")

    return data
