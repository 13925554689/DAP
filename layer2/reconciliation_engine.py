"""Intelligent Reconciliation Engine for intercompany transactions.

This module provides advanced reconciliation capabilities including:
1. Automatic transaction matching
2. Tolerance-based difference handling
3. Reconciliation report generation
4. Scenario-based reconciliation rules
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class ReconciliationEngine:
    """Intelligent engine for reconciling intercompany transactions."""

    def __init__(self, db_path: str):
        """Initialize reconciliation engine.

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

    def auto_reconcile_transactions(
        self,
        entity_ids: List[int],
        period: str,
        scenario: Optional[str] = None
    ) -> Dict[str, Any]:
        """Automatically reconcile intercompany transactions.

        Args:
            entity_ids: List of entity IDs in scope
            period: Fiscal period
            scenario: Optional transaction scenario type

        Returns:
            Dictionary with reconciliation results:
            {
                'matched_count': int,
                'unmatched_count': int,
                'auto_adjusted': int,
                'tolerance_exceeded': int,
                'total_matched_amount': float,
                'total_difference_amount': float,
                'details': List[Dict],
                'report': str
            }
        """
        self.connect()

        logger.info(f"Starting auto-reconciliation for {len(entity_ids)} entities, period {period}")

        # 1. Get reconciliation rules
        rules = self._get_reconciliation_rules(scenario)
        logger.info(f"Loaded {len(rules)} reconciliation rules")

        # 2. Get unreconciled transactions
        transactions = self._get_unreconciled_transactions(entity_ids, period, scenario)
        logger.info(f"Found {len(transactions)} unreconciled transactions")

        if transactions.empty:
            return {
                'matched_count': 0,
                'unmatched_count': 0,
                'auto_adjusted': 0,
                'tolerance_exceeded': 0,
                'total_matched_amount': 0.0,
                'total_difference_amount': 0.0,
                'details': [],
                'report': 'No transactions to reconcile'
            }

        # 3. Match transactions
        matches = self._match_transactions(transactions, rules)
        logger.info(f"Matched {len(matches)} transaction pairs")

        # 4. Process differences
        adjustments = self._process_differences(matches, rules)
        logger.info(f"Generated {len(adjustments)} adjustments")

        # 5. Update database
        self._update_reconciliation_status(matches, adjustments)

        # 6. Generate report
        report = self._generate_reconciliation_report(matches, adjustments, transactions)

        self.conn.commit()

        return report

    def _get_reconciliation_rules(
        self,
        scenario: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get reconciliation rules from database.

        Args:
            scenario: Optional transaction scenario type

        Returns:
            List of reconciliation rule dictionaries
        """
        query = """
            SELECT * FROM reconciliation_rules
            WHERE is_active = 1
        """
        params = []

        if scenario:
            query += " AND scenario_type = ?"
            params.append(scenario)

        query += " ORDER BY rule_id"

        try:
            df = pd.read_sql_query(query, self.conn, params=params)
            return df.to_dict('records')
        except Exception as e:
            logger.warning(f"Could not load reconciliation rules: {e}")
            # Return default rules
            return [{
                'scenario_type': 'default',
                'tolerance_days': 3,
                'tolerance_amount': 100.0,
                'auto_adjust': 1,
                'matching_fields': '["transaction_type", "currency"]'
            }]

    def _get_unreconciled_transactions(
        self,
        entity_ids: List[int],
        period: str,
        scenario: Optional[str] = None
    ) -> pd.DataFrame:
        """Get unreconciled transactions.

        Args:
            entity_ids: List of entity IDs
            period: Fiscal period
            scenario: Optional transaction scenario

        Returns:
            DataFrame of unreconciled transactions
        """
        if not entity_ids:
            return pd.DataFrame()

        placeholders = ",".join(["?"] * len(entity_ids))

        query = f"""
            SELECT *
            FROM intercompany_transactions
            WHERE fiscal_period = ?
              AND (seller_entity_id IN ({placeholders}) OR buyer_entity_id IN ({placeholders}))
              AND (reconciliation_status IS NULL OR reconciliation_status = '未对账')
              AND needs_elimination = 1
        """

        params = [period] + entity_ids + entity_ids

        if scenario:
            query += " AND transaction_type = ?"
            params.append(scenario)

        query += " ORDER BY transaction_date, transaction_amount DESC"

        try:
            df = pd.read_sql_query(query, self.conn, params=params)
            return df
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            return pd.DataFrame()

    def _match_transactions(
        self,
        transactions: pd.DataFrame,
        rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Match transactions based on rules.

        Args:
            transactions: DataFrame of transactions
            rules: List of reconciliation rules

        Returns:
            List of matched transaction pairs with differences
        """
        matches = []

        # Get default rule
        default_rule = rules[0] if rules else {
            'tolerance_days': 3,
            'tolerance_amount': 100.0
        }

        # Separate seller and buyer transactions
        seller_txns = transactions[transactions['seller_entity_id'].notna()].copy()
        buyer_txns = transactions[transactions['buyer_entity_id'].notna()].copy()

        logger.info(f"Matching {len(seller_txns)} seller vs {len(buyer_txns)} buyer transactions")

        # Try to match each seller transaction
        for _, seller in seller_txns.iterrows():
            best_match = None
            best_score = 0

            for _, buyer in buyer_txns.iterrows():
                # Skip if already matched
                if buyer.get('_matched'):
                    continue

                # Check if counterparties match
                if seller['buyer_entity_id'] != buyer['seller_entity_id']:
                    continue
                if seller['seller_entity_id'] != buyer['buyer_entity_id']:
                    continue

                # Calculate match score
                score = self._calculate_match_score(seller, buyer, default_rule)

                if score > best_score and score >= 0.5:  # Minimum 50% match
                    best_match = buyer
                    best_score = score

            if best_match is not None:
                # Mark as matched
                buyer_txns.loc[best_match.name, '_matched'] = True

                # Calculate differences
                time_diff = abs((pd.to_datetime(seller['transaction_date']) -
                               pd.to_datetime(best_match['transaction_date'])).days)
                amount_diff = abs(seller['transaction_amount_cny'] -
                                best_match['transaction_amount_cny'])

                matches.append({
                    'seller_txn_id': int(seller['transaction_id']),
                    'buyer_txn_id': int(best_match['transaction_id']),
                    'seller_entity': int(seller['seller_entity_id']),
                    'buyer_entity': int(seller['buyer_entity_id']),
                    'transaction_type': seller['transaction_type'],
                    'seller_amount': float(seller['transaction_amount_cny']),
                    'buyer_amount': float(best_match['transaction_amount_cny']),
                    'amount_difference': float(amount_diff),
                    'time_difference_days': int(time_diff),
                    'match_score': float(best_score),
                    'seller_date': str(seller['transaction_date']),
                    'buyer_date': str(best_match['transaction_date'])
                })

        return matches

    def _calculate_match_score(
        self,
        txn1: pd.Series,
        txn2: pd.Series,
        rule: Dict[str, Any]
    ) -> float:
        """Calculate match score between two transactions.

        Args:
            txn1: First transaction
            txn2: Second transaction
            rule: Reconciliation rule

        Returns:
            Match score between 0 and 1
        """
        score = 0.0
        weights = {
            'amount': 0.5,
            'date': 0.2,
            'type': 0.2,
            'currency': 0.1
        }

        # Amount similarity
        amount1 = txn1.get('transaction_amount_cny', 0)
        amount2 = txn2.get('transaction_amount_cny', 0)
        if amount1 and amount2:
            amount_diff = abs(amount1 - amount2)
            amount_tolerance = rule.get('tolerance_amount', 100.0)
            if amount_diff == 0:
                score += weights['amount']
            elif amount_diff <= amount_tolerance:
                score += weights['amount'] * (1 - amount_diff / amount_tolerance)

        # Date similarity
        try:
            date1 = pd.to_datetime(txn1['transaction_date'])
            date2 = pd.to_datetime(txn2['transaction_date'])
            date_diff = abs((date1 - date2).days)
            date_tolerance = rule.get('tolerance_days', 3)
            if date_diff == 0:
                score += weights['date']
            elif date_diff <= date_tolerance:
                score += weights['date'] * (1 - date_diff / date_tolerance)
        except:
            pass

        # Type match
        if txn1.get('transaction_type') == txn2.get('transaction_type'):
            score += weights['type']

        # Currency match
        if txn1.get('currency') == txn2.get('currency'):
            score += weights['currency']

        return score

    def _process_differences(
        self,
        matches: List[Dict[str, Any]],
        rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process differences in matched transactions.

        Args:
            matches: List of matched transaction pairs
            rules: Reconciliation rules

        Returns:
            List of adjustment records
        """
        adjustments = []
        default_rule = rules[0] if rules else {'tolerance_amount': 100.0, 'auto_adjust': 1}

        for match in matches:
            amount_diff = match['amount_difference']
            tolerance = default_rule.get('tolerance_amount', 100.0)
            auto_adjust = default_rule.get('auto_adjust', 1)

            if amount_diff > 0:
                if amount_diff <= tolerance and auto_adjust:
                    # Auto-adjust within tolerance
                    adjustments.append({
                        'match_id': f"{match['seller_txn_id']}-{match['buyer_txn_id']}",
                        'adjustment_type': 'auto_tolerance',
                        'amount_difference': amount_diff,
                        'action': 'auto_adjusted',
                        'description': f"自动调整差异 {amount_diff:.2f} (在容忍范围内)"
                    })
                    match['adjustment_status'] = 'auto_adjusted'
                else:
                    # Requires manual review
                    adjustments.append({
                        'match_id': f"{match['seller_txn_id']}-{match['buyer_txn_id']}",
                        'adjustment_type': 'manual_review',
                        'amount_difference': amount_diff,
                        'action': 'requires_review',
                        'description': f"差异 {amount_diff:.2f} 超出容忍范围，需人工审核"
                    })
                    match['adjustment_status'] = 'requires_review'
            else:
                match['adjustment_status'] = 'perfect_match'

        return adjustments

    def _update_reconciliation_status(
        self,
        matches: List[Dict[str, Any]],
        adjustments: List[Dict[str, Any]]
    ):
        """Update reconciliation status in database.

        Args:
            matches: List of matched transactions
            adjustments: List of adjustments
        """
        for match in matches:
            status = match.get('adjustment_status', 'matched')

            # Update seller transaction
            self.conn.execute("""
                UPDATE intercompany_transactions
                SET reconciliation_status = ?,
                    reconciliation_partner_id = ?,
                    time_difference_days = ?,
                    amount_difference = ?,
                    auto_reconciled = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE transaction_id = ?
            """, (
                status,
                match['buyer_txn_id'],
                match['time_difference_days'],
                match['amount_difference'],
                1 if status == 'auto_adjusted' else 0,
                match['seller_txn_id']
            ))

            # Update buyer transaction
            self.conn.execute("""
                UPDATE intercompany_transactions
                SET reconciliation_status = ?,
                    reconciliation_partner_id = ?,
                    time_difference_days = ?,
                    amount_difference = ?,
                    auto_reconciled = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE transaction_id = ?
            """, (
                status,
                match['seller_txn_id'],
                match['time_difference_days'],
                match['amount_difference'],
                1 if status == 'auto_adjusted' else 0,
                match['buyer_txn_id']
            ))

        logger.info(f"Updated reconciliation status for {len(matches)} transaction pairs")

    def _generate_reconciliation_report(
        self,
        matches: List[Dict[str, Any]],
        adjustments: List[Dict[str, Any]],
        all_transactions: pd.DataFrame
    ) -> Dict[str, Any]:
        """Generate reconciliation report.

        Args:
            matches: List of matched transactions
            adjustments: List of adjustments
            all_transactions: All transactions in scope

        Returns:
            Report dictionary
        """
        matched_count = len(matches)
        unmatched_count = len(all_transactions) - matched_count * 2

        auto_adjusted = len([m for m in matches if m.get('adjustment_status') == 'auto_adjusted'])
        perfect_matches = len([m for m in matches if m.get('adjustment_status') == 'perfect_match'])
        requires_review = len([m for m in matches if m.get('adjustment_status') == 'requires_review'])

        total_matched_amount = sum(m['seller_amount'] for m in matches)
        total_difference = sum(m['amount_difference'] for m in matches)

        report_text = f"""
对账报告
{'='*60}
对账期间: {all_transactions.iloc[0]['fiscal_period'] if not all_transactions.empty else 'N/A'}
对账时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

对账结果统计:
- 总交易数: {len(all_transactions)}
- 成功匹配: {matched_count} 对
- 未匹配: {unmatched_count}

匹配详情:
- 完全匹配: {perfect_matches}
- 自动调整: {auto_adjusted}
- 需人工审核: {requires_review}

金额统计:
- 匹配总金额: {total_matched_amount:,.2f}
- 差异总金额: {total_difference:,.2f}
- 平均差异: {total_difference/matched_count if matched_count > 0 else 0:,.2f}

对账完成度: {matched_count*2/len(all_transactions)*100 if len(all_transactions) > 0 else 0:.1f}%
{'='*60}
"""

        return {
            'matched_count': matched_count,
            'unmatched_count': unmatched_count,
            'auto_adjusted': auto_adjusted,
            'perfect_matches': perfect_matches,
            'requires_review': requires_review,
            'total_matched_amount': total_matched_amount,
            'total_difference_amount': total_difference,
            'avg_difference': total_difference / matched_count if matched_count > 0 else 0,
            'completion_rate': matched_count * 2 / len(all_transactions) * 100 if len(all_transactions) > 0 else 0,
            'details': matches,
            'adjustments': adjustments,
            'report': report_text
        }

    def get_reconciliation_summary(
        self,
        entity_ids: List[int],
        period: str
    ) -> Dict[str, Any]:
        """Get reconciliation summary for entities and period.

        Args:
            entity_ids: List of entity IDs
            period: Fiscal period

        Returns:
            Summary dictionary
        """
        self.connect()

        placeholders = ",".join(["?"] * len(entity_ids))
        params = [period] + entity_ids + entity_ids

        # Get summary statistics
        query = f"""
            SELECT
                COUNT(*) as total_transactions,
                COUNT(CASE WHEN reconciliation_status = 'perfect_match' THEN 1 END) as perfect_matches,
                COUNT(CASE WHEN reconciliation_status = 'auto_adjusted' THEN 1 END) as auto_adjusted,
                COUNT(CASE WHEN reconciliation_status = 'requires_review' THEN 1 END) as requires_review,
                COUNT(CASE WHEN reconciliation_status IS NULL OR reconciliation_status = '未对账' THEN 1 END) as unreconciled,
                SUM(CASE WHEN amount_difference IS NOT NULL THEN amount_difference ELSE 0 END) as total_difference
            FROM intercompany_transactions
            WHERE fiscal_period = ?
              AND (seller_entity_id IN ({placeholders}) OR buyer_entity_id IN ({placeholders}))
        """

        row = self.conn.execute(query, params).fetchone()

        return {
            'total_transactions': row['total_transactions'],
            'perfect_matches': row['perfect_matches'],
            'auto_adjusted': row['auto_adjusted'],
            'requires_review': row['requires_review'],
            'unreconciled': row['unreconciled'],
            'total_difference': row['total_difference'] or 0.0,
            'reconciliation_rate': (row['total_transactions'] - row['unreconciled']) / row['total_transactions'] * 100
                                  if row['total_transactions'] > 0 else 0
        }


if __name__ == "__main__":
    # Test reconciliation engine
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/dap.db"

    print(f"\n{'='*60}")
    print(f"Reconciliation Engine Test")
    print(f"{'='*60}\n")

    with ReconciliationEngine(db_path) as engine:
        print("Reconciliation Engine initialized successfully")
        print(f"Database: {db_path}")
