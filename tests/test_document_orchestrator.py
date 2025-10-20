import io
import json
from pathlib import Path

import pytest
import yaml

from layer1.storage_manager import StorageManager
from layer4.document_orchestrator import DocumentOrchestrator


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def orchestrator_env(tmp_path):
    db_path = tmp_path / "test.db"
    output_dir = tmp_path / "output"
    attachments_dir = tmp_path / "attachments"
    template_path = tmp_path / "templates.yaml"

    storage = StorageManager(str(db_path))

    with storage.connection_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE test_table (
                col1 TEXT,
                col2 TEXT
            )
            """
        )
        cursor.execute(
            "INSERT INTO test_table (col1, col2) VALUES (?, ?)",
            ("value-1", "project-123"),
        )
        cursor.execute(
            """
            INSERT INTO meta_companies (company_id, company_name, company_code, industry)
            VALUES (?, ?, ?, ?)
            """,
            ("company-xyz", "���Թ�˾", "COMP-XYZ", "����ҵ"),
        )
        cursor.execute(
            """
            INSERT INTO dap_projects (
                project_id, project_code, project_name, client_name,
                fiscal_year, fiscal_period, status, created_by, settings
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("project-123", "PRJ-123", "������Ŀ", "���Թ�˾", None, None, "active", "unit-test", None),
        )
        cursor.execute(
            """
            INSERT INTO meta_projects (project_id, project_name, project_code, company_id, project_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("project-123", "������Ŀ", "PRJ-123", "company-xyz", "���"),
        )
        conn.commit()

    template_content = {
        "templates": {
            "test_template": {
                "description": "测试模板",
                "output_formats": ["json"],
                "data_bindings": {
                    "header": {
                        "source": "test_table",
                        "select": ["col1"],
                        "filters": {"col2": "project_id"},
                    },
                    "summary": {
                        "query": "SELECT :project_id AS project_ref"
                    },
                },
                "layout": {},
            }
        },
        "default_settings": {
            "output_path": str(output_dir),
            "attachment_storage": {
                "path": str(attachments_dir),
                "chunk_size": 4096,
                "max_file_size": 10 * 1024 * 1024,
                "encryption": {
                    "enabled": True,
                    "algorithm": "xor",
                    "key": "unit-test-key",
                    "key_id": "unit-key",
                },
            },
            "lineage_fields": ["project_id", "company_id"],
        },
    }
    template_path.write_text(
        yaml.safe_dump(template_content, allow_unicode=True),
        encoding="utf-8",
    )

    orchestrator = DocumentOrchestrator(
        storage_manager=storage,
        template_path=template_path,
    )

    yield {
        "orchestrator": orchestrator,
        "storage": storage,
        "template_path": template_path,
        "output_dir": output_dir,
    }

    orchestrator.close()


def test_list_templates_reads_yaml(orchestrator_env):
    orchestrator = orchestrator_env["orchestrator"]
    templates = orchestrator.list_templates()
    names = {item["name"] for item in templates}
    assert "test_template" in names


def test_generate_document_persists_metadata(orchestrator_env):
    orchestrator = orchestrator_env["orchestrator"]
    storage = orchestrator_env["storage"]

    result = orchestrator.generate_document(
        "test_template",
        project_id="project-123",
        company_id="company-xyz",
        requested_by="tester",
    )

    assert result["doc_type"] == "test_template"
    assert result["status"] == "generated"
    assert result["project_id"] == "project-123"
    storage_path = (REPO_ROOT / result["storage_path"]).resolve()
    assert storage_path.exists()

    payload = json.loads(storage_path.read_text(encoding="utf-8"))
    assert payload["context"]["project_id"] == "project-123"
    assert payload["data"]["header"][0]["col1"] == "value-1"
    assert payload["data"]["summary"][0]["project_ref"] == "project-123"

    with storage.connection_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT project_id FROM audit_documents WHERE document_id = ?",
            (result["document_id"],),
        )
        assert cursor.fetchone()[0] == "project-123"

        cursor.execute(
            "SELECT COUNT(*) FROM audit_document_versions WHERE document_id = ?",
            (result["document_id"],),
        )
        assert cursor.fetchone()[0] == 1


def test_get_document_includes_versions(orchestrator_env):
    orchestrator = orchestrator_env["orchestrator"]

    generated = orchestrator.generate_document(
        "test_template",
        project_id="project-123",
        company_id="company-xyz",
    )

    document = orchestrator.get_document(
        generated["document_id"], project_id="project-123"
    )
    assert document is not None
    assert document["document_id"] == generated["document_id"]
    assert document["project_id"] == "project-123"
    assert document["versions"], "Expected at least one version entry"


def test_save_attachment_encrypted_large_file(orchestrator_env):
    orchestrator = orchestrator_env["orchestrator"]
    storage = orchestrator_env["storage"]

    payload = io.BytesIO(b"a" * (orchestrator.chunk_size + 128))
    result = orchestrator.save_attachment(
        file_stream=payload,
        original_filename="test_receipt.pdf",
        category="vouchers",
        voucher_id="VCH-001",
        target_table="test_table",
        target_record_id="record-123",
        metadata={"source": "unit-test"},
        uploaded_by="tester",
        project_id="project-123",
    )

    assert result["attachment_id"]
    assert result["project_id"] == "project-123"
    assert result["metadata"]["original_size"] == orchestrator.chunk_size + 128
    assert "encryption" in result["metadata"]
    assert result["metadata"]["checksum"]

    stored_path = Path(result["storage_path"])
    if not stored_path.is_absolute():
        stored_path = (REPO_ROOT / result["storage_path"]).resolve()
    assert stored_path.exists()

    with storage.connection_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT project_id, encryption_key_id, upload_status FROM attachments WHERE attachment_id = ?",
            (result["attachment_id"],),
        )
        project_id_value, key_id, status = cursor.fetchone()
        assert project_id_value == "project-123"
        assert key_id is not None
        assert status == "encrypted"
