"""Group Hierarchy Manager for multi-level company structure management.

This module provides comprehensive entity hierarchy management including:
1. Entity (company) creation and management
2. Parent-child relationship tracking
3. Ownership percentage calculation (direct and effective)
4. Hierarchy path management
5. Consolidation scope determination
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GroupHierarchyManager:
    """Manages multi-level company hierarchies for consolidation."""

    def __init__(self, db_path: str):
        """Initialize the hierarchy manager.

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

    def create_entity(
        self,
        project_id: str,
        entity_code: str,
        entity_name: str,
        entity_type: str = "子公司",
        parent_entity_id: Optional[int] = None,
        ownership_percentage: float = 100.0,
        **kwargs
    ) -> int:
        """Create a new entity (company) in the hierarchy.

        Args:
            project_id: Project identifier
            entity_code: Unique entity code
            entity_name: Entity name
            entity_type: Type of entity (母公司, 子公司, 孙公司, 联营公司, 合营公司)
            parent_entity_id: Parent entity ID (None for root entity)
            ownership_percentage: Direct ownership percentage (0-100)
            **kwargs: Additional entity attributes

        Returns:
            Entity ID of the newly created entity

        Raises:
            ValueError: If entity_code already exists or validation fails
        """
        self.connect()

        # Validate ownership percentage
        if not 0 < ownership_percentage <= 100:
            raise ValueError(f"Ownership percentage must be between 0 and 100, got {ownership_percentage}")

        # Check if entity code already exists
        existing = self.conn.execute(
            "SELECT entity_id FROM entities WHERE entity_code = ?",
            (entity_code,)
        ).fetchone()

        if existing:
            raise ValueError(f"Entity code '{entity_code}' already exists")

        # Calculate level and hierarchy path
        level = 1
        hierarchy_path = ""
        effective_ownership = ownership_percentage

        if parent_entity_id is not None:
            parent = self.get_entity(parent_entity_id)
            if not parent:
                raise ValueError(f"Parent entity {parent_entity_id} not found")

            level = parent["level"] + 1
            parent_path = parent["hierarchy_path"] or ""
            hierarchy_path = f"{parent_path}.{parent_entity_id}" if parent_path else str(parent_entity_id)

            # Calculate effective ownership
            parent_effective = parent.get("effective_ownership", 100.0)
            effective_ownership = (parent_effective * ownership_percentage) / 100.0

        # Determine consolidation method based on ownership
        if effective_ownership >= 50:
            consolidation_method = "全额合并" if ownership_percentage > 95 else "全额合并"
        elif effective_ownership >= 20:
            consolidation_method = "权益法"
        else:
            consolidation_method = "成本法"

        # Insert entity
        cursor = self.conn.execute("""
            INSERT INTO entities (
                entity_code, entity_name, entity_type, project_id,
                parent_entity_id, level, hierarchy_path,
                ownership_percentage, effective_ownership,
                control_type, consolidation_method,
                taxpayer_id, registration_number, legal_representative,
                registered_capital, registered_address, business_scope,
                fiscal_year, fiscal_period, accounting_standard,
                functional_currency, is_active, created_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity_code, entity_name, entity_type, project_id,
            parent_entity_id, level, hierarchy_path,
            ownership_percentage, effective_ownership,
            kwargs.get("control_type", self._determine_control_type(ownership_percentage)),
            consolidation_method,
            kwargs.get("taxpayer_id"),
            kwargs.get("registration_number"),
            kwargs.get("legal_representative"),
            kwargs.get("registered_capital"),
            kwargs.get("registered_address"),
            kwargs.get("business_scope"),
            kwargs.get("fiscal_year"),
            kwargs.get("fiscal_period"),
            kwargs.get("accounting_standard", "企业会计准则"),
            kwargs.get("functional_currency", "CNY"),
            kwargs.get("is_active", 1),
            kwargs.get("created_by"),
            kwargs.get("notes")
        ))

        entity_id = cursor.lastrowid
        self.conn.commit()

        # Create relationship record if has parent
        if parent_entity_id is not None:
            self._create_relationship(
                parent_entity_id, entity_id, ownership_percentage, **kwargs
            )

        logger.info(f"Created entity {entity_id}: {entity_name} (level {level})")
        return entity_id

    def _determine_control_type(self, ownership_pct: float) -> str:
        """Determine control type based on ownership percentage."""
        if ownership_pct >= 99:
            return "全资"
        elif ownership_pct >= 50:
            return "控股"
        elif ownership_pct >= 20:
            return "参股"
        else:
            return "参股"

    def _create_relationship(
        self,
        parent_entity_id: int,
        child_entity_id: int,
        ownership_percentage: float,
        **kwargs
    ):
        """Create entity relationship record."""
        self.conn.execute("""
            INSERT INTO entity_relationships (
                parent_entity_id, child_entity_id, relationship_type,
                ownership_percentage, voting_rights_percentage,
                investment_date, investment_amount, investment_account,
                is_active, effective_from, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            parent_entity_id, child_entity_id,
            kwargs.get("relationship_type", "直接投资"),
            ownership_percentage,
            kwargs.get("voting_rights_percentage", ownership_percentage),
            kwargs.get("investment_date"),
            kwargs.get("investment_amount"),
            kwargs.get("investment_account"),
            kwargs.get("is_active", 1),
            kwargs.get("effective_from", datetime.now().strftime("%Y-%m-%d")),
            kwargs.get("notes")
        ))
        self.conn.commit()

    def add_subsidiary(
        self,
        parent_id: int,
        subsidiary_data: Dict[str, Any],
        ownership_pct: float
    ) -> int:
        """Convenience method to add a subsidiary to an existing entity.

        Args:
            parent_id: Parent entity ID
            subsidiary_data: Dictionary with subsidiary information
            ownership_pct: Ownership percentage

        Returns:
            Entity ID of the new subsidiary
        """
        return self.create_entity(
            project_id=subsidiary_data.get("project_id", ""),
            entity_code=subsidiary_data["entity_code"],
            entity_name=subsidiary_data["entity_name"],
            entity_type=subsidiary_data.get("entity_type", "子公司"),
            parent_entity_id=parent_id,
            ownership_percentage=ownership_pct,
            **subsidiary_data
        )

    def get_entity(self, entity_id: int) -> Optional[Dict[str, Any]]:
        """Get entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            Entity dictionary or None if not found
        """
        self.connect()
        row = self.conn.execute(
            "SELECT * FROM entities WHERE entity_id = ?",
            (entity_id,)
        ).fetchone()

        return dict(row) if row else None

    def get_entity_by_code(self, entity_code: str) -> Optional[Dict[str, Any]]:
        """Get entity by code.

        Args:
            entity_code: Entity code

        Returns:
            Entity dictionary or None if not found
        """
        self.connect()
        row = self.conn.execute(
            "SELECT * FROM entities WHERE entity_code = ?",
            (entity_code,)
        ).fetchone()

        return dict(row) if row else None

    def list_entities(self, project_id: str) -> List[Dict[str, Any]]:
        """List all entities in a project.

        Args:
            project_id: Project identifier

        Returns:
            List of entity dictionaries
        """
        self.connect()
        rows = self.conn.execute(
            """SELECT * FROM entities
               WHERE project_id = ?
               ORDER BY level, entity_code""",
            (project_id,)
        ).fetchall()

        return [dict(row) for row in rows]

    def get_entity_hierarchy(
        self,
        parent_entity_id: int,
        max_depth: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get entity hierarchy tree starting from parent.

        Args:
            parent_entity_id: Parent entity ID
            max_depth: Maximum depth to traverse (None for unlimited)

        Returns:
            List of entities in the hierarchy
        """
        self.connect()

        parent = self.get_entity(parent_entity_id)
        if not parent:
            return []

        parent_level = parent["level"]
        hierarchy_pattern = f"{parent['hierarchy_path']}.{parent_entity_id}%"

        query = """
            SELECT * FROM entities
            WHERE entity_id = ? OR hierarchy_path LIKE ?
        """
        params = [parent_entity_id, hierarchy_pattern]

        if max_depth is not None:
            query += " AND level <= ?"
            params.append(parent_level + max_depth)

        query += " ORDER BY level, entity_code"

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_direct_children(self, parent_entity_id: int) -> List[Dict[str, Any]]:
        """Get direct children of an entity.

        Args:
            parent_entity_id: Parent entity ID

        Returns:
            List of child entities
        """
        self.connect()
        rows = self.conn.execute(
            """SELECT * FROM entities
               WHERE parent_entity_id = ?
               ORDER BY entity_code""",
            (parent_entity_id,)
        ).fetchall()

        return [dict(row) for row in rows]

    def calculate_hierarchy_path(self, entity_id: int) -> str:
        """Calculate and update hierarchy path for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            Updated hierarchy path
        """
        entity = self.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        parent_id = entity["parent_entity_id"]
        if parent_id is None:
            hierarchy_path = ""
        else:
            parent = self.get_entity(parent_id)
            parent_path = parent["hierarchy_path"] or ""
            hierarchy_path = f"{parent_path}.{parent_id}" if parent_path else str(parent_id)

        # Update in database
        self.connect()
        self.conn.execute(
            "UPDATE entities SET hierarchy_path = ? WHERE entity_id = ?",
            (hierarchy_path, entity_id)
        )
        self.conn.commit()

        return hierarchy_path

    def get_consolidation_scope(
        self,
        parent_id: int,
        include_criteria: Optional[Dict[str, Any]] = None
    ) -> List[int]:
        """Get list of entity IDs to include in consolidation.

        Args:
            parent_id: Parent entity ID (consolidation root)
            include_criteria: Optional filtering criteria
                - min_ownership: Minimum effective ownership percentage
                - consolidation_methods: List of allowed consolidation methods
                - entity_types: List of allowed entity types

        Returns:
            List of entity IDs in consolidation scope
        """
        criteria = include_criteria or {}
        min_ownership = criteria.get("min_ownership", 0)
        methods = criteria.get("consolidation_methods", ["全额合并", "比例合并"])
        types = criteria.get("entity_types")

        # Get all entities in hierarchy
        entities = self.get_entity_hierarchy(parent_id)

        # Filter based on criteria
        scope_ids = []
        for entity in entities:
            # Check ownership
            if entity["effective_ownership"] < min_ownership:
                continue

            # Check consolidation method
            if entity["consolidation_method"] not in methods:
                continue

            # Check entity type
            if types and entity["entity_type"] not in types:
                continue

            # Check if active
            if not entity["is_active"]:
                continue

            scope_ids.append(entity["entity_id"])

        logger.info(f"Consolidation scope for entity {parent_id}: {len(scope_ids)} entities")
        return scope_ids

    def calculate_effective_ownership(
        self,
        parent_id: int,
        target_id: int
    ) -> float:
        """Calculate effective ownership percentage from parent to target.

        Args:
            parent_id: Parent entity ID
            target_id: Target entity ID

        Returns:
            Effective ownership percentage (0-100)
        """
        if parent_id == target_id:
            return 100.0

        target = self.get_entity(target_id)
        if not target:
            raise ValueError(f"Target entity {target_id} not found")

        # If target is direct child
        if target["parent_entity_id"] == parent_id:
            return target["ownership_percentage"]

        # Traverse up from target to parent
        effective = 100.0
        current_id = target_id

        while current_id != parent_id:
            current = self.get_entity(current_id)
            if not current or current["parent_entity_id"] is None:
                return 0.0  # No path found

            effective = (effective * current["ownership_percentage"]) / 100.0
            current_id = current["parent_entity_id"]

        return effective

    def update_entity(self, entity_id: int, **kwargs) -> bool:
        """Update entity information.

        Args:
            entity_id: Entity ID
            **kwargs: Fields to update

        Returns:
            True if successful
        """
        self.connect()

        # Build UPDATE query dynamically
        allowed_fields = [
            "entity_name", "entity_type", "ownership_percentage",
            "control_type", "consolidation_method",
            "taxpayer_id", "registration_number", "legal_representative",
            "registered_capital", "registered_address", "business_scope",
            "fiscal_year", "fiscal_period", "accounting_standard",
            "functional_currency", "is_active", "notes"
        ]

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        # Add updated_at
        updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build SQL
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [entity_id]

        self.conn.execute(
            f"UPDATE entities SET {set_clause} WHERE entity_id = ?",
            values
        )
        self.conn.commit()

        logger.info(f"Updated entity {entity_id}")
        return True

    def delete_entity(self, entity_id: int, cascade: bool = False) -> bool:
        """Delete an entity.

        Args:
            entity_id: Entity ID
            cascade: If True, delete all children recursively

        Returns:
            True if successful

        Raises:
            ValueError: If entity has children and cascade=False
        """
        self.connect()

        # Check for children
        children = self.get_direct_children(entity_id)
        if children and not cascade:
            raise ValueError(
                f"Entity {entity_id} has {len(children)} children. "
                "Set cascade=True to delete recursively."
            )

        if cascade:
            # Delete children first
            for child in children:
                self.delete_entity(child["entity_id"], cascade=True)

        # Delete relationships
        self.conn.execute(
            "DELETE FROM entity_relationships WHERE parent_entity_id = ? OR child_entity_id = ?",
            (entity_id, entity_id)
        )

        # Delete entity
        self.conn.execute("DELETE FROM entities WHERE entity_id = ?", (entity_id,))
        self.conn.commit()

        logger.info(f"Deleted entity {entity_id}")
        return True

    def get_entity_path_names(self, entity_id: int) -> List[str]:
        """Get the full path of entity names from root to entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of entity names from root to target
        """
        path_names = []
        current_id = entity_id

        while current_id is not None:
            entity = self.get_entity(current_id)
            if not entity:
                break
            path_names.insert(0, entity["entity_name"])
            current_id = entity["parent_entity_id"]

        return path_names

    def get_statistics(self, project_id: str) -> Dict[str, Any]:
        """Get hierarchy statistics for a project.

        Args:
            project_id: Project identifier

        Returns:
            Dictionary with statistics
        """
        self.connect()

        stats = {}

        # Total entities
        stats["total_entities"] = self.conn.execute(
            "SELECT COUNT(*) FROM entities WHERE project_id = ?",
            (project_id,)
        ).fetchone()[0]

        # By level
        level_rows = self.conn.execute(
            """SELECT level, COUNT(*) as count
               FROM entities
               WHERE project_id = ?
               GROUP BY level
               ORDER BY level""",
            (project_id,)
        ).fetchall()
        stats["by_level"] = {row[0]: row[1] for row in level_rows}

        # By entity type
        type_rows = self.conn.execute(
            """SELECT entity_type, COUNT(*) as count
               FROM entities
               WHERE project_id = ?
               GROUP BY entity_type""",
            (project_id,)
        ).fetchall()
        stats["by_type"] = {row[0]: row[1] for row in type_rows}

        # Max depth
        max_level = self.conn.execute(
            "SELECT MAX(level) FROM entities WHERE project_id = ?",
            (project_id,)
        ).fetchone()[0] or 0
        stats["max_depth"] = max_level

        return stats


if __name__ == "__main__":
    # Test with sample data
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/dap.db"

    print(f"\n{'='*60}")
    print(f"Group Hierarchy Manager Test")
    print(f"{'='*60}\n")

    with GroupHierarchyManager(db_path) as manager:
        # Get statistics
        stats = manager.get_statistics("default_project")
        print(f"Hierarchy Statistics:")
        print(f"  Total Entities: {stats.get('total_entities', 0)}")
        print(f"  Max Depth: {stats.get('max_depth', 0)}")
        print(f"  By Level: {stats.get('by_level', {})}")
        print(f"  By Type: {stats.get('by_type', {})}")
