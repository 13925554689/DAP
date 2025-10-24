"""Database schema upgrade for reconciliation and adjustment features.

This module adds:
1. Reconciliation fields to intercompany_transactions table
2. reconciliation_rules table
3. adjustment_history table
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ReconciliationDatabaseUpgrade:
    """Handles database schema upgrade for reconciliation features."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_path}")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def upgrade(self) -> bool:
        """Execute all upgrade steps."""
        try:
            self.connect()

            # Check if already upgraded
            if self._check_if_upgraded():
                logger.info("Database already upgraded for reconciliation features")
                return True

            logger.info("Starting database upgrade for reconciliation and adjustment features...")

            # Extend intercompany_transactions table
            self._extend_intercompany_transactions()

            # Create reconciliation_rules table
            self._create_reconciliation_rules_table()

            # Create adjustment_history table
            self._create_adjustment_history_table()

            # Create indexes
            self._create_indexes()

            # Mark upgrade complete
            self._mark_upgrade_complete()

            self.conn.commit()
            logger.info("Database upgrade completed successfully!")
            return True

        except Exception as e:
            logger.error(f"Database upgrade failed: {e}", exc_info=True)
            if self.conn:
                self.conn.rollback()
            return False
        finally:
            self.disconnect()

    def _check_if_upgraded(self) -> bool:
        """Check if reconciliation features already exist."""
        cursor = self.conn.cursor()

        # Check if reconciliation_rules table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='reconciliation_rules'
        """)

        return cursor.fetchone() is not None

    def _extend_intercompany_transactions(self):
        """Add reconciliation fields to intercompany_transactions table."""
        logger.info("Extending intercompany_transactions table...")

        # Check if table exists
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='intercompany_transactions'
        """)

        if not cursor.fetchone():
            logger.warning("intercompany_transactions table does not exist, skipping extension")
            return

        # Add columns if they don't exist
        columns_to_add = [
            ("reconciliation_status", "TEXT DEFAULT '未对账'"),
            ("reconciliation_partner_id", "INTEGER"),
            ("time_difference_days", "INTEGER DEFAULT 0"),
            ("amount_difference", "REAL DEFAULT 0.0"),
            ("auto_reconciled", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_def in columns_to_add:
            try:
                self.conn.execute(f"""
                    ALTER TABLE intercompany_transactions
                    ADD COLUMN {col_name} {col_def}
                """)
                logger.info(f"Added column {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"Column {col_name} already exists")
                else:
                    raise

    def _create_reconciliation_rules_table(self):
        """Create reconciliation_rules table."""
        logger.info("Creating reconciliation_rules table...")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_type TEXT NOT NULL,
                tolerance_days INTEGER DEFAULT 3,
                tolerance_amount REAL DEFAULT 100.0,
                tolerance_percentage REAL DEFAULT 1.0,
                auto_adjust INTEGER DEFAULT 1,
                matching_fields TEXT,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default rules
        default_rules = [
            ('销售商品', 3, 100.0, 1.0, 1, '["transaction_type", "currency"]', '商品销售对账规则'),
            ('提供服务', 5, 500.0, 2.0, 1, '["transaction_type", "currency"]', '服务收入对账规则'),
            ('借款', 1, 10.0, 0.1, 1, '["transaction_type", "currency"]', '借款对账规则'),
            ('资产转让', 3, 1000.0, 0.5, 0, '["transaction_type", "currency"]', '资产转让对账规则（需人工审核）'),
            ('default', 3, 100.0, 1.0, 1, '["transaction_type"]', '默认对账规则'),
        ]

        for rule in default_rules:
            try:
                self.conn.execute("""
                    INSERT INTO reconciliation_rules
                    (scenario_type, tolerance_days, tolerance_amount, tolerance_percentage,
                     auto_adjust, matching_fields, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, rule)
            except sqlite3.IntegrityError:
                logger.info(f"Default rule for {rule[0]} already exists")

        logger.info("Reconciliation_rules table created successfully")

    def _create_adjustment_history_table(self):
        """Create adjustment_history table."""
        logger.info("Creating adjustment_history table...")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS adjustment_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjustment_id INTEGER NOT NULL,
                adjustment_type TEXT NOT NULL,
                adjustment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entity_id INTEGER,
                period TEXT NOT NULL,
                debit_account TEXT,
                debit_account_name TEXT,
                credit_account TEXT,
                credit_account_name TEXT,
                amount REAL NOT NULL CHECK(amount > 0),
                description TEXT,
                created_by TEXT,
                is_reversed INTEGER DEFAULT 0,
                reversed_by_id INTEGER,
                value_dimension TEXT DEFAULT 'actual',
                FOREIGN KEY (adjustment_id) REFERENCES consolidation_adjustments(adjustment_id),
                FOREIGN KEY (reversed_by_id) REFERENCES adjustment_history(history_id)
            )
        """)

        logger.info("Adjustment_history table created successfully")

    def _create_indexes(self):
        """Create indexes for performance optimization."""
        logger.info("Creating indexes...")

        indexes = [
            # Reconciliation indexes
            "CREATE INDEX IF NOT EXISTS idx_interco_recon_status ON intercompany_transactions(reconciliation_status)",
            "CREATE INDEX IF NOT EXISTS idx_interco_recon_partner ON intercompany_transactions(reconciliation_partner_id)",

            # Reconciliation rules indexes
            "CREATE INDEX IF NOT EXISTS idx_recon_rules_scenario ON reconciliation_rules(scenario_type)",
            "CREATE INDEX IF NOT EXISTS idx_recon_rules_active ON reconciliation_rules(is_active)",

            # Adjustment history indexes
            "CREATE INDEX IF NOT EXISTS idx_adj_history_adj_id ON adjustment_history(adjustment_id)",
            "CREATE INDEX IF NOT EXISTS idx_adj_history_entity ON adjustment_history(entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_adj_history_period ON adjustment_history(period)",
            "CREATE INDEX IF NOT EXISTS idx_adj_history_type ON adjustment_history(adjustment_type)",
            "CREATE INDEX IF NOT EXISTS idx_adj_history_dimension ON adjustment_history(value_dimension)",
        ]

        for idx_sql in indexes:
            self.conn.execute(idx_sql)

        logger.info(f"Created {len(indexes)} indexes successfully")

    def _mark_upgrade_complete(self):
        """Mark the upgrade as complete in system metadata."""
        logger.info("Marking upgrade as complete...")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS system_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            INSERT OR REPLACE INTO system_metadata (key, value, updated_at)
            VALUES ('reconciliation_upgrade_version', '1.0.0', CURRENT_TIMESTAMP)
        """)


def upgrade_database(db_path: str) -> bool:
    """Convenience function to upgrade database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if upgrade successful, False otherwise
    """
    upgrader = ReconciliationDatabaseUpgrade(db_path)
    return upgrader.upgrade()


if __name__ == "__main__":
    # Test upgrade with default database path
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/dap.db"

    print(f"\n{'='*60}")
    print(f"Database Upgrade for Reconciliation Features")
    print(f"{'='*60}")
    print(f"Database: {db_path}\n")

    if upgrade_database(db_path):
        print("\n✅ Database upgrade completed successfully!")
    else:
        print("\n❌ Database upgrade failed!")
        sys.exit(1)
