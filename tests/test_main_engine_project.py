import logging

import pytest

from layer1.storage_manager import StorageManager
from main_engine import EnhancedDAPEngine


def build_engine(db_path: str) -> EnhancedDAPEngine:
    engine = EnhancedDAPEngine.__new__(EnhancedDAPEngine)
    engine.storage_manager = StorageManager(db_path)
    return engine


def test_prepare_project_context_existing(tmp_path):
    db_path = tmp_path / "engine_existing.db"
    engine = build_engine(str(db_path))
    storage_manager = engine.storage_manager
    project_id = storage_manager.create_project(
        project_name="现有项目",
        project_code="EX-001",
    )

    context = EnhancedDAPEngine._prepare_project_context(
        engine,
        {"project_code": "EX-001"},
    )

    assert context["project_id"] == project_id
    assert storage_manager.get_current_project_id() == project_id


def test_prepare_project_context_autocreate(tmp_path, caplog):
    db_path = tmp_path / "engine_autocreate.db"
    engine = build_engine(str(db_path))
    storage_manager = engine.storage_manager

    with caplog.at_level(logging.INFO):
        context = EnhancedDAPEngine._prepare_project_context(
            engine,
            {"project_name": "新增项目", "project_code": "NEW-001"},
        )

    created_id = context["project_id"]
    assert created_id != storage_manager.DEFAULT_PROJECT_ID
    project = storage_manager.get_project(created_id)
    assert project is not None
    assert project["project_name"] == "新增项目"
    assert storage_manager.get_current_project_id() == created_id


def test_prepare_project_context_defaults(tmp_path):
    db_path = tmp_path / "engine_default.db"
    engine = build_engine(str(db_path))
    storage_manager = engine.storage_manager

    context = EnhancedDAPEngine._prepare_project_context(engine, {})

    assert context["project_id"] == storage_manager.DEFAULT_PROJECT_ID
    assert storage_manager.get_current_project_id() == storage_manager.DEFAULT_PROJECT_ID
