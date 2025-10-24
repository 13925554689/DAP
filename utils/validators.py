"""
DAP - Input Validation Module
Provides unified data validation functionality
"""

import re
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from .exceptions import ValidationError, SecurityError


class ProcessingRequest(BaseModel):
    """Data processing request validation model"""

    data_source_path: str = Field(..., description="Data source path")
    options: Dict[str, Any] = Field(default_factory=dict, description="Processing options")

    @field_validator("data_source_path")
    def validate_path(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValidationError("Data source path cannot be empty")

        path = Path(value)

        if not path.exists():
            raise ValidationError(f"Data source does not exist: {value}")

        if not path.is_file() and not path.is_dir():
            raise ValidationError(f"Invalid path type: {value}")

        if not os.access(path, os.R_OK):
            raise ValidationError(f"Data source is not readable: {value}")

        return str(path.absolute())

    @field_validator("options", mode="before")
    def validate_options(cls, value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError("Options must be a dictionary")

        allowed_options = {
            "start_api_server",
            "auto_ai_analysis",
            "batch_size",
            "parallel_processing",
            "max_workers",
        }

        for key in value.keys():
            if not isinstance(key, str):
                raise ValidationError(f"Option key must be string: {key}")
            if key not in allowed_options:
                print(f"Warning: unknown option {key}")

        return value


class SQLQueryValidator:
    """SQL query validator"""

    # Dangerous SQL keywords
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

    # Allowed table name pattern
    TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

    @classmethod
    def validate_table_name(cls, table_name: str) -> str:
        """Validate table name security"""
        if not table_name or not table_name.strip():
            raise SecurityError("Table name cannot be empty")

        table_name = table_name.strip()

        # Check table name format
        if not cls.TABLE_NAME_PATTERN.match(table_name):
            raise SecurityError(f"Invalid table name format: {table_name}")

        # Check length
        if len(table_name) > 64:
            raise SecurityError(f"Table name too long: {table_name}")

        # Check for dangerous keywords
        table_lower = table_name.lower()
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in table_lower:
                raise SecurityError(f"Table name contains dangerous keyword: {table_name}")

        return table_name

    @classmethod
    def validate_column_name(cls, column_name: str) -> str:
        """Validate column name security"""
        if not column_name or not column_name.strip():
            raise SecurityError("Column name cannot be empty")

        column_name = column_name.strip()

        # Use same pattern for column validation
        if not cls.TABLE_NAME_PATTERN.match(column_name):
            raise SecurityError(f"Invalid column name format: {column_name}")

        if len(column_name) > 64:
            raise SecurityError(f"Column name too long: {column_name}")

        return column_name

    @classmethod
    def validate_query_safety(cls, query: str) -> str:
        """Validate query statement security"""
        if not query or not query.strip():
            raise SecurityError("Query statement cannot be empty")

        query_lower = query.lower().strip()

        # Check if SELECT statement
        if not query_lower.startswith("select"):
            raise SecurityError("Only SELECT queries are allowed")

        # Check for dangerous keywords
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in query_lower:
                raise SecurityError(f"Query contains dangerous keyword: {keyword}")

        # Check semicolon (prevent SQL injection)
        if ";" in query and not query.strip().endswith(";"):
            raise SecurityError("Query contains multiple statements")

        return query.strip()


class FileValidator:
    """File validator"""

    # Allowed file extensions
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

    # Maximum file size (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024

    @classmethod
    def validate_file_path(cls, file_path: str) -> str:
        """Validate file path"""
        if not file_path or not file_path.strip():
            raise ValidationError("File path cannot be empty")

        path = Path(file_path).expanduser()
        resolved_path = path.resolve()

        if not resolved_path.exists():
            raise ValidationError(f"File does not exist: {file_path}")

        if not resolved_path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}")

        if resolved_path.suffix.lower() not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(f"Unsupported file type: {resolved_path.suffix}")

        try:
            file_size = os.path.getsize(resolved_path)
        except OSError as exc:
            raise ValidationError(f"Cannot get file size: {exc}") from exc

        if file_size > cls.MAX_FILE_SIZE:
            raise ValidationError(f"File too large: {file_size / 1024 / 1024:.1f}MB (max 100MB)")

        if not os.access(resolved_path, os.R_OK):
            raise ValidationError(f"File not readable: {file_path}")

        # Security check - validate path is within allowed directories
        try:
            resolved_path.relative_to(Path.cwd().resolve())
        except ValueError:
            # Not in current directory, check other allowed roots
            allowed_roots = [
                Path.cwd(),
                Path(tempfile.gettempdir()),
                Path("C:\\Data"),
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
                raise SecurityError(f"Access to path not allowed: {file_path}")

        return str(resolved_path)

    @classmethod
    def validate_directory_path(cls, dir_path: str) -> str:
        """Validate directory path"""
        if not dir_path or not dir_path.strip():
            raise ValidationError("Directory path cannot be empty")

        path = Path(dir_path)
        resolved_path = path.resolve()

        if not resolved_path.exists():
            raise ValidationError(f"Directory does not exist: {dir_path}")

        if not resolved_path.is_dir():
            raise ValidationError(f"Path is not a directory: {dir_path}")

        # Security check
        try:
            resolved_path.relative_to(Path.cwd().resolve())
        except ValueError:
            allowed_roots = [
                Path.cwd(),
                Path(tempfile.gettempdir()),
                Path("C:\\Data"),
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
                raise SecurityError(f"Access to directory not allowed: {dir_path}")

        if not os.access(resolved_path, os.R_OK):
            raise ValidationError(f"Directory not readable: {dir_path}")

        return str(resolved_path)


def validate_api_input(
    data: Dict[str, Any], required_fields: List[str] = None
) -> Dict[str, Any]:
    """Validate API input data"""
    if not isinstance(data, dict):
        raise ValidationError("Input data must be a dictionary")

    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")

    return data
