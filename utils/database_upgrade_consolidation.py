"""Database schema upgrade for multi-level consolidation support.

This module provides database schema extensions to support:
1. Multi-level company hierarchies (6+ levels)
2. Consolidated financial reporting
3. Internal transaction elimination
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ConsolidationDatabaseUpgrade:
    """Handles database schema upgrade for consolidation features."""

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
                logger.info("Database already upgraded for consolidation features")
                return True

            logger.info("Starting database upgrade for consolidation features...")

            # Create new tables
            self._create_entities_table()
            self._create_entity_relationships_table()
            self._create_intercompany_transactions_table()
            self._create_consolidation_adjustments_table()
            self._create_consolidation_metadata_table()

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
        """Check if consolidation tables already exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='entities'
        """)
        return cursor.fetchone() is not None

    def _create_entities_table(self):
        """Create entities (companies) table."""
        logger.info("Creating entities table...")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_code TEXT NOT NULL UNIQUE,
                entity_name TEXT NOT NULL,
                entity_type TEXT CHECK(entity_type IN ('母公司', '子公司', '孙公司', '联营公司', '合营公司')) DEFAULT '子公司',

                -- Project association
                project_id TEXT NOT NULL,

                -- Hierarchy information
                parent_entity_id INTEGER,
                level INTEGER DEFAULT 1 CHECK(level >= 1 AND level <= 10),
                hierarchy_path TEXT,

                -- Ownership structure
                ownership_percentage REAL DEFAULT 100.0 CHECK(ownership_percentage > 0 AND ownership_percentage <= 100),
                effective_ownership REAL DEFAULT 100.0 CHECK(effective_ownership > 0 AND effective_ownership <= 100),
                control_type TEXT CHECK(control_type IN ('全资', '控股', '参股', '共同控制')) DEFAULT '控股',

                -- Basic information
                taxpayer_id TEXT,
                registration_number TEXT,
                legal_representative TEXT,
                registered_capital REAL,
                registered_address TEXT,
                business_scope TEXT,

                -- Financial information
                fiscal_year TEXT,
                fiscal_period TEXT,
                accounting_standard TEXT CHECK(accounting_standard IN ('企业会计准则', 'IFRS', 'US GAAP', '小企业会计准则')) DEFAULT '企业会计准则',
                functional_currency TEXT DEFAULT 'CNY',

                -- Status
                is_active INTEGER DEFAULT 1,
                consolidation_method TEXT CHECK(consolidation_method IN ('全额合并', '比例合并', '权益法', '成本法', '不合并')) DEFAULT '全额合并',

                -- Audit trail
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                notes TEXT,

                FOREIGN KEY (parent_entity_id) REFERENCES entities(entity_id)
            )
        """)
        logger.info("Entities table created successfully")

    def _create_entity_relationships_table(self):
        """Create entity relationships table for detailed hierarchy tracking."""
        logger.info("Creating entity_relationships table...")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_relationships (
                relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_entity_id INTEGER NOT NULL,
                child_entity_id INTEGER NOT NULL,

                -- Relationship details
                relationship_type TEXT CHECK(relationship_type IN ('直接投资', '间接投资', '交叉持股', '联营', '合营')) DEFAULT '直接投资',
                ownership_percentage REAL NOT NULL CHECK(ownership_percentage > 0 AND ownership_percentage <= 100),
                voting_rights_percentage REAL CHECK(voting_rights_percentage > 0 AND voting_rights_percentage <= 100),

                -- Investment details
                investment_date DATE,
                investment_amount REAL,
                investment_account TEXT,

                -- Status
                is_active INTEGER DEFAULT 1,
                effective_from DATE,
                effective_to DATE,

                -- Audit trail
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,

                FOREIGN KEY (parent_entity_id) REFERENCES entities(entity_id),
                FOREIGN KEY (child_entity_id) REFERENCES entities(entity_id),
                UNIQUE(parent_entity_id, child_entity_id)
            )
        """)
        logger.info("Entity_relationships table created successfully")

    def _create_intercompany_transactions_table(self):
        """Create internal transactions table for elimination tracking."""
        logger.info("Creating intercompany_transactions table...")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS intercompany_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Transaction parties
                seller_entity_id INTEGER NOT NULL,
                buyer_entity_id INTEGER NOT NULL,

                -- Transaction details
                transaction_type TEXT CHECK(transaction_type IN ('销售商品', '提供服务', '借款', '担保', '资产转让', '其他')) NOT NULL,
                transaction_date DATE NOT NULL,
                fiscal_period TEXT NOT NULL,

                -- Financial details
                transaction_amount REAL NOT NULL,
                currency TEXT DEFAULT 'CNY',
                exchange_rate REAL DEFAULT 1.0,
                transaction_amount_cny REAL,

                -- Accounting records
                seller_account_code TEXT,
                seller_account_name TEXT,
                buyer_account_code TEXT,
                buyer_account_name TEXT,
                voucher_number TEXT,

                -- Elimination tracking
                needs_elimination INTEGER DEFAULT 1,
                elimination_status TEXT CHECK(elimination_status IN ('待抵销', '已抵销', '部分抵销', '无需抵销')) DEFAULT '待抵销',
                elimination_percentage REAL DEFAULT 100.0,

                -- Unrealized profit
                has_unrealized_profit INTEGER DEFAULT 0,
                unrealized_profit_amount REAL DEFAULT 0.0,

                -- Status
                is_verified INTEGER DEFAULT 0,
                verified_by TEXT,
                verified_at TIMESTAMP,

                -- Audit trail
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,

                FOREIGN KEY (seller_entity_id) REFERENCES entities(entity_id),
                FOREIGN KEY (buyer_entity_id) REFERENCES entities(entity_id)
            )
        """)
        logger.info("Intercompany_transactions table created successfully")

    def _create_consolidation_adjustments_table(self):
        """Create consolidation adjustment entries table."""
        logger.info("Creating consolidation_adjustments table...")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS consolidation_adjustments (
                adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Consolidation context
                consolidation_period TEXT NOT NULL,
                parent_entity_id INTEGER NOT NULL,

                -- Adjustment type
                adjustment_type TEXT CHECK(adjustment_type IN ('内部交易抵销', '内部债权债务抵销', '未实现利润抵销', '长期股权投资抵销', '少数股东权益调整', '其他')) NOT NULL,
                adjustment_category TEXT CHECK(adjustment_category IN ('合并工作底稿调整', '持续性调整', '本期调整')) DEFAULT '本期调整',

                -- Accounting entry
                entry_number TEXT,
                entry_date DATE,
                debit_account_code TEXT NOT NULL,
                debit_account_name TEXT,
                credit_account_code TEXT NOT NULL,
                credit_account_name TEXT,
                amount REAL NOT NULL CHECK(amount > 0),
                currency TEXT DEFAULT 'CNY',

                -- Related entities
                related_entity_id INTEGER,
                related_transaction_id INTEGER,

                -- Status
                is_applied INTEGER DEFAULT 0,
                is_recurring INTEGER DEFAULT 0,

                -- Audit trail
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                approved_by TEXT,
                approved_at TIMESTAMP,
                notes TEXT,

                FOREIGN KEY (parent_entity_id) REFERENCES entities(entity_id),
                FOREIGN KEY (related_entity_id) REFERENCES entities(entity_id),
                FOREIGN KEY (related_transaction_id) REFERENCES intercompany_transactions(transaction_id)
            )
        """)
        logger.info("Consolidation_adjustments table created successfully")

    def _create_consolidation_metadata_table(self):
        """Create consolidation metadata table for tracking consolidation runs."""
        logger.info("Creating consolidation_metadata table...")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS consolidation_metadata (
                consolidation_id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Consolidation scope
                parent_entity_id INTEGER NOT NULL,
                consolidation_period TEXT NOT NULL,
                consolidation_date DATE DEFAULT (date('now')),

                -- Scope details
                scope_entity_ids TEXT NOT NULL,
                scope_entity_count INTEGER,
                consolidation_method TEXT,

                -- Results summary
                total_assets REAL,
                total_liabilities REAL,
                total_equity REAL,
                minority_interest REAL,
                consolidated_revenue REAL,
                consolidated_net_income REAL,

                -- Elimination summary
                elimination_count INTEGER DEFAULT 0,
                total_elimination_amount REAL DEFAULT 0.0,

                -- Status
                status TEXT CHECK(status IN ('进行中', '已完成', '失败', '已取消')) DEFAULT '进行中',

                -- Audit trail
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                notes TEXT,

                FOREIGN KEY (parent_entity_id) REFERENCES entities(entity_id)
            )
        """)
        logger.info("Consolidation_metadata table created successfully")

    def _create_indexes(self):
        """Create indexes for performance optimization."""
        logger.info("Creating indexes...")

        indexes = [
            # Entities indexes
            "CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_entities_parent ON entities(parent_entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_entities_level ON entities(level)",
            "CREATE INDEX IF NOT EXISTS idx_entities_hierarchy ON entities(hierarchy_path)",

            # Relationships indexes
            "CREATE INDEX IF NOT EXISTS idx_relationships_parent ON entity_relationships(parent_entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_relationships_child ON entity_relationships(child_entity_id)",

            # Intercompany transactions indexes
            "CREATE INDEX IF NOT EXISTS idx_interco_seller ON intercompany_transactions(seller_entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_interco_buyer ON intercompany_transactions(buyer_entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_interco_period ON intercompany_transactions(fiscal_period)",
            "CREATE INDEX IF NOT EXISTS idx_interco_status ON intercompany_transactions(elimination_status)",

            # Adjustments indexes
            "CREATE INDEX IF NOT EXISTS idx_adjustments_period ON consolidation_adjustments(consolidation_period)",
            "CREATE INDEX IF NOT EXISTS idx_adjustments_parent ON consolidation_adjustments(parent_entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_adjustments_type ON consolidation_adjustments(adjustment_type)",

            # Metadata indexes
            "CREATE INDEX IF NOT EXISTS idx_metadata_parent ON consolidation_metadata(parent_entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_metadata_period ON consolidation_metadata(consolidation_period)",
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
            VALUES ('consolidation_upgrade_version', '1.0.0', CURRENT_TIMESTAMP)
        """)


def upgrade_database(db_path: str) -> bool:
    """Convenience function to upgrade database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if upgrade successful, False otherwise
    """
    upgrader = ConsolidationDatabaseUpgrade(db_path)
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
    print(f"Database Upgrade for Consolidation Features")
    print(f"{'='*60}")
    print(f"Database: {db_path}\n")

    if upgrade_database(db_path):
        print("\n✅ Database upgrade completed successfully!")
    else:
        print("\n❌ Database upgrade failed!")
        sys.exit(1)
