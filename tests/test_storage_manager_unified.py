import pandas as pd

from layer1.storage_manager import StorageManager


def test_unified_tables_keep_data_per_project(tmp_path):
    db_path = tmp_path / "unified.db"
    manager = StorageManager(str(db_path))

    project_a = "proj_a"
    project_b = "proj_b"

    data_a = pd.DataFrame(
        [
            {
                "entity_name": "Entity A",
                "entity_code": "EA",
                "voucher_number": "V1",
                "voucher_date": "2024-01-01",
                "summary": "Init",
                "account_code": "1001",
                "account_name": "Cash",
                "debit_amount": 100,
                "credit_amount": 0,
            }
        ]
    )
    data_b = pd.DataFrame(
        [
            {
                "entity_name": "Entity B",
                "entity_code": "EB",
                "voucher_number": "V2",
                "voucher_date": "2024-02-15",
                "summary": "Follow-up",
                "account_code": "2001",
                "account_name": "AP",
                "debit_amount": 0,
                "credit_amount": 200,
            }
        ]
    )

    manager._build_and_store_unified_model({"table_a": data_a}, {}, project_a)
    manager._build_and_store_unified_model({"table_b": data_b}, {}, project_b)

    sanitized_a = manager._sanitize_name(project_a)
    sanitized_b = manager._sanitize_name(project_b)
    expected_bases = [
        "vw_account_year_summary",
        "vw_voucher_with_entries",
        "vw_voucher_with_attachments",
    ]

    with manager.connection_pool.get_connection() as conn:
        entity_counts = dict(
            conn.execute(
                "SELECT project_id, COUNT(*) FROM dim_entities GROUP BY project_id"
            ).fetchall()
        )
        entry_counts = dict(
            conn.execute(
                "SELECT project_id, COUNT(*) FROM fact_entries GROUP BY project_id"
            ).fetchall()
        )

        views = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            ).fetchall()
        }

        meta_pairs = {
            (row[0], row[1])
            for row in conn.execute(
                "SELECT view_name, project_id FROM meta_views"
            ).fetchall()
        }

        for base in expected_bases:
            view_a = f"{base}_{sanitized_a}"
            view_b = f"{base}_{sanitized_b}"
            assert view_a in views
            assert view_b in views
            assert (view_a, project_a) in meta_pairs
            assert (view_b, project_b) in meta_pairs

            project_ids_a = {
                row[0]
                for row in conn.execute(
                    f"SELECT DISTINCT project_id FROM {view_a}"
                ).fetchall()
            }
            project_ids_b = {
                row[0]
                for row in conn.execute(
                    f"SELECT DISTINCT project_id FROM {view_b}"
                ).fetchall()
            }

            if base.endswith("attachments"):
                assert project_ids_a in (set(), {project_a})
                assert project_ids_b in (set(), {project_b})
            else:
                assert project_ids_a == {project_a}
                assert project_ids_b == {project_b}

    assert entity_counts[project_a] == 1
    assert entity_counts[project_b] == 1
    assert entry_counts[project_a] == 1
    assert entry_counts[project_b] == 1


def test_unified_schema_backfills_project_scope(tmp_path):
    db_path = tmp_path / "legacy.db"
    manager = StorageManager(str(db_path))

    with manager.connection_pool.get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS dim_entities")
        conn.execute(
            """
            CREATE TABLE dim_entities (
                entity_id INTEGER PRIMARY KEY,
                entity_code TEXT,
                entity_name TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO dim_entities (entity_code, entity_name) VALUES (?, ?)",
            ("LEGACY", "Legacy Entity"),
        )
        conn.commit()

    manager._ensure_unified_schema()

    with manager.connection_pool.get_connection() as conn:
        info = conn.execute("PRAGMA table_info(dim_entities)").fetchall()
        column_names = {row[1] for row in info}
        assert "project_id" in column_names

        pk_columns = [
            row[1] for row in sorted(info, key=lambda r: r[5] or 0) if row[5]
        ]
        assert pk_columns == ["project_id", "entity_id"]

        rows = conn.execute(
            "SELECT project_id, entity_id, entity_code FROM dim_entities"
        ).fetchall()
        assert rows == [
            (StorageManager.DEFAULT_PROJECT_ID, 1, "LEGACY")
        ]

        indexes = {
            row[1] for row in conn.execute("PRAGMA index_list('dim_entities')").fetchall()
        }
        assert "idx_dim_entities_project_code" in indexes
