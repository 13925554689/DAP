"""
DAP v2.0 - Database Initialization Script
==========================================
This script initializes the database schema and loads initial data.
Supports both PostgreSQL and SQLite.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from models.database import Base, get_engine
from models.user import User, Role, Permission
from models.project import Project
from models.client import Client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def read_sql_file(filepath: str) -> str:
    """读取SQL文件内容"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def convert_postgres_to_sqlite(sql: str) -> str:
    """转换PostgreSQL语法到SQLite兼容语法"""
    # UUID -> TEXT
    sql = sql.replace('UUID', 'TEXT')
    sql = sql.replace('gen_random_uuid()', "lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))")

    # TIMESTAMP -> DATETIME
    sql = sql.replace('TIMESTAMP', 'DATETIME')
    sql = sql.replace('CURRENT_TIMESTAMP', "datetime('now')")

    # BOOLEAN -> INTEGER
    sql = sql.replace('BOOLEAN DEFAULT TRUE', 'INTEGER DEFAULT 1')
    sql = sql.replace('BOOLEAN DEFAULT FALSE', 'INTEGER DEFAULT 0')
    sql = sql.replace('BOOLEAN', 'INTEGER')

    # Remove CHECK constraints with regex (SQLite doesn't support all CHECK syntax)
    import re
    sql = re.sub(r',\s*CONSTRAINT\s+check_\w+\s+CHECK\s+\([^)]+\)', '', sql, flags=re.IGNORECASE)

    # Remove ON DELETE CASCADE (SQLite supports it but let's simplify)
    # sql = sql.replace('ON DELETE CASCADE', '')

    # Remove PostgreSQL-specific functions
    sql = sql.replace("~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}$'", "LIKE '%@%.%'")

    # Remove triggers and functions (will handle separately)
    sql = re.sub(r'CREATE OR REPLACE FUNCTION.*?language.*?;', '', sql, flags=re.DOTALL | re.IGNORECASE)
    sql = re.sub(r'CREATE TRIGGER.*?;', '', sql, flags=re.IGNORECASE)

    # Remove COMMENT statements
    sql = re.sub(r'COMMENT ON.*?;', '', sql, flags=re.IGNORECASE)

    return sql


def execute_sql_file(engine, filepath: str, use_sqlite: bool = True):
    """执行SQL文件"""
    logger.info(f"Executing SQL file: {filepath}")

    sql = read_sql_file(filepath)

    if use_sqlite and 'sqlite' in str(engine.url):
        logger.info("Converting PostgreSQL syntax to SQLite...")
        sql = convert_postgres_to_sqlite(sql)

    # Split by semicolon and execute each statement
    statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]

    with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            if not stmt:
                continue
            try:
                conn.execute(text(stmt))
                logger.debug(f"Executed statement {i}/{len(statements)}")
            except Exception as e:
                logger.error(f"Error executing statement {i}: {stmt[:100]}...")
                logger.error(f"Error: {e}")
                # Continue with other statements
                continue


