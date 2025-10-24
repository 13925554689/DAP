"""Consolidation Engine for generating group-level consolidated financial reports.

This module provides comprehensive consolidation functionality including:
1. Identification of intercompany transactions
2. Generation of elimination entries
3. Consolidation of financial statements
4. Minority interest calculation
5. Consolidation adjustments management
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from layer2.group_hierarchy_manager import GroupHierarchyManager
from layer2.reconciliation_engine import ReconciliationEngine
from layer2.adjustment_manager import AdjustmentManager

logger = logging.getLogger(__name__)


class ConsolidationEngine:
    """Engine for generating consolidated financial reports."""

    def __init__(self, db_path: str):
        """Initialize the consolidation engine.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.hierarchy_manager = GroupHierarchyManager(db_path)
        self.reconciliation_engine = ReconciliationEngine(db_path)
        self.adjustment_manager = AdjustmentManager(db_path)

    def connect(self):
        """Establish database connection."""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.debug(f"Connected to database: {self.db_path}")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def generate_consolidated_report(
        self,
        parent_entity_id: int,
        period: str,
        report_type: str = "balance_sheet",
        include_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate consolidated financial report.

        Args:
            parent_entity_id: Parent entity ID (consolidation root)
            period: Fiscal period (e.g., "2024-12")
            report_type: Type of report (balance_sheet, income_statement, cash_flow)
            include_criteria: Criteria for including entities in consolidation

        Returns:
            Dictionary containing consolidated report data and metadata
        """
        self.connect()
        self.hierarchy_manager.connect()

        logger.info(f"Generating consolidated {report_type} for entity {parent_entity_id}, period {period}")

        # Step 1: Determine consolidation scope
        scope_entity_ids = self.hierarchy_manager.get_consolidation_scope(
            parent_entity_id, include_criteria
        )

        if not scope_entity_ids:
            logger.warning("No entities in consolidation scope")
            return {
                "success": False,
                "error": "No entities in consolidation scope",
                "scope_entity_ids": []
            }

        logger.info(f"Consolidation scope: {len(scope_entity_ids)} entities")

        # Step 2: Perform intelligent reconciliation of intercompany transactions
        reconciliation_result = self.reconciliation_engine.auto_reconcile_transactions(
            entity_ids=scope_entity_ids,
            period=period
        )
        logger.info(f"Reconciliation completed: {reconciliation_result.get('matched_count', 0)} matched, "
                   f"{reconciliation_result.get('auto_adjusted_count', 0)} auto-adjusted")

        # Step 3: Identify intercompany transactions (now with reconciliation status)
        interco_transactions = self._identify_intercompany_transactions(
            scope_entity_ids, period
        )
        logger.info(f"Found {len(interco_transactions)} intercompany transactions")

        # Step 4: Generate elimination entries
        elimination_entries = self._generate_elimination_entries(
            interco_transactions, parent_entity_id, period
        )
        logger.info(f"Generated {len(elimination_entries)} elimination entries")

        # Step 4: Retrieve individual entity financials
        entity_financials = self._get_entity_financials(
            scope_entity_ids, period, report_type
        )

        # Step 5: Perform consolidation
        consolidated_data = self._perform_consolidation(
            entity_financials, elimination_entries, report_type
        )

        # Step 6: Calculate minority interest
        minority_interest = self._calculate_minority_interest(
            scope_entity_ids, entity_financials, parent_entity_id
        )

        # Step 7: Create consolidation metadata
        consolidation_id = self._create_consolidation_metadata(
            parent_entity_id, period, scope_entity_ids,
            consolidated_data, len(elimination_entries)
        )

        return {
            "success": True,
            "consolidation_id": consolidation_id,
            "report_type": report_type,
            "period": period,
            "scope_entity_ids": scope_entity_ids,
            "scope_entity_count": len(scope_entity_ids),
            "interco_transaction_count": len(interco_transactions),
            "elimination_count": len(elimination_entries),
            "minority_interest": minority_interest,
            "consolidated_data": consolidated_data,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "parent_entity_id": parent_entity_id
            }
        }

    def _identify_intercompany_transactions(
        self,
        entity_ids: List[int],
        period: str
    ) -> pd.DataFrame:
        """Identify intercompany transactions within the consolidation scope.

        Args:
            entity_ids: List of entity IDs in scope
            period: Fiscal period

        Returns:
            DataFrame of intercompany transactions
        """
        if not entity_ids:
            return pd.DataFrame()

        placeholders = ",".join(["?"] * len(entity_ids))

        query = f"""
            SELECT *
            FROM intercompany_transactions
            WHERE fiscal_period = ?
              AND seller_entity_id IN ({placeholders})
              AND buyer_entity_id IN ({placeholders})
              AND needs_elimination = 1
              AND elimination_status != '无需抵销'
            ORDER BY transaction_date
        """

        params = [period] + entity_ids + entity_ids

        df = pd.read_sql_query(query, self.conn, params=params)
        return df

    def _generate_elimination_entries(
        self,
        transactions: pd.DataFrame,
        parent_entity_id: int,
        period: str
    ) -> List[Dict[str, Any]]:
        """Generate elimination entries for intercompany transactions.

        Args:
            transactions: DataFrame of intercompany transactions
            parent_entity_id: Parent entity ID
            period: Fiscal period

        Returns:
            List of elimination entry dictionaries
        """
        entries = []

        for _, txn in transactions.iterrows():
            txn_type = txn["transaction_type"]
            amount = txn["transaction_amount_cny"] or txn["transaction_amount"]

            if txn_type == "销售商品":
                # Eliminate internal revenue and cost of goods sold
                entries.extend(self._eliminate_goods_sale(txn, amount, parent_entity_id, period))

            elif txn_type == "提供服务":
                # Eliminate internal service revenue
                entries.extend(self._eliminate_service_revenue(txn, amount, parent_entity_id, period))

            elif txn_type == "借款":
                # Eliminate internal debt
                entries.extend(self._eliminate_internal_debt(txn, amount, parent_entity_id, period))

            elif txn_type == "资产转让":
                # Eliminate unrealized gains on asset transfers
                entries.extend(self._eliminate_asset_transfer(txn, amount, parent_entity_id, period))

        # Save elimination entries to database
        self._save_elimination_entries(entries)

        return entries

    def _eliminate_goods_sale(
        self,
        txn: pd.Series,
        amount: float,
        parent_id: int,
        period: str
    ) -> List[Dict[str, Any]]:
        """Generate elimination entries for goods sale."""
        entries = []

        # Basic elimination: DR Revenue, CR Cost of Goods Sold
        entries.append({
            "consolidation_period": period,
            "parent_entity_id": parent_id,
            "adjustment_type": "内部交易抵销",
            "adjustment_category": "本期调整",
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "debit_account_code": "6001",  # Operating Revenue
            "debit_account_name": "主营业务收入",
            "credit_account_code": "6401",  # Cost of Goods Sold
            "credit_account_name": "主营业务成本",
            "amount": amount,
            "related_transaction_id": int(txn["transaction_id"]),
            "notes": f"抵销内部销售: {txn.get('voucher_number', 'N/A')}"
        })

        # If there's unrealized profit
        if txn.get("has_unrealized_profit") and txn.get("unrealized_profit_amount", 0) > 0:
            unrealized = txn["unrealized_profit_amount"]
            entries.append({
                "consolidation_period": period,
                "parent_entity_id": parent_id,
                "adjustment_type": "未实现利润抵销",
                "adjustment_category": "本期调整",
                "entry_date": datetime.now().strftime("%Y-%m-%d"),
                "debit_account_code": "6401",
                "debit_account_name": "主营业务成本",
                "credit_account_code": "1405",  # Inventory
                "credit_account_name": "存货",
                "amount": unrealized,
                "related_transaction_id": int(txn["transaction_id"]),
                "notes": f"抵销未实现内部利润: {unrealized}"
            })

        return entries

    def _eliminate_service_revenue(
        self,
        txn: pd.Series,
        amount: float,
        parent_id: int,
        period: str
    ) -> List[Dict[str, Any]]:
        """Generate elimination entries for service revenue."""
        return [{
            "consolidation_period": period,
            "parent_entity_id": parent_id,
            "adjustment_type": "内部交易抵销",
            "adjustment_category": "本期调整",
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "debit_account_code": "6001",
            "debit_account_name": "主营业务收入",
            "credit_account_code": "6402",  # Operating Expenses
            "credit_account_name": "管理费用",
            "amount": amount,
            "related_transaction_id": int(txn["transaction_id"]),
            "notes": f"抵销内部服务收入: {txn.get('voucher_number', 'N/A')}"
        }]

    def _eliminate_internal_debt(
        self,
        txn: pd.Series,
        amount: float,
        parent_id: int,
        period: str
    ) -> List[Dict[str, Any]]:
        """Generate elimination entries for internal debt."""
        return [{
            "consolidation_period": period,
            "parent_entity_id": parent_id,
            "adjustment_type": "内部债权债务抵销",
            "adjustment_category": "本期调整",
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "debit_account_code": "2203",  # Short-term Borrowings
            "debit_account_name": "短期借款",
            "credit_account_code": "1122",  # Other Receivables
            "credit_account_name": "其他应收款",
            "amount": amount,
            "related_transaction_id": int(txn["transaction_id"]),
            "notes": f"抵销内部债权债务: {txn.get('voucher_number', 'N/A')}"
        }]

    def _eliminate_asset_transfer(
        self,
        txn: pd.Series,
        amount: float,
        parent_id: int,
        period: str
    ) -> List[Dict[str, Any]]:
        """Generate elimination entries for asset transfer."""
        unrealized_gain = txn.get("unrealized_profit_amount", 0)

        if unrealized_gain <= 0:
            return []

        return [{
            "consolidation_period": period,
            "parent_entity_id": parent_id,
            "adjustment_type": "未实现利润抵销",
            "adjustment_category": "本期调整",
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "debit_account_code": "6051",  # Non-operating Income
            "debit_account_name": "营业外收入",
            "credit_account_code": "1601",  # Fixed Assets
            "credit_account_name": "固定资产",
            "amount": unrealized_gain,
            "related_transaction_id": int(txn["transaction_id"]),
            "notes": f"抵销资产转让未实现利润: {unrealized_gain}"
        }]

    def _save_elimination_entries(self, entries: List[Dict[str, Any]]):
        """Save elimination entries to database."""
        if not entries:
            return

        for entry in entries:
            self.conn.execute("""
                INSERT INTO consolidation_adjustments (
                    consolidation_period, parent_entity_id, adjustment_type,
                    adjustment_category, entry_date,
                    debit_account_code, debit_account_name,
                    credit_account_code, credit_account_name,
                    amount, related_transaction_id, notes, is_applied
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["consolidation_period"], entry["parent_entity_id"],
                entry["adjustment_type"], entry["adjustment_category"],
                entry["entry_date"],
                entry["debit_account_code"], entry["debit_account_name"],
                entry["credit_account_code"], entry["credit_account_name"],
                entry["amount"], entry.get("related_transaction_id"),
                entry.get("notes"), 1
            ))

        self.conn.commit()
        logger.info(f"Saved {len(entries)} elimination entries")

    def _get_entity_financials(
        self,
        entity_ids: List[int],
        period: str,
        report_type: str
    ) -> Dict[int, pd.DataFrame]:
        """Retrieve financial data for each entity.

        Args:
            entity_ids: List of entity IDs
            period: Fiscal period
            report_type: Type of report

        Returns:
            Dictionary mapping entity_id to financial DataFrame
        """
        financials = {}

        # This is a simplified implementation
        # In production, you would query actual financial data tables

        for entity_id in entity_ids:
            # Query account balances or trial balance for the entity
            query = """
                SELECT account_code, account_name, SUM(debit_amount) as debit,
                       SUM(credit_amount) as credit
                FROM voucher_details vd
                JOIN vouchers v ON vd.voucher_id = v.voucher_id
                WHERE v.entity_id = ? AND v.fiscal_period = ?
                GROUP BY account_code, account_name
            """

            try:
                df = pd.read_sql_query(query, self.conn, params=(entity_id, period))
                financials[entity_id] = df
            except Exception as e:
                logger.warning(f"Could not retrieve financials for entity {entity_id}: {e}")
                financials[entity_id] = pd.DataFrame()

        return financials

    def _perform_consolidation(
        self,
        entity_financials: Dict[int, pd.DataFrame],
        elimination_entries: List[Dict[str, Any]],
        report_type: str
    ) -> pd.DataFrame:
        """Perform the actual consolidation of financial data.

        Args:
            entity_financials: Financial data by entity
            elimination_entries: Elimination adjustments
            report_type: Type of report

        Returns:
            Consolidated financial DataFrame
        """
        if not entity_financials:
            return pd.DataFrame()

        # Step 1: Aggregate all entity financials
        all_data = []
        for entity_id, df in entity_financials.items():
            if not df.empty:
                df_copy = df.copy()
                df_copy["entity_id"] = entity_id
                all_data.append(df_copy)

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)

        # Step 2: Group by account and sum
        consolidated = combined.groupby(["account_code", "account_name"]).agg({
            "debit": "sum",
            "credit": "sum"
        }).reset_index()

        # Step 3: Apply elimination entries
        for entry in elimination_entries:
            # Debit adjustment
            debit_mask = consolidated["account_code"] == entry["debit_account_code"]
            if debit_mask.any():
                consolidated.loc[debit_mask, "debit"] += entry["amount"]
            else:
                # Add new row
                new_row = {
                    "account_code": entry["debit_account_code"],
                    "account_name": entry["debit_account_name"],
                    "debit": entry["amount"],
                    "credit": 0
                }
                consolidated = pd.concat([consolidated, pd.DataFrame([new_row])], ignore_index=True)

            # Credit adjustment
            credit_mask = consolidated["account_code"] == entry["credit_account_code"]
            if credit_mask.any():
                consolidated.loc[credit_mask, "credit"] += entry["amount"]
            else:
                # Add new row
                new_row = {
                    "account_code": entry["credit_account_code"],
                    "account_name": entry["credit_account_name"],
                    "debit": 0,
                    "credit": entry["amount"]
                }
                consolidated = pd.concat([consolidated, pd.DataFrame([new_row])], ignore_index=True)

        # Step 4: Calculate final balances
        consolidated["balance"] = consolidated["debit"] - consolidated["credit"]

        # Step 5: Re-group in case we added duplicate accounts
        consolidated = consolidated.groupby(["account_code", "account_name"]).agg({
            "debit": "sum",
            "credit": "sum",
            "balance": "sum"
        }).reset_index()

        consolidated = consolidated.sort_values("account_code")

        logger.info(f"Consolidated {len(consolidated)} accounts")
        return consolidated

    def _calculate_minority_interest(
        self,
        entity_ids: List[int],
        entity_financials: Dict[int, pd.DataFrame],
        parent_id: int
    ) -> Dict[str, Any]:
        """Calculate minority interest for partially-owned subsidiaries.

        Args:
            entity_ids: List of entity IDs in scope
            entity_financials: Financial data by entity
            parent_id: Parent entity ID

        Returns:
            Dictionary with minority interest calculations
        """
        minority_interest = {
            "total_amount": 0.0,
            "by_entity": {}
        }

        for entity_id in entity_ids:
            if entity_id == parent_id:
                continue

            entity = self.hierarchy_manager.get_entity(entity_id)
            if not entity:
                continue

            # Calculate minority percentage
            effective_ownership = entity.get("effective_ownership", 100.0)
            minority_pct = 100.0 - effective_ownership

            if minority_pct <= 0:
                continue

            # Get entity's equity (simplified - would need actual equity calculation)
            equity = 0.0
            if entity_id in entity_financials:
                df = entity_financials[entity_id]
                # Sum equity accounts (3xxx accounts typically)
                equity_mask = df["account_code"].str.startswith("3")
                equity = df[equity_mask]["balance"].sum() if equity_mask.any() else 0.0

            minority_amount = equity * (minority_pct / 100.0)

            minority_interest["by_entity"][entity_id] = {
                "entity_name": entity["entity_name"],
                "minority_percentage": minority_pct,
                "equity": equity,
                "minority_amount": minority_amount
            }

            minority_interest["total_amount"] += minority_amount

        logger.info(f"Total minority interest: {minority_interest['total_amount']}")
        return minority_interest

    def _create_consolidation_metadata(
        self,
        parent_entity_id: int,
        period: str,
        scope_entity_ids: List[int],
        consolidated_data: pd.DataFrame,
        elimination_count: int
    ) -> int:
        """Create consolidation metadata record.

        Args:
            parent_entity_id: Parent entity ID
            period: Fiscal period
            scope_entity_ids: List of entity IDs in scope
            consolidated_data: Consolidated financial data
            elimination_count: Number of elimination entries

        Returns:
            Consolidation ID
        """
        # Calculate summary figures
        total_assets = consolidated_data[
            consolidated_data["account_code"].str.startswith("1")
        ]["balance"].sum() if not consolidated_data.empty else 0

        total_liabilities = consolidated_data[
            consolidated_data["account_code"].str.startswith("2")
        ]["balance"].sum() if not consolidated_data.empty else 0

        total_equity = consolidated_data[
            consolidated_data["account_code"].str.startswith("3")
        ]["balance"].sum() if not consolidated_data.empty else 0

        cursor = self.conn.execute("""
            INSERT INTO consolidation_metadata (
                parent_entity_id, consolidation_period, consolidation_date,
                scope_entity_ids, scope_entity_count, consolidation_method,
                total_assets, total_liabilities, total_equity,
                elimination_count, status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            parent_entity_id, period, datetime.now().strftime("%Y-%m-%d"),
            ",".join(map(str, scope_entity_ids)), len(scope_entity_ids),
            "全额合并",
            total_assets, total_liabilities, total_equity,
            elimination_count, "已完成", "system"
        ))

        consolidation_id = cursor.lastrowid
        self.conn.commit()

        logger.info(f"Created consolidation metadata: ID {consolidation_id}")
        return consolidation_id


if __name__ == "__main__":
    # Test consolidation engine
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/dap.db"

    print(f"\n{'='*60}")
    print(f"Consolidation Engine Test")
    print(f"{'='*60}\n")

    with ConsolidationEngine(db_path) as engine:
        print("Consolidation Engine initialized successfully")
        print(f"Database: {db_path}")
