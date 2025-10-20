"""
Utility script to validate schema changes and run automated tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

from layer1.storage_manager import StorageManager


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "dap_data.db"


def ensure_database_tables(expected_tables: Iterable[str]) -> None:
    """
    Confirm that each expected table exists in the SQLite catalogue.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        for table in expected_tables:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cursor.fetchone() is None:
                raise RuntimeError(f"Missing table {table} in {DB_PATH}")


def run_pytest() -> int:
    """
    Execute pytest with verbose output. Propagate exit code.
    """
    command = [sys.executable, "-m", "pytest", "-v", "tests"]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return result.returncode


def main() -> int:
    StorageManager(str(DB_PATH))
    expected = [
        "audit_documents",
        "audit_document_versions",
        "attachments",
        "attachment_links",
        "attachment_ocr_results",
    ]
    ensure_database_tables(expected)
    return run_pytest()


if __name__ == "__main__":
    sys.exit(main())