def init_database(drop_existing: bool = False, use_orm: bool = True):
    """
    初始化数据库

    Args:
        drop_existing: 是否删除已有数据库
        use_orm: 是否使用ORM创建表（推荐），否则使用SQL文件
    """
    logger.info("=" * 60)
    logger.info("DAP v2.0 Database Initialization")
    logger.info("=" * 60)

    # Get database engine
    engine = get_engine()
    logger.info(f"Database URL: {engine.url}")

    # Drop existing tables if requested
    if drop_existing:
        logger.warning("Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("All tables dropped.")

    # Create tables using ORM
    if use_orm:
        logger.info("Creating tables using SQLAlchemy ORM...")
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created successfully!")

        # Load initial data
        load_initial_data(engine)
    else:
        # Alternative: Execute SQL files directly
        logger.info("Creating tables using SQL files...")
        schema_dir = Path(__file__).parent.parent / 'database' / 'schemas'

        sql_files = [
            '01_users_permissions.sql',
            '02_project_management.sql',
            '03_client_organization.sql',
            '04_data_import_mapping.sql',
            '05_financial_data.sql',
            '06_audit_workpaper.sql',
            '07_consolidation.sql',
            '08_review_workflow.sql',
            '09_audit_trail.sql',
            '10_template_enhancement.sql',
        ]

        for sql_file in sql_files:
            filepath = schema_dir / sql_file
            if filepath.exists():
                execute_sql_file(engine, str(filepath), use_sqlite='sqlite' in str(engine.url))
            else:
                logger.warning(f"SQL file not found: {filepath}")

    logger.info("=" * 60)
    logger.info("Database initialization completed successfully!")
    logger.info("=" * 60)


def load_initial_data(engine):
    """加载初始数据（仅ORM模式）"""
    logger.info("Loading initial data...")

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Check if roles already exist
        existing_roles = session.query(Role).count()
        if existing_roles > 0:
            logger.info(f"Initial data already loaded ({existing_roles} roles found). Skipping...")
            return

        # Create default roles
        roles = [
            Role(
                role_name='审计员',
                role_code='auditor',
                description='初级审计人员,负责具体审计工作',
                level=1
            ),
            Role(
                role_name='项目组长',
                role_code='senior',
                description='高级审计员,负责审计组管理',
                level=2
            ),
            Role(
                role_name='项目经理',
                role_code='manager',
                description='审计项目经理,负责整体项目管理和一级复核',
                level=3
            ),
            Role(
                role_name='合伙人',
                role_code='partner',
                description='签字合伙人,负责最终审计意见和风险控制',
                level=4
            ),
        ]

        session.add_all(roles)
        session.commit()
        logger.info(f"Created {len(roles)} default roles")

        # Create default permissions
        permissions_data = [
            # 项目管理权限
            ('创建项目', 'project_create', 'project', 'create', '创建新的审计项目'),
            ('查看项目', 'project_read', 'project', 'read', '查看审计项目信息'),
            ('编辑项目', 'project_update', 'project', 'update', '编辑审计项目信息'),
            ('删除项目', 'project_delete', 'project', 'delete', '删除审计项目'),
            ('项目审批', 'project_approve', 'project', 'approve', '审批项目立项/结案'),
            # 底稿管理权限
            ('创建底稿', 'workpaper_create', 'workpaper', 'create', '创建审计底稿'),
            ('查看底稿', 'workpaper_read', 'workpaper', 'read', '查看审计底稿'),
            ('编辑底稿', 'workpaper_update', 'workpaper', 'update', '编辑审计底稿'),
            ('删除底稿', 'workpaper_delete', 'workpaper', 'delete', '删除审计底稿'),
            # 复核权限
            ('一级复核', 'review_level1', 'review', 'approve', '项目组长复核'),
            ('二级复核', 'review_level2', 'review', 'approve', '项目经理复核'),
            ('三级复核', 'review_level3', 'review', 'approve', '合伙人复核'),
            # 合并报表权限
            ('查看合并报表', 'consolidation_read', 'consolidation', 'read', '查看合并报表'),
            ('编辑抵消分录', 'consolidation_update', 'consolidation', 'update', '编辑抵消分录'),
            ('生成合并报表', 'consolidation_generate', 'consolidation', 'create', '生成合并报表'),
        ]

        permissions = []
        for perm_data in permissions_data:
            perm = Permission(
                permission_name=perm_data[0],
                permission_code=perm_data[1],
                module=perm_data[2],
                action=perm_data[3],
                description=perm_data[4]
            )
            permissions.append(perm)

        session.add_all(permissions)
        session.commit()
        logger.info(f"Created {len(permissions)} default permissions")

        # Assign permissions to roles
        # TODO: Implement role-permission associations
        # This requires the role_permissions association table to be properly set up

        logger.info("Initial data loaded successfully!")

    except Exception as e:
        logger.error(f"Error loading initial data: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def verify_database():
    """验证数据库结构"""
    logger.info("Verifying database structure...")

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Test queries
        role_count = session.query(Role).count()
        perm_count = session.query(Permission).count()

        logger.info(f"✓ Roles table: {role_count} records")
        logger.info(f"✓ Permissions table: {perm_count} records")

        # List all roles
        roles = session.query(Role).all()
        logger.info("\nDefault Roles:")
        for role in roles:
            logger.info(f"  - {role.role_name} ({role.role_code}) - Level {role.level}")

        logger.info("\nDatabase verification completed successfully!")

    except Exception as e:
        logger.error(f"Database verification failed: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Initialize DAP v2.0 Database')
    parser.add_argument('--drop', action='store_true', help='Drop existing tables before creating')
    parser.add_argument('--sql', action='store_true', help='Use SQL files instead of ORM')
    parser.add_argument('--verify', action='store_true', help='Only verify database structure')

    args = parser.parse_args()

    try:
        if args.verify:
            verify_database()
        else:
            init_database(drop_existing=args.drop, use_orm=not args.sql)
            verify_database()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)
