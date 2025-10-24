"""Adjustment Manager for handling various data adjustments.

This module provides comprehensive adjustment management including:
1. Single entity adjustments
2. Fair value adjustments
3. Consolidation adjustments
4. Adjustment trail tracking
5. Before/after comparison
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class AdjustmentManager:
    """Manager for handling all types of data adjustments."""

    def __init__(self, db_path: str):
        """Initialize adjustment manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

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

    def create_adjustment(
        self,
        adjustment_type: str,
        entity_id: int,
        period: str,
        entries: List[Dict[str, Any]],
        value_dimension: str = 'actual',
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> int:
        """Create adjustment entries with full audit trail.

        Args:
            adjustment_type: Type of adjustment (单体调整/公允价值调整/合并调整/初始化调整)
            entity_id: Entity ID
            period: Fiscal period
            entries: List of adjustment entries
            value_dimension: Value dimension (actual/budget/forecast/adjusted)
            description: Adjustment description
            created_by: User who created the adjustment

        Returns:
            Adjustment ID

        Example entry:
        {
            'debit_account': '1001',
            'debit_account_name': '库存现金',
            'credit_account': '1002',
            'credit_account_name': '银行存款',
            'amount': 10000.00,
            'description': '调整现金余额'
        }
        """
        self.connect()

        logger.info(f"Creating {adjustment_type} for entity {entity_id}, period {period}")
        logger.info(f"Number of entries: {len(entries)}")

        # Create main adjustment record
        cursor = self.conn.execute("""
            INSERT INTO consolidation_adjustments (
                consolidation_period, parent_entity_id, adjustment_type,
                adjustment_category, entry_date,
                debit_account_code, credit_account_code, amount,
                notes, created_by, is_applied
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            period,
            entity_id,
            adjustment_type,
            '本期调整',
            datetime.now().strftime("%Y-%m-%d"),
            entries[0].get('debit_account', ''),
            entries[0].get('credit_account', ''),
            sum(e.get('amount', 0) for e in entries),
            description or f"{adjustment_type} - {len(entries)}笔分录",
            created_by,
            0  # Not yet applied
        ))

        adjustment_id = cursor.lastrowid

        # Create detailed history records for each entry
        for entry in entries:
            self.conn.execute("""
                INSERT INTO adjustment_history (
                    adjustment_id, adjustment_type, entity_id, period,
                    debit_account, debit_account_name,
                    credit_account, credit_account_name,
                    amount, description, created_by, value_dimension
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                adjustment_id,
                adjustment_type,
                entity_id,
                period,
                entry.get('debit_account'),
                entry.get('debit_account_name'),
                entry.get('credit_account'),
                entry.get('credit_account_name'),
                entry.get('amount'),
                entry.get('description'),
                created_by,
                value_dimension
            ))

        self.conn.commit()

        logger.info(f"Created adjustment {adjustment_id} with {len(entries)} entries")
        return adjustment_id

    def single_entity_adjustment(
        self,
        entity_id: int,
        period: str,
        entries: List[Dict[str, Any]],
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> int:
        """Create single entity adjustment (audit adjustment).

        Args:
            entity_id: Entity ID
            period: Fiscal period
            entries: List of adjustment entries
            description: Adjustment description
            created_by: User who created the adjustment

        Returns:
            Adjustment ID
        """
        return self.create_adjustment(
            adjustment_type='单体调整',
            entity_id=entity_id,
            period=period,
            entries=entries,
            value_dimension='audit_adjusted',
            description=description or '单体审计调整',
            created_by=created_by
        )

    def fair_value_adjustment(
        self,
        entity_id: int,
        period: str,
        asset_account: str,
        asset_name: str,
        fair_value_change: float,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> int:
        """Create fair value adjustment.

        Args:
            entity_id: Entity ID
            period: Fiscal period
            asset_account: Asset account code
            asset_name: Asset account name
            fair_value_change: Fair value change amount (positive = increase)
            description: Adjustment description
            created_by: User who created the adjustment

        Returns:
            Adjustment ID
        """
        if fair_value_change > 0:
            # Increase: DR Asset, CR Gain
            entries = [{
                'debit_account': asset_account,
                'debit_account_name': asset_name,
                'credit_account': '6051',
                'credit_account_name': '公允价值变动损益',
                'amount': abs(fair_value_change),
                'description': f'{asset_name}公允价值上升'
            }]
        else:
            # Decrease: DR Loss, CR Asset
            entries = [{
                'debit_account': '6051',
                'debit_account_name': '公允价值变动损益',
                'credit_account': asset_account,
                'credit_account_name': asset_name,
                'amount': abs(fair_value_change),
                'description': f'{asset_name}公允价值下降'
            }]

        return self.create_adjustment(
            adjustment_type='公允价值调整',
            entity_id=entity_id,
            period=period,
            entries=entries,
            value_dimension='fair_value',
            description=description or f'{asset_name}公允价值调整',
            created_by=created_by
        )

    def consolidation_adjustment(
        self,
        parent_entity_id: int,
        period: str,
        entries: List[Dict[str, Any]],
        related_transaction_id: Optional[int] = None,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> int:
        """Create consolidation adjustment.

        Args:
            parent_entity_id: Parent entity ID
            period: Fiscal period
            entries: List of adjustment entries
            related_transaction_id: Related intercompany transaction ID
            description: Adjustment description
            created_by: User who created the adjustment

        Returns:
            Adjustment ID
        """
        # Create main adjustment
        adjustment_id = self.create_adjustment(
            adjustment_type='合并调整',
            entity_id=parent_entity_id,
            period=period,
            entries=entries,
            value_dimension='consolidated',
            description=description or '合并报表调整',
            created_by=created_by
        )

        # Link to related transaction if provided
        if related_transaction_id:
            self.conn.execute("""
                UPDATE consolidation_adjustments
                SET related_transaction_id = ?
                WHERE adjustment_id = ?
            """, (related_transaction_id, adjustment_id))
            self.conn.commit()

        return adjustment_id

    def get_adjustment_trail(
        self,
        adjustment_id: int
    ) -> List[Dict[str, Any]]:
        """Get complete adjustment trail with all history.

        Args:
            adjustment_id: Adjustment ID

        Returns:
            List of adjustment history records
        """
        self.connect()

        query = """
            SELECT
                h.*,
                a.adjustment_category,
                a.is_applied,
                a.created_at as adjustment_created_at
            FROM adjustment_history h
            JOIN consolidation_adjustments a ON h.adjustment_id = a.adjustment_id
            WHERE h.adjustment_id = ?
            ORDER BY h.history_id
        """

        rows = self.conn.execute(query, (adjustment_id,)).fetchall()
        return [dict(row) for row in rows]

    def compare_before_after(
        self,
        entity_id: int,
        period: str,
        adjustment_id: int
    ) -> Dict[str, Any]:
        """Compare data before and after adjustment.

        Args:
            entity_id: Entity ID
            period: Fiscal period
            adjustment_id: Adjustment ID

        Returns:
            Dictionary with before/after comparison
        """
        self.connect()

        # Get adjustment entries
        trail = self.get_adjustment_trail(adjustment_id)

        if not trail:
            return {
                'success': False,
                'error': 'Adjustment not found'
            }

        # Get affected accounts
        affected_accounts = set()
        for entry in trail:
            if entry.get('debit_account'):
                affected_accounts.add(entry['debit_account'])
            if entry.get('credit_account'):
                affected_accounts.add(entry['credit_account'])

        # For each affected account, get balance before and after
        comparisons = []

        for account in affected_accounts:
            # This is simplified - in production would query actual account balances
            # from voucher_details or trial_balance tables

            comparison = {
                'account_code': account,
                'account_name': None,  # Would be looked up
                'before_debit': 0.0,
                'before_credit': 0.0,
                'before_balance': 0.0,
                'adjustment_debit': 0.0,
                'adjustment_credit': 0.0,
                'after_debit': 0.0,
                'after_credit': 0.0,
                'after_balance': 0.0
            }

            # Calculate adjustment amounts for this account
            for entry in trail:
                if entry.get('debit_account') == account:
                    comparison['adjustment_debit'] += entry.get('amount', 0)
                    comparison['account_name'] = entry.get('debit_account_name')
                if entry.get('credit_account') == account:
                    comparison['adjustment_credit'] += entry.get('amount', 0)
                    comparison['account_name'] = entry.get('credit_account_name')

            # Calculate after amounts
            comparison['after_debit'] = comparison['before_debit'] + comparison['adjustment_debit']
            comparison['after_credit'] = comparison['before_credit'] + comparison['adjustment_credit']
            comparison['after_balance'] = comparison['before_balance'] + \
                                         comparison['adjustment_debit'] - comparison['adjustment_credit']

            comparisons.append(comparison)

        return {
            'success': True,
            'adjustment_id': adjustment_id,
            'entity_id': entity_id,
            'period': period,
            'adjustment_type': trail[0]['adjustment_type'] if trail else None,
            'total_entries': len(trail),
            'affected_accounts': len(comparisons),
            'comparisons': comparisons
        }

    def apply_adjustment(
        self,
        adjustment_id: int,
        applied_by: Optional[str] = None
    ) -> bool:
        """Apply (post) adjustment to accounts.

        Args:
            adjustment_id: Adjustment ID
            applied_by: User who applied the adjustment

        Returns:
            True if successful
        """
        self.connect()

        try:
            self.conn.execute("""
                UPDATE consolidation_adjustments
                SET is_applied = 1,
                    approved_by = ?,
                    approved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE adjustment_id = ?
            """, (applied_by, adjustment_id))

            self.conn.commit()

            logger.info(f"Applied adjustment {adjustment_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply adjustment {adjustment_id}: {e}")
            self.conn.rollback()
            return False

    def reverse_adjustment(
        self,
        adjustment_id: int,
        reversed_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> int:
        """Reverse an adjustment by creating opposite entries.

        Args:
            adjustment_id: Adjustment ID to reverse
            reversed_by: User who reversed the adjustment
            reason: Reason for reversal

        Returns:
            New adjustment ID for reversal entries
        """
        self.connect()

        # Get original adjustment trail
        original_trail = self.get_adjustment_trail(adjustment_id)

        if not original_trail:
            raise ValueError(f"Adjustment {adjustment_id} not found")

        # Create reversal entries (swap debit/credit)
        reversal_entries = []
        for entry in original_trail:
            reversal_entries.append({
                'debit_account': entry['credit_account'],
                'debit_account_name': entry['credit_account_name'],
                'credit_account': entry['debit_account'],
                'credit_account_name': entry['debit_account_name'],
                'amount': entry['amount'],
                'description': f"冲销: {entry.get('description', '')}"
            })

        # Create reversal adjustment
        reversal_id = self.create_adjustment(
            adjustment_type=original_trail[0]['adjustment_type'],
            entity_id=original_trail[0]['entity_id'],
            period=original_trail[0]['period'],
            entries=reversal_entries,
            value_dimension=original_trail[0]['value_dimension'],
            description=f"冲销调整{adjustment_id}: {reason or ''}",
            created_by=reversed_by
        )

        # Mark original as reversed
        self.conn.execute("""
            UPDATE adjustment_history
            SET is_reversed = 1, reversed_by_id = ?
            WHERE adjustment_id = ?
        """, (reversal_id, adjustment_id))

        self.conn.commit()

        logger.info(f"Reversed adjustment {adjustment_id} with reversal {reversal_id}")
        return reversal_id

    def list_adjustments(
        self,
        entity_id: Optional[int] = None,
        period: Optional[str] = None,
        adjustment_type: Optional[str] = None,
        is_applied: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List adjustments with optional filters.

        Args:
            entity_id: Filter by entity ID
            period: Filter by period
            adjustment_type: Filter by adjustment type
            is_applied: Filter by applied status

        Returns:
            List of adjustment summary records
        """
        self.connect()

        query = """
            SELECT
                a.adjustment_id,
                a.adjustment_type,
                a.consolidation_period as period,
                a.parent_entity_id as entity_id,
                a.entry_date,
                a.amount,
                a.is_applied,
                a.created_by,
                a.created_at,
                a.notes,
                COUNT(h.history_id) as entry_count
            FROM consolidation_adjustments a
            LEFT JOIN adjustment_history h ON a.adjustment_id = h.adjustment_id
            WHERE 1=1
        """
        params = []

        if entity_id is not None:
            query += " AND a.parent_entity_id = ?"
            params.append(entity_id)

        if period:
            query += " AND a.consolidation_period = ?"
            params.append(period)

        if adjustment_type:
            query += " AND a.adjustment_type = ?"
            params.append(adjustment_type)

        if is_applied is not None:
            query += " AND a.is_applied = ?"
            params.append(1 if is_applied else 0)

        query += " GROUP BY a.adjustment_id ORDER BY a.created_at DESC"

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_adjustment_summary(
        self,
        entity_id: int,
        period: str
    ) -> Dict[str, Any]:
        """Get adjustment summary statistics.

        Args:
            entity_id: Entity ID
            period: Fiscal period

        Returns:
            Summary statistics dictionary
        """
        self.connect()

        query = """
            SELECT
                adjustment_type,
                COUNT(*) as count,
                SUM(amount) as total_amount,
                SUM(CASE WHEN is_applied = 1 THEN 1 ELSE 0 END) as applied_count
            FROM consolidation_adjustments
            WHERE parent_entity_id = ? AND consolidation_period = ?
            GROUP BY adjustment_type
        """

        rows = self.conn.execute(query, (entity_id, period)).fetchall()

        summary = {
            'entity_id': entity_id,
            'period': period,
            'by_type': {},
            'total_adjustments': 0,
            'total_amount': 0.0,
            'total_applied': 0
        }

        for row in rows:
            adj_type = row['adjustment_type']
            summary['by_type'][adj_type] = {
                'count': row['count'],
                'total_amount': row['total_amount'],
                'applied_count': row['applied_count']
            }
            summary['total_adjustments'] += row['count']
            summary['total_amount'] += row['total_amount']
            summary['total_applied'] += row['applied_count']

        return summary


if __name__ == "__main__":
    # Test adjustment manager
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/dap.db"

    print(f"\n{'='*60}")
    print(f"Adjustment Manager Test")
    print(f"{'='*60}\n")

    with AdjustmentManager(db_path) as manager:
        print("Adjustment Manager initialized successfully")
        print(f"Database: {db_path}")
