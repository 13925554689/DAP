import os
import sys
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(ROOT, "..")))

from layer1.storage_manager import StorageManager


def main() -> None:
    db_path = os.path.join("data", "test_regression.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    storage = StorageManager(db_path)

    project_id = storage.create_project(
        project_name="示例集团账套",
        project_code="DEMO-001",
        client_name="示例集团",
        fiscal_year="2023",
        created_by="regression_demo",
    )
    storage.set_current_project(project_id)

    ledger_df = pd.DataFrame(
        {
            "公司名称": ["示例科技股份有限公司"] * 3,
            "年份": ["2023", "2023", "2023"],
            "期间": ["01", "02", "02"],
            "凭证号": ["0001", "0002", "0002"],
            "凭证日期": ["2023-01-15", "2023-02-10", "2023-02-10"],
            "摘要": ["采购原料", "主营业务收入", "主营业务成本"],
            "科目编码": ["1405", "6001", "6401"],
            "科目名称": ["原材料", "主营业务收入", "主营业务成本"],
            "借方金额": [50000, 0, 40000],
            "贷方金额": [0, 80000, 0],
            "附件路径": ["docs/invoice.pdf", "docs/sales.pdf", "docs/cost.pdf"],
        }
    )

    cleaned_payload = {"general_ledger": ledger_df}

    schema = {
        "tables": {
            "general_ledger": {
                "business_meaning": {
                    "entity_name": "示例科技股份有限公司",
                    "entity_code": "DEMO-HX001",
                    "table_type": "ledger",
                },
                "columns": {},
            }
        }
    }

    storage.store_cleaned_data(cleaned_payload, schema)

    entities = storage.list_entities_summary()
    print("Entity Summary:", entities)

    entity_id = entities[0]["entity_id"]
    years = storage.list_years_for_entity(entity_id)
    print("Year Summary:", years)

    fiscal_year = years[0]["fiscal_year"]
    accounts = storage.list_accounts_for_entity_year(entity_id, fiscal_year)
    print("Accounts:", accounts)

    account_id = accounts[0]["account_id"]
    vouchers = storage.list_vouchers_for_account(entity_id, fiscal_year, account_id)
    print("Vouchers:", vouchers)

    voucher_id = vouchers["rows"][0]["voucher_id"]
    entries = storage.get_voucher_entries_paginated(voucher_id)
    print("Voucher Entries:", entries)

    attachments = storage.get_voucher_attachments(voucher_id)
    print("Attachments:", attachments)

    view_suffix = storage._sanitize_name(project_id)  # noqa: SLF001 - demo script
    unified_view = f"vw_voucher_with_entries_{view_suffix}"

    with storage.connection_pool.get_connection() as conn:
        unified_rows = pd.read_sql_query(
            f"""
            SELECT project_id, voucher_number, account_code, debit_amount, credit_amount
            FROM {unified_view}
            ORDER BY voucher_number, line_number
            """,
            conn,
        ).to_dict(orient="records")
        meta_view_entries = conn.execute(
            "SELECT view_name, project_id FROM meta_views WHERE project_id = ?",
            (project_id,),
        ).fetchall()

    print("Unified View Rows:", unified_rows)
    print("Meta View Records:", meta_view_entries)


if __name__ == "__main__":
    main()
