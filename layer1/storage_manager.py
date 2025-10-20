"""
DAP - 存储管理器
基于SQLite的科学数据存储与多维视图管理
"""

import sqlite3
import pandas as pd
import numpy as np
import json
import os
import calendar
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import sys
import time
from math import ceil
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.validators import SQLQueryValidator
from utils.connection_pool import get_connection_pool

logger = logging.getLogger(__name__)

class StorageManager:
    """科学存储管理器 - 基于SQLite"""

    PROJECTS_TABLE_NAME = "dap_projects"
    DEFAULT_PROJECT_STATUS = "new"
    DEFAULT_PROJECT_ID = "default_project"
    DEFAULT_PROJECT_NAME = "默认项目"

    COLUMN_SYNONYMS = {
        "entity_name": [
            "entity_name",
            "company",
            "company_name",
            "单位名称",
            "客户名称",
            "企业名称",
            "customer_name",
            "client_name",
        ],
        "entity_code": [
            "entity_code",
            "company_code",
            "customer_id",
            "客户编号",
            "单位编码",
            "企业编码",
        ],
        "voucher_number": [
            "voucher_no",
            "voucher_number",
            "凭证号",
            "凭证编号",
            "document_no",
            "doc_no",
            "凭证号码",
            "单据号",
        ],
        "voucher_date": [
            "voucher_date",
            "date",
            "凭证日期",
            "记账日期",
            "单据日期",
            "会计日期",
            "过账日期",
        ],
        "summary": [
            "summary",
            "description",
            "memo",
            "remark",
            "摘要",
            "说明",
            "用途",
        ],
        "account_code": [
            "account_code",
            "account",
            "account_id",
            "account_no",
            "科目编码",
            "科目代号",
            "会计科目",
            "subject_code",
            "科目号",
        ],
        "account_name": [
            "account_name",
            "科目名称",
            "account_desc",
            "account_description",
            "subject_name",
            "科目",
            "会计科目名称",
        ],
        "debit_amount": [
            "debit",
            "debit_amount",
            "借方",
            "借方金额",
            "借记",
            "借记金额",
        ],
        "credit_amount": [
            "credit",
            "credit_amount",
            "贷方",
            "贷方金额",
            "贷记",
            "贷记金额",
        ],
        "amount": [
            "amount",
            "金额",
            "发生额",
            "balance",
            "total",
            "合计",
        ],
        "currency": [
            "currency",
            "币种",
            "currency_code",
            "currency_name",
        ],
        "attachment_path": [
            "attachment",
            "attachment_path",
            "附件",
            "附件路径",
            "file_path",
            "原始单据",
            "document_path",
            "image_path",
        ],
        "attachment_desc": [
            "attachment_desc",
            "附件说明",
            "附件描述",
            "附件备注",
            "原始单据备注",
        ],
        "fiscal_year": [
            "fiscal_year",
            "year",
            "年度",
            "会计年度",
            "financial_year",
        ],
        "fiscal_period": [
            "fiscal_period",
            "period",
            "月份",
            "会计期间",
            "期数",
            "month",
        ],
    }

    DEFAULT_ENTITY_NAME = "Default Entity"
    DEFAULT_ENTITY_CODE = "ENTITY-0000"
    
    def __init__(self, db_path: str = 'data/dap_data.db'):
        self.db_path = db_path
        self.base_db_path = db_path
        self.current_project_id: Optional[str] = None

        # ȷ������Ŀ¼����
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # ʹ�����ӳع������ݿ�����
        self.connection_pool = get_connection_pool(db_path)

        # Ϊ�洢����������һ���־����ӣ����ⱻ���ӳػ���
        self.conn = sqlite3.connect(
            db_path,
            timeout=30,
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row

        # Ӧ��SQLite�����Ż�
        self._optimize_sqlite()

        # ��ʼ�����ݿ�ṹ
        self.setup_database_structure()

        # ����ͳһ���������ά�ȡ���ʵ��
        self._ensure_unified_schema()

        # ȷ����Ŀ������ر��ṹ
        self._ensure_project_schema()
        self._ensure_default_project()
        self.set_current_project(self.DEFAULT_PROJECT_ID)

        logger.info(f"�洢��������ʼ����ɣ����ݿ�·��: {db_path}")
    
    def _optimize_sqlite(self):
        """优化SQLite设置"""
        optimizations = [
            "PRAGMA journal_mode=WAL",  # 写前日志模式，提高并发性能
            "PRAGMA synchronous=NORMAL",  # 平衡安全性和性能
            "PRAGMA cache_size=20000",  # 增加缓存大小（提升到20MB）
            "PRAGMA foreign_keys=ON",  # 启用外键约束
            "PRAGMA temp_store=memory",  # 临时表存储在内存
            "PRAGMA mmap_size=268435456",  # 启用内存映射IO（256MB）
            "PRAGMA page_size=4096",  # 优化页面大小
            "PRAGMA auto_vacuum=INCREMENTAL",  # 增量清理
            "PRAGMA optimize"  # 自动优化
        ]
        
        for pragma in optimizations:
            try:
                self.conn.execute(pragma)
                logger.debug(f"SQLite优化设置: {pragma}")
            except Exception as e:
                logger.warning(f"SQLite优化失败: {pragma} - {e}")
        
        # 设置连接超时
        self.conn.execute("PRAGMA busy_timeout=30000")  # 30秒超时
    
    def _column_exists(self, table: str, column: str) -> bool:
        """检查指定表是否存在给定列。"""
        try:
            info = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        except Exception as exc:
            logger.warning("无法检查列 %s.%s: %s", table, column, exc)
            return False
        return any(row[1] == column for row in info)

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        """在列不存在时尝试新增列。"""
        if self._column_exists(table, column):
            return
        try:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            logger.info("为表 %s 添加列 %s", table, column)
        except Exception as exc:
            logger.warning("添加列失败 %s.%s: %s", table, column, exc)

    def _ensure_project_schema(self) -> None:
        """确保项目管理相关的表结构和索引存在。"""
        try:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dap_projects (
                    project_id TEXT PRIMARY KEY,
                    project_code TEXT,
                    project_name TEXT NOT NULL,
                    client_name TEXT,
                    fiscal_year TEXT,
                    fiscal_period TEXT,
                    status TEXT DEFAULT 'new',
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settings TEXT
                )
                """
            )
        except Exception as exc:
            logger.error("创建项目主表失败: %s", exc)
            return

        project_column_targets = {
            "meta_tables": "TEXT",
            "meta_columns": "TEXT",
            "meta_relationships": "TEXT",
            "meta_companies": "TEXT",
            "meta_projects": "TEXT",
            "meta_views": "TEXT",
            "meta_dimensions": "TEXT",
            "audit_documents": "TEXT",
            "audit_document_versions": "TEXT",
            "attachments": "TEXT",
            "attachment_links": "TEXT",
            "attachment_ocr_results": "TEXT",
            "dim_entities": "TEXT",
            "dim_periods": "TEXT",
            "dim_accounts": "TEXT",
            "fact_vouchers": "TEXT",
            "fact_entries": "TEXT",
            "fact_attachments": "TEXT",
        }

        for table, column_type in project_column_targets.items():
            if not self._table_exists(table):
                continue
            self._add_column_if_missing(table, "project_id", column_type)

        index_targets = [
            "meta_tables",
            "meta_columns",
            "meta_relationships",
            "meta_views",
            "audit_documents",
            "attachments",
            "dim_entities",
            "dim_periods",
            "dim_accounts",
            "fact_vouchers",
            "fact_entries",
            "fact_attachments",
        ]

        for table in index_targets:
            if not self._table_exists(table):
                continue
            try:
                self.conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_project ON {table}(project_id)"
                )
            except Exception as exc:
                logger.warning("创建项目索引失败 %s: %s", table, exc)

        try:
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_dap_projects_code ON dap_projects(project_code)"
            )
        except Exception as exc:
            logger.warning("创建项目编码索引失败: %s", exc)

        self.conn.commit()
    
    def _ensure_default_project(self) -> None:
        """确保默认项目存在。"""
        try:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO dap_projects
                (project_id, project_code, project_name, status, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.DEFAULT_PROJECT_ID,
                    self.DEFAULT_PROJECT_ID,
                    self.DEFAULT_PROJECT_NAME,
                    self.DEFAULT_PROJECT_STATUS,
                    "system",
                ),
            )
            self.conn.commit()
        except Exception as exc:
            logger.warning("初始化默认项目失败: %s", exc)

    def list_projects(self) -> List[Dict[str, Any]]:
        """列出所有项目。"""
        query = """
            SELECT project_id, project_code, project_name, client_name,
                   fiscal_year, fiscal_period, status, created_by,
                   created_at, updated_at, settings
            FROM dap_projects
            ORDER BY created_at DESC
        """
        rows = self.conn.execute(query).fetchall()
        projects: List[Dict[str, Any]] = []
        for row in rows:
            projects.append(
                {
                    "project_id": row["project_id"],
                    "project_code": row["project_code"],
                    "project_name": row["project_name"],
                    "client_name": row["client_name"],
                    "fiscal_year": row["fiscal_year"],
                    "fiscal_period": row["fiscal_period"],
                    "status": row["status"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "settings": row["settings"],
                }
            )
        return projects

    def get_project(self, identifier: str) -> Optional[Dict[str, Any]]:
        """根据项目ID或项目代码获取项目信息。"""
        query = """
            SELECT project_id, project_code, project_name, client_name,
                   fiscal_year, fiscal_period, status, created_by,
                   created_at, updated_at, settings
            FROM dap_projects
            WHERE project_id = ? OR project_code = ?
            LIMIT 1
        """
        row = self.conn.execute(query, (identifier, identifier)).fetchone()
        if not row:
            return None
        return {
            "project_id": row["project_id"],
            "project_code": row["project_code"],
            "project_name": row["project_name"],
            "client_name": row["client_name"],
            "fiscal_year": row["fiscal_year"],
            "fiscal_period": row["fiscal_period"],
            "status": row["status"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "settings": row["settings"],
        }

    def create_project(
        self,
        project_name: str,
        project_code: Optional[str] = None,
        client_name: Optional[str] = None,
        fiscal_year: Optional[str] = None,
        fiscal_period: Optional[str] = None,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建新项目并返回项目ID。"""
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        project_code = project_code or project_id
        status = status or self.DEFAULT_PROJECT_STATUS
        try:
            self.conn.execute(
                """
                INSERT INTO dap_projects
                (project_id, project_code, project_name, client_name,
                 fiscal_year, fiscal_period, status, created_by, settings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    project_code,
                    project_name,
                    client_name,
                    fiscal_year,
                    fiscal_period,
                    status,
                    created_by,
                    self._safe_json_dumps(settings) if settings else None,
                ),
            )
            self.conn.commit()
            return project_id
        except Exception as exc:
            logger.error("创建项目失败: %s", exc)
            raise

    def set_current_project(self, identifier: str) -> None:
        """将指定项目设置为当前项目。"""
        project = self.get_project(identifier)
        if not project:
            raise ValueError(f"项目未找到: {identifier}")
        self.current_project_id = project["project_id"]
        logger.info("当前项目已切换至: %s (%s)", project["project_name"], self.current_project_id)

    def get_current_project_id(self) -> str:
        """获取当前项目ID。"""
        return self.current_project_id or self.DEFAULT_PROJECT_ID

    def get_current_project(self) -> Dict[str, Any]:
        """获取当前项目详情。"""
        project = self.get_project(self.get_current_project_id())
        if not project:
            return {
                "project_id": self.DEFAULT_PROJECT_ID,
                "project_code": self.DEFAULT_PROJECT_ID,
                "project_name": self.DEFAULT_PROJECT_NAME,
                "status": self.DEFAULT_PROJECT_STATUS,
            }
        return project

    def _project_token(self) -> str:
        """获取当前项目用于命名的安全标识。"""
        return self._sanitize_name(self.get_current_project_id())

    def _project_scoped_table_name(self, prefix: str, original_name: str) -> str:
        """基于项目范围构造存储使用的表名。"""
        return f"{prefix}_{self._project_token()}_{self._sanitize_name(original_name)}"

    
    def setup_database_structure(self):
        """设置数据库结构"""
        logger.info("初始化数据库结构")
        
        # 创建元数据表
        self._create_metadata_tables()
        
        # 创建视图管理表
        self._create_view_management_tables()
        self._create_document_management_tables()
        
        logger.info("数据库结构初始化完成")
    
    def _create_metadata_tables(self):
        """创建元数据表"""
        metadata_tables = {
            'meta_tables': '''
                CREATE TABLE IF NOT EXISTS meta_tables (
                    table_name TEXT PRIMARY KEY,
                    original_name TEXT,
                    table_type TEXT,
                    business_domain TEXT,
                    row_count INTEGER,
                    column_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    schema_info TEXT,
                    data_quality_score REAL
                )
            ''',
            
            'meta_columns': '''
                CREATE TABLE IF NOT EXISTS meta_columns (
                    table_name TEXT,
                    column_name TEXT,
                    column_type TEXT,
                    data_type TEXT,
                    business_meaning TEXT,
                    null_ratio REAL,
                    unique_ratio REAL,
                    sample_values TEXT,
                    is_primary_key BOOLEAN DEFAULT FALSE,
                    is_foreign_key BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (table_name, column_name),
                    FOREIGN KEY (table_name) REFERENCES meta_tables(table_name)
                )
            ''',
            
            'meta_relationships': '''
                CREATE TABLE IF NOT EXISTS meta_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_table TEXT,
                    from_column TEXT,
                    to_table TEXT,
                    to_column TEXT,
                    relationship_type TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_table) REFERENCES meta_tables(table_name),
                    FOREIGN KEY (to_table) REFERENCES meta_tables(table_name)
                )
            ''',
            
            'meta_companies': '''
                CREATE TABLE IF NOT EXISTS meta_companies (
                    company_id TEXT PRIMARY KEY,
                    company_name TEXT,
                    company_code TEXT,
                    industry TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            
            'meta_projects': '''
                CREATE TABLE IF NOT EXISTS meta_projects (
                    project_id TEXT PRIMARY KEY,
                    project_name TEXT,
                    project_code TEXT,
                    company_id TEXT,
                    project_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES meta_companies(company_id)
                )
            '''
        }
        
        for table_name, create_sql in metadata_tables.items():
            try:
                self.conn.execute(create_sql)
                logger.info(f"创建元数据表: {table_name}")
            except Exception as e:
                logger.error(f"创建元数据表失败 {table_name}: {e}")
        
        self.conn.commit()
    
    def _create_document_management_tables(self):
        """Create document and attachment tables for audit workflow."""
        document_tables = {
            'audit_documents': '''
                CREATE TABLE IF NOT EXISTS audit_documents (
                    document_id TEXT PRIMARY KEY,
                    doc_type TEXT,
                    project_id TEXT,
                    company_id TEXT,
                    template_name TEXT,
                    status TEXT DEFAULT 'draft',
                    storage_path TEXT,
                    checksum TEXT,
                    format TEXT,
                    generated_by TEXT,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (project_id) REFERENCES meta_projects(project_id),
                    FOREIGN KEY (company_id) REFERENCES meta_companies(company_id)
                )
            ''',
            'audit_document_versions': '''
                CREATE TABLE IF NOT EXISTS audit_document_versions (
                    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT,
                    version_number INTEGER,
                    storage_path TEXT,
                    checksum TEXT,
                    format TEXT,
                    notes TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (document_id) REFERENCES audit_documents(document_id)
                )
            ''',
            'attachments': '''
                CREATE TABLE IF NOT EXISTS attachments (
                    attachment_id TEXT PRIMARY KEY,
                    source_table TEXT,
                    source_record_id TEXT,
                    voucher_id TEXT,
                    category TEXT,
                    file_name TEXT,
                    storage_path TEXT,
                    storage_backend TEXT DEFAULT 'local',
                    mime_type TEXT,
                    file_size INTEGER,
                    checksum TEXT,
                    encryption_key_id TEXT,
                    upload_status TEXT DEFAULT 'pending',
                    uploaded_by TEXT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            ''',
            'attachment_links': '''
                CREATE TABLE IF NOT EXISTS attachment_links (
                    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attachment_id TEXT,
                    target_table TEXT,
                    target_record_id TEXT,
                    relation_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (attachment_id) REFERENCES attachments(attachment_id)
                )
            ''',
            'attachment_ocr_results': '''
                CREATE TABLE IF NOT EXISTS attachment_ocr_results (
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attachment_id TEXT,
                    ocr_text TEXT,
                    ocr_metadata TEXT,
                    processor_version TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    confidence REAL,
                    FOREIGN KEY (attachment_id) REFERENCES attachments(attachment_id)
                )
            '''
        }

        for table_name, create_sql in document_tables.items():
            try:
                self.conn.execute(create_sql)
                logger.info(f"Document table ensured: {table_name}")
            except Exception as e:
                logger.error(f"Document table creation failed {table_name}: {e}")

        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_audit_documents_project ON audit_documents(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_documents_type ON audit_documents(doc_type)",
            "CREATE INDEX IF NOT EXISTS idx_audit_document_versions_doc ON audit_document_versions(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_attachments_voucher ON attachments(voucher_id)",
            "CREATE INDEX IF NOT EXISTS idx_attachments_record ON attachments(source_table, source_record_id)",
            "CREATE INDEX IF NOT EXISTS idx_attachment_links_target ON attachment_links(target_table, target_record_id)",
            "CREATE INDEX IF NOT EXISTS idx_attachment_ocr_results_attachment ON attachment_ocr_results(attachment_id)"
        ]

        for index_sql in index_statements:
            try:
                self.conn.execute(index_sql)
                logger.debug(f"Create index: {index_sql}")
            except Exception as e:
                logger.warning(f"Index creation failed {index_sql}: {e}")

        self.conn.commit()
    
    def _create_view_management_tables(self):
        """创建视图管理表"""
        view_tables = {
            'meta_views': '''
                CREATE TABLE IF NOT EXISTS meta_views (
                    view_name TEXT,
                    project_id TEXT,
                    view_type TEXT,
                    base_tables TEXT,
                    dimension_key TEXT,
                    dimension_value TEXT,
                    sql_definition TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_refreshed TIMESTAMP,
                    PRIMARY KEY (view_name, project_id)
                )
            ''',
            
            'meta_dimensions': '''
                CREATE TABLE IF NOT EXISTS meta_dimensions (
                    dimension_name TEXT PRIMARY KEY,
                    dimension_type TEXT,
                    description TEXT,
                    column_mapping TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''
        }
        
        for table_name, create_sql in view_tables.items():
            try:
                self.conn.execute(create_sql)
                logger.info(f"创建视图管理表: {table_name}")
            except Exception as e:
                logger.error(f"创建视图管理表失败 {table_name}: {e}")
        
        self.conn.commit()
    
    def store_cleaned_data(self, cleaned_data: Dict[str, pd.DataFrame], 
                          schema: Dict[str, Any]) -> bool:
        """存储清洗后的数据"""
        logger.info("开始存储清洗后的数据")
        
        try:
            current_project = self.get_current_project_id()
            project_tables: Dict[str, str] = {}
            for table_name, table_data in cleaned_data.items():
                logger.info(f"存储表: {table_name}")
                
                # 1. 存储原始清洗数据到raw_clean表
                storage_table_name = self._project_scoped_table_name('raw_clean', table_name)

                self._store_table_data(storage_table_name, table_data, current_project)
                self._create_project_table_alias(
                    f"raw_clean_{self._sanitize_name(table_name)}",
                    storage_table_name,
                    current_project,
                )
                project_tables[table_name] = storage_table_name

                
                # 2. 存储元数据
                table_schema = schema.get(table_name, {})
                self._store_table_metadata(
                    storage_table_name,
                    table_name,
                    table_data,
                    table_schema,
                    current_project,
                )
                
                # 3. 检测并存储公司信息
                companies = self._detect_companies(table_data)
                for company in companies:
                    self._store_company_metadata(company)
                
                # 4. 检测并存储项目信息
                projects = self._detect_projects(table_data)
                for project in projects:
                    self._store_project_metadata(project)
            
            # 5. 创建多维度视图
            self._create_dimensional_views(cleaned_data, project_tables, current_project)

            # 6. 构建统一数据模型并生成钻取视图
            self._build_and_store_unified_model(cleaned_data, schema, current_project)
            
            # 7. 建立索引优化查询
            self._create_indexes()
            
            logger.info("数据存储完成")
            return True
            
        except Exception as e:
            logger.error(f"数据存储失败: {e}")
            self.conn.rollback()
            return False
    
    def _store_table_data(self, table_name: str, data: pd.DataFrame, project_id: str):
        """存储表数据，按项目追加写入。"""
        try:
            frame = data.copy()
            if project_id:
                frame["project_id"] = project_id

            if self._table_exists(table_name):
                try:
                    if project_id and self._column_exists(table_name, "project_id"):
                        self.conn.execute(
                            f"DELETE FROM {table_name} WHERE project_id = ?",
                            (project_id,),
                        )
                    else:
                        self.conn.execute(f"DELETE FROM {table_name}")
                except Exception as exc:
                    logger.warning("清理表 %s 旧数据失败: %s", table_name, exc)

            frame.to_sql(
                table_name,
                self.conn,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=1000,
            )
            logger.info("表 %s 存储完成（项目 %s），共 %d 行", table_name, project_id, len(frame))

        except Exception as exc:
            logger.error("存储表数据失败 %s: %s", table_name, exc)
            raise
    
    def _create_project_table_alias(
        self, alias_name: str, storage_table: str, project_id: str
    ) -> None:
        """为项目数据创建兼容视图别名。"""
        try:
            self.conn.execute(f"DROP VIEW IF EXISTS {alias_name}")
            alias_sql = f"""
                CREATE VIEW IF NOT EXISTS {alias_name} AS
                SELECT *
                FROM {storage_table}
                WHERE project_id = '{project_id}'
            """
            self.conn.execute(alias_sql)
        except Exception as exc:
            logger.warning("创建项目视图别名失败 %s -> %s: %s", alias_name, storage_table, exc)
    
    def _store_table_metadata(
        self,
        storage_table_name: str,
        original_table_name: str,
        data: pd.DataFrame,
        schema: Dict[str, Any],
        project_id: str,
    ):
        """存储表元数据（按项目划分）。"""
        try:
            quality_score = self._calculate_quality_score(data, schema)
            business_meaning = schema.get("business_meaning", {})

            table_meta_sql = """
                INSERT OR REPLACE INTO meta_tables
                (table_name, project_id, original_name, table_type, business_domain,
                 row_count, column_count, schema_info, data_quality_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            self.conn.execute(
                table_meta_sql,
                (
                    storage_table_name,
                    project_id,
                    original_table_name,
                    business_meaning.get("table_type", "unknown"),
                    business_meaning.get("business_domain", "general"),
                    len(data),
                    len(data.columns),
                    self._safe_json_dumps(schema),
                    quality_score,
                ),
            )

            columns_info = schema.get("columns", {})
            primary_keys = schema.get("primary_keys", [])

            delete_columns_sql = (
                "DELETE FROM meta_columns WHERE table_name = ? AND project_id = ?"
            )
            self.conn.execute(delete_columns_sql, (storage_table_name, project_id))

            column_meta_sql = """
                INSERT INTO meta_columns
                (table_name, project_id, column_name, column_type, data_type,
                 business_meaning, null_ratio, unique_ratio, sample_values, is_primary_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            column_data = []
            for column in data.columns:
                column_info = columns_info.get(column, {})
                null_ratio = (
                    data[column].isnull().sum() / len(data) if len(data) > 0 else 0.0
                )
                unique_ratio = (
                    data[column].nunique() / len(data) if len(data) > 0 else 0.0
                )
                sample_values = self._safe_sample_values(data[column])
                column_data.append(
                    (
                        storage_table_name,
                        project_id,
                        column,
                        column_info.get("type", "unknown"),
                        str(data[column].dtype),
                        self._get_column_business_meaning(column, business_meaning),
                        null_ratio,
                        unique_ratio,
                        self._safe_json_dumps(sample_values),
                        1 if column in primary_keys else 0,
                    )
                )

            if column_data:
                self.conn.executemany(column_meta_sql, column_data)

            relationships = schema.get("relationships", [])
            if relationships:
                rel_delete_sql = (
                    "DELETE FROM meta_relationships WHERE from_table = ? AND project_id = ?"
                )
                self.conn.execute(rel_delete_sql, (storage_table_name, project_id))

                rel_sql = """
                    INSERT OR REPLACE INTO meta_relationships
                    (from_table, project_id, from_column, to_table, to_column, relationship_type, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """

                for rel in relationships:
                    to_table = rel.get("to_table")
                    if not to_table:
                        continue
                    self.conn.execute(
                        rel_sql,
                        (
                            storage_table_name,
                            project_id,
                            rel.get("from_column"),
                            to_table,
                            rel.get("to_column"),
                            rel.get("relationship_type", "foreign_key"),
                            rel.get("confidence", 0.0),
                        ),
                    )

            self.conn.commit()

        except Exception as exc:
            logger.error("存储表元数据失败 %s: %s", storage_table_name, exc)
            raise
    
    def _calculate_quality_score(self, data: pd.DataFrame, schema: Dict[str, Any]) -> float:
        """计算数据质量评分（0-1）"""
        scores = []
        
        # 完整性评分（空值比例）
        null_ratio = data.isnull().sum().sum() / data.size if data.size > 0 else 1
        completeness_score = 1 - null_ratio
        scores.append(completeness_score * 0.3)
        
        # 唯一性评分（重复行比例）
        duplicate_ratio = data.duplicated().sum() / len(data) if len(data) > 0 else 0
        uniqueness_score = 1 - duplicate_ratio
        scores.append(uniqueness_score * 0.2)
        
        # 一致性评分（数据类型一致性）
        consistency_score = 1.0  # 简化实现
        scores.append(consistency_score * 0.2)
        
        # 准确性评分（基于业务规则验证）
        accuracy_score = 0.8  # 简化实现
        scores.append(accuracy_score * 0.3)
        
        return sum(scores)
    
    def _safe_sample_values(self, series: pd.Series, max_samples: int = 5) -> List[Any]:
        """安全获取样本值，确保JSON可序列化"""
        try:
            # 获取非空样本值
            sample_values = series.dropna().head(max_samples).tolist()
            
            # 转换为JSON安全的格式
            safe_values = []
            for value in sample_values:
                if pd.isna(value):
                    safe_values.append(None)
                elif isinstance(value, (bool, np.bool_)):
                    safe_values.append(bool(value))
                elif isinstance(value, (int, np.integer)):
                    safe_values.append(int(value))
                elif isinstance(value, (float, np.floating)):
                    if np.isnan(value) or np.isinf(value):
                        safe_values.append(None)
                    else:
                        safe_values.append(float(value))
                elif isinstance(value, (str, np.str_)):
                    safe_values.append(str(value))
                elif hasattr(value, 'isoformat'):  # datetime
                    safe_values.append(value.isoformat())
                else:
                    # 对于其他类型，尝试转换为字符串
                    safe_values.append(str(value))
            
            return safe_values
            
        except Exception as e:
            logger.warning(f"获取样本值失败: {e}")
            return []
    
    def _safe_json_dumps(self, obj: Any) -> str:
        """安全的JSON序列化，处理不可序列化对象"""
        try:
            # 先通过自定义处理器预处理对象
            safe_obj = self._make_json_safe(obj)
            return json.dumps(safe_obj, ensure_ascii=False, allow_nan=False)
        except Exception as e:
            logger.warning(f"JSON序列化失败: {e}")
            return "{}"
    
    def _make_json_safe(self, obj):
        """递归地使对象JSON安全"""
        if obj is None:
            return None
        elif obj is np.nan or obj is np.inf or obj is -np.inf:
            return None
        elif isinstance(obj, dict):
            return {k: self._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        elif isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        elif isinstance(obj, (int, np.integer)):
            return int(obj)
        elif isinstance(obj, (float, np.floating)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, (str, np.str_)):
            return str(obj)
        elif hasattr(obj, 'isoformat'):  # datetime
            return obj.isoformat()
        else:
            # 对于标量值检查是否为NaN
            try:
                if pd.isna(obj):
                    return None
            except (TypeError, ValueError):
                pass
            return str(obj)
    
    def _json_default(self, obj):
        """JSON序列化的默认处理函数"""
        if pd.isna(obj):
            return None
        elif isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        elif isinstance(obj, (int, np.integer)):
            return int(obj)
        elif isinstance(obj, (float, np.floating)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif obj is np.nan:
            return None
        elif isinstance(obj, (str, np.str_)):
            return str(obj)
        elif hasattr(obj, 'isoformat'):  # datetime
            return obj.isoformat()
        else:
            return str(obj)
    
    def _get_column_business_meaning(self, column: str, business_meaning: Dict[str, Any]) -> str:
        """获取列的业务含义"""
        column_meanings = business_meaning.get('column_meanings', {})
        return column_meanings.get(column, 'unknown')
    
    def _detect_companies(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """检测数据中的公司信息"""
        companies = []
        
        # 查找包含公司信息的列
        company_columns = []
        for col in data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['公司', 'company', 'corp', '企业', '单位']):
                company_columns.append(col)
        
        # 提取公司信息
        for col in company_columns:
            unique_companies = data[col].dropna().unique()
            
            for company_name in unique_companies:
                if company_name and str(company_name).strip():
                    companies.append({
                        'company_id': self._generate_company_id(company_name),
                        'company_name': str(company_name).strip(),
                        'source_column': col
                    })
        
        return companies
    
    def _detect_projects(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """检测数据中的项目信息"""
        projects = []
        
        # 查找包含项目信息的列
        project_columns = []
        for col in data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['项目', 'project', 'proj', '工程']):
                project_columns.append(col)
        
        # 提取项目信息
        for col in project_columns:
            unique_projects = data[col].dropna().unique()
            
            for project_name in unique_projects:
                if project_name and str(project_name).strip():
                    projects.append({
                        'project_id': self._generate_project_id(project_name),
                        'project_name': str(project_name).strip(),
                        'source_column': col
                    })
        
        return projects
    
    def _generate_company_id(self, company_name: str) -> str:
        """生成公司ID"""
        # 简化实现：使用公司名的哈希值
        import hashlib
        return f"comp_{hashlib.md5(company_name.encode()).hexdigest()[:8]}"
    
    def _generate_project_id(self, project_name: str) -> str:
        """生成项目ID"""
        # 简化实现：使用项目名的哈希值
        import hashlib
        return f"proj_{hashlib.md5(project_name.encode()).hexdigest()[:8]}"
    
    def _store_company_metadata(self, company: Dict[str, Any]):
        """存储公司元数据"""
        try:
            project_id = self.get_current_project_id()
            company_sql = """
                INSERT OR IGNORE INTO meta_companies 
                (company_id, project_id, company_name)
                VALUES (?, ?, ?)
            """

            self.conn.execute(
                company_sql,
                (
                    company["company_id"],
                    project_id,
                    company["company_name"],
                ),
            )

        except Exception as exc:
            logger.warning("存储公司元数据失败: %s", exc)
    
    def _store_project_metadata(self, project: Dict[str, Any]):
        """存储项目元数据"""
        try:
            project_sql = '''
                INSERT OR IGNORE INTO meta_projects 
                (project_id, project_name, project_code)
                VALUES (?, ?, ?)
            '''
            
            self.conn.execute(
                project_sql,
                (
                    project["project_id"],
                    project["project_name"],
                    project.get("project_code"),
                ),
            )
            
        except Exception as exc:
            logger.warning("存储项目元数据失败: %s", exc)
    
    def _create_dimensional_views(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        project_tables: Dict[str, str],
        project_id: str,
    ):
        """创建多维度视图（按项目隔离）"""
        logger.info("创建多维度视图 (项目 %s)", project_id)
        self._create_company_views(cleaned_data, project_tables, project_id)
        self._create_project_views(cleaned_data, project_tables, project_id)
        self._create_temporal_views(cleaned_data, project_tables, project_id)
        self._create_business_views(cleaned_data, project_tables, project_id)

    def _create_company_views(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        project_tables: Dict[str, str],
        project_id: str,
    ):
        """创建公司维度视图"""
        for table_name, data in cleaned_data.items():
            storage_table = project_tables.get(table_name)
            if not storage_table:
                continue
            company_column = self._find_company_column(data)
            if not company_column:
                continue
            companies = data[company_column].dropna().unique()
            for company in companies:
                if not company or not str(company).strip():
                    continue
                safe_company_name = self._sanitize_name(str(company))
                safe_table_name = self._sanitize_name(table_name)
                view_name = (
                    f"view_{self._project_token()}_company_{safe_company_name}_{safe_table_name}"
                )
                try:
                    self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                    actual_sql = f"""
                        CREATE VIEW IF NOT EXISTS {view_name} AS
                        SELECT *
                        FROM {storage_table}
                        WHERE project_id = '{project_id}'
                          AND "{company_column}" = '{str(company).replace("'", "''")}'
                    """
                    self.conn.execute(actual_sql)
                    self._record_view_metadata(
                        view_name,
                        'company',
                        [storage_table],
                        company_column,
                        str(company),
                        project_id,
                        actual_sql.strip(),
                    )
                except Exception as exc:
                    logger.warning("创建公司视图失败 %s: %s", view_name, exc)

    def _create_project_views(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        project_tables: Dict[str, str],
        project_id: str,
    ):
        """创建项目维度视图"""
        for table_name, data in cleaned_data.items():
            storage_table = project_tables.get(table_name)
            if not storage_table:
                continue
            project_column = self._find_project_column(data)
            if not project_column:
                continue
            projects = data[project_column].dropna().unique()
            for project in projects:
                if not project or not str(project).strip():
                    continue
                safe_project_name = self._sanitize_name(str(project))
                safe_table_name = self._sanitize_name(table_name)
                view_name = (
                    f"view_{self._project_token()}_project_{safe_project_name}_{safe_table_name}"
                )
                try:
                    self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                    actual_sql = f"""
                        CREATE VIEW IF NOT EXISTS {view_name} AS
                        SELECT *
                        FROM {storage_table}
                        WHERE project_id = '{project_id}'
                          AND "{project_column}" = '{str(project).replace("'", "''")}'
                    """
                    self.conn.execute(actual_sql)
                    self._record_view_metadata(
                        view_name,
                        'project',
                        [storage_table],
                        project_column,
                        str(project),
                        project_id,
                        actual_sql.strip(),
                    )
                except Exception as exc:
                    logger.warning("创建项目视图失败 %s: %s", view_name, exc)
    def _create_temporal_views(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        project_tables: Dict[str, str],
        project_id: str,
    ):
        """创建时间维度视图"""
        for table_name, data in cleaned_data.items():
            storage_table = project_tables.get(table_name)
            if not storage_table:
                continue
            date_columns = self._find_date_columns(data)
            for date_column in date_columns:
                safe_table_name = self._sanitize_name(table_name)
                annual_view = f"view_{self._project_token()}_temporal_annual_{safe_table_name}"
                try:
                    self.conn.execute(f"DROP VIEW IF EXISTS {annual_view}")
                    annual_sql = f"""
                        CREATE VIEW IF NOT EXISTS {annual_view} AS
                        SELECT 
                            strftime('%Y', "{date_column}") as year,
                            COUNT(*) as record_count,
                            *
                        FROM {storage_table}
                        WHERE project_id = '{project_id}'
                          AND "{date_column}" IS NOT NULL
                        GROUP BY strftime('%Y', "{date_column}")
                    """
                    self.conn.execute(annual_sql)
                    self._record_view_metadata(
                        annual_view,
                        'temporal_annual',
                        [storage_table],
                        date_column,
                        'year',
                        project_id,
                        annual_sql.strip(),
                    )
                except Exception as exc:
                    logger.warning("创建年度视图失败 %s: %s", annual_view, exc)

                monthly_view = f"view_{self._project_token()}_temporal_monthly_{safe_table_name}"
                try:
                    self.conn.execute(f"DROP VIEW IF EXISTS {monthly_view}")
                    monthly_sql = f"""
                        CREATE VIEW IF NOT EXISTS {monthly_view} AS
                        SELECT 
                            strftime('%Y-%m', "{date_column}") as month,
                            COUNT(*) as record_count,
                            *
                        FROM {storage_table}
                        WHERE project_id = '{project_id}'
                          AND "{date_column}" IS NOT NULL
                        GROUP BY strftime('%Y-%m', "{date_column}")
                    """
                    self.conn.execute(monthly_sql)
                    self._record_view_metadata(
                        monthly_view,
                        'temporal_monthly',
                        [storage_table],
                        date_column,
                        'month',
                        project_id,
                        monthly_sql.strip(),
                    )
                except Exception as exc:
                    logger.warning("创建月度视图失败 %s: %s", monthly_view, exc)
    
    def _create_business_views(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        project_tables: Dict[str, str],
        project_id: str,
    ):
        """创建业务维度视图"""
        # 创建审计重点视图
        self._create_audit_focus_views(cleaned_data, project_tables, project_id)
        
        # 创建财务分析视图
        self._create_financial_analysis_views(cleaned_data, project_tables, project_id)
    
    def _create_audit_focus_views(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        project_tables: Dict[str, str],
        project_id: str,
    ):
        """创建重点视图"""
        try:
            candidates = []
            for table_name, data in cleaned_data.items():
                amount_columns = self._find_amount_columns(data)
                if amount_columns:
                    candidates.append((table_name, amount_columns[0]))
            if not candidates:
                return

            table_name, amount_column = candidates[0]
            storage_table = project_tables.get(table_name)
            if not storage_table:
                return

            view_name = f"view_{self._project_token()}_audit_high_risk_{self._sanitize_name(table_name)}"
            self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            risk_sql = f"""
                CREATE VIEW IF NOT EXISTS {view_name} AS
                SELECT *,
                    CASE 
                        WHEN "{amount_column}" > (SELECT AVG("{amount_column}") * 3 FROM {storage_table} WHERE project_id = '{project_id}') 
                        THEN 'HIGH_AMOUNT'
                        WHEN "{amount_column}" < 0 THEN 'NEGATIVE_AMOUNT'
                        ELSE 'NORMAL'
                    END as risk_flag
                FROM {storage_table}
                WHERE project_id = '{project_id}'
                  AND risk_flag != 'NORMAL'
            """
            self.conn.execute(risk_sql)
            self._record_view_metadata(
                view_name,
                'audit_risk',
                [storage_table],
                amount_column,
                'high_risk',
                project_id,
                risk_sql.strip(),
            )
            logger.info("创建高风险交易视图: %s", view_name)
        except Exception as exc:
            logger.warning("创建重点视图失败: %s", exc)

    def _create_financial_analysis_views(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        project_tables: Dict[str, str],
        project_id: str,
    ):
        """创建财务分析视图"""
        # 这里可以根据具体的财务数据创建分析视图
        # 例如：资产负债表视图、损益表视图等
        pass

    def _build_and_store_unified_model(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        schema: Dict[str, Any],
        project_id: str,
    ) -> None:
        """构建统一的数据模型并生成钻取视图。"""
        if not cleaned_data:
            return

        try:
            unified_data = self._build_unified_model(cleaned_data, schema or {}, project_id)
            if not unified_data:
                return

            self._store_unified_tables(unified_data, project_id)
            self._create_unified_views(project_id)
        except Exception as exc:
            logger.warning(f"构建统一数据模型失败: {exc}")

    def _build_unified_model(
        self,
        cleaned_data: Dict[str, pd.DataFrame],
        schema: Dict[str, Any],
        project_id: str,
    ) -> Dict[str, pd.DataFrame]:
        """根据清洗后的数据生成统一的维度、事实表。"""
        entities: List[Dict[str, Any]] = []
        periods: List[Dict[str, Any]] = []
        accounts: List[Dict[str, Any]] = []
        vouchers: List[Dict[str, Any]] = []
        entries: List[Dict[str, Any]] = []
        attachments: List[Dict[str, Any]] = []

        entity_index: Dict[str, int] = {}
        period_index: Dict[tuple, int] = {}
        account_index: Dict[tuple, int] = {}
        voucher_index: Dict[tuple, int] = {}
        voucher_totals: Dict[int, Dict[str, float]] = {}

        entity_counter = 1
        period_counter = 1
        account_counter = 1
        voucher_counter = 1
        entry_counter = 1
        attachment_counter = 1

        schema_tables = schema.get("tables", schema)

        for table_name, data in cleaned_data.items():
            if data is None or data.empty:
                continue

            table_schema = schema_tables.get(table_name, {})
            business_meaning = table_schema.get("business_meaning", {})
            table_type = business_meaning.get("table_type") or table_schema.get("table_type")
            default_entity_name = business_meaning.get(
                "entity_name", self.DEFAULT_ENTITY_NAME
            )
            default_entity_code = business_meaning.get(
                "entity_code", self.DEFAULT_ENTITY_CODE
            )

            df = data.copy()
            df.columns = [str(col) for col in df.columns]
            df.reset_index(drop=True, inplace=True)

            col_entity_name = self._detect_column(df.columns, "entity_name")
            col_entity_code = self._detect_column(df.columns, "entity_code")
            col_voucher_number = self._detect_column(df.columns, "voucher_number")
            col_voucher_date = self._detect_column(df.columns, "voucher_date")
            col_summary = self._detect_column(df.columns, "summary")
            col_account_code = self._detect_column(df.columns, "account_code")
            col_account_name = self._detect_column(df.columns, "account_name")
            col_debit = self._detect_column(df.columns, "debit_amount")
            col_credit = self._detect_column(df.columns, "credit_amount")
            col_amount = self._detect_column(df.columns, "amount")
            col_currency = self._detect_column(df.columns, "currency")
            col_attachment_path = self._detect_column(df.columns, "attachment_path")
            col_attachment_desc = self._detect_column(df.columns, "attachment_desc")
            col_year = self._detect_column(df.columns, "fiscal_year")
            col_period = self._detect_column(df.columns, "fiscal_period")

            for idx, row in df.iterrows():
                entity_name = self._safe_str(
                    row.get(col_entity_name), default_entity_name
                )
                entity_code = self._safe_str(
                    row.get(col_entity_code), default_entity_code
                )
                entity_key = entity_code or entity_name or self.DEFAULT_ENTITY_NAME

                if entity_key not in entity_index:
                    entity_id = entity_counter
                    entity_counter += 1
                    entity_index[entity_key] = entity_id
                    entities.append(
                        {
                            "project_id": project_id,
                            "entity_id": entity_id,
                            "entity_code": entity_code or None,
                            "entity_name": entity_name or self.DEFAULT_ENTITY_NAME,
                            "source_table": table_name,
                            "created_at": datetime.utcnow().isoformat(),
                        }
                    )
                entity_id = entity_index[entity_key]

                voucher_date = self._safe_datetime(row.get(col_voucher_date))
                fiscal_year, fiscal_period, period_start, period_end = (
                    self._derive_period_info(
                        voucher_date, row, col_year=col_year, col_period=col_period
                    )
                )
                period_key = (entity_id, fiscal_year, fiscal_period)
                if period_key not in period_index:
                    period_id = period_counter
                    period_counter += 1
                    period_index[period_key] = period_id
                    periods.append(
                        {
                            "project_id": project_id,
                            "period_id": period_id,
                            "entity_id": entity_id,
                            "fiscal_year": fiscal_year,
                            "fiscal_period": fiscal_period,
                            "period_start": period_start.isoformat()
                            if period_start
                            else None,
                            "period_end": period_end.isoformat()
                            if period_end
                            else None,
                            "created_at": datetime.utcnow().isoformat(),
                        }
                    )
                period_id = period_index[period_key]

                account_code = self._safe_str(row.get(col_account_code))
                account_name = self._safe_str(row.get(col_account_name))
                if not account_code and not account_name:
                    account_code = f"AUTO-{table_name}"
                    account_name = "Unmapped Account"
                account_key = (entity_id, account_code or account_name)
                if account_key not in account_index:
                    account_id = account_counter
                    account_counter += 1
                    account_index[account_key] = account_id
                    accounts.append(
                        {
                            "project_id": project_id,
                            "account_id": account_id,
                            "entity_id": entity_id,
                            "account_code": account_code or None,
                            "account_name": account_name or None,
                            "parent_account_code": None,
                            "account_level": None,
                            "account_type": table_type,
                            "created_at": datetime.utcnow().isoformat(),
                        }
                    )
                account_id = account_index[account_key]

                voucher_number = self._safe_str(row.get(col_voucher_number))
                if not voucher_number:
                    voucher_number = f"AUTO-{table_name}-{idx+1}"
                summary = self._safe_str(
                    row.get(col_summary), default=f"{table_name} row {idx+1}"
                )

                debit_amount = self._safe_number(row.get(col_debit))
                credit_amount = self._safe_number(row.get(col_credit))
                if debit_amount == 0 and credit_amount == 0 and col_amount:
                    raw_amount = self._safe_number(row.get(col_amount))
                    if raw_amount >= 0:
                        debit_amount = raw_amount
                        credit_amount = 0.0
                    else:
                        debit_amount = 0.0
                        credit_amount = abs(raw_amount)
                amount_value = debit_amount - credit_amount

                voucher_key = (
                    entity_id,
                    voucher_number,
                    voucher_date.date() if voucher_date else None,
                )
                if voucher_key not in voucher_index:
                    voucher_id = voucher_counter
                    voucher_counter += 1
                    voucher_index[voucher_key] = voucher_id
                    voucher_totals[voucher_id] = {"debit": 0.0, "credit": 0.0}
                    vouchers.append(
                        {
                            "project_id": project_id,
                            "voucher_id": voucher_id,
                            "entity_id": entity_id,
                            "period_id": period_id,
                            "voucher_number": voucher_number,
                            "voucher_date": voucher_date.date().isoformat()
                            if voucher_date
                            else None,
                            "summary": summary,
                            "source_table": table_name,
                            "source_row_id": f"{table_name}:{idx}",
                            "total_debit": 0.0,
                            "total_credit": 0.0,
                            "created_at": datetime.utcnow().isoformat(),
                        }
                    )
                voucher_id = voucher_index[voucher_key]
                totals = voucher_totals[voucher_id]
                totals["debit"] += debit_amount
                totals["credit"] += credit_amount

                entries.append(
                    {
                        "project_id": project_id,
                        "entry_id": entry_counter,
                        "voucher_id": voucher_id,
                        "line_number": idx + 1,
                        "account_id": account_id,
                        "debit_amount": debit_amount,
                        "credit_amount": credit_amount,
                        "amount": amount_value,
                        "currency": self._safe_str(row.get(col_currency)),
                        "description": summary,
                        "source_table": table_name,
                        "source_row_id": f"{table_name}:{idx}",
                    }
                )
                entry_counter += 1

                if col_attachment_path:
                    attachment_path = self._safe_str(row.get(col_attachment_path))
                    if attachment_path:
                        attachment_desc = self._safe_str(
                            row.get(col_attachment_desc), summary
                        )
                        attachments.append(
                            {
                                "project_id": project_id,
                                "attachment_id": attachment_counter,
                                "voucher_id": voucher_id,
                                "file_path": attachment_path,
                                "description": attachment_desc,
                                "uploaded_at": datetime.utcnow().isoformat(),
                                "source_table": table_name,
                                "source_row_id": f"{table_name}:{idx}",
                            }
                        )
                        attachment_counter += 1

        for voucher in vouchers:
            totals = voucher_totals.get(
                voucher["voucher_id"], {"debit": 0.0, "credit": 0.0}
            )
            voucher["total_debit"] = totals["debit"]
            voucher["total_credit"] = totals["credit"]

        result: Dict[str, pd.DataFrame] = {}
        if entities:
            result["dim_entities"] = pd.DataFrame(entities)
        if periods:
            result["dim_periods"] = pd.DataFrame(periods)
        if accounts:
            result["dim_accounts"] = pd.DataFrame(accounts)
        if vouchers:
            result["fact_vouchers"] = pd.DataFrame(vouchers)
        if entries:
            result["fact_entries"] = pd.DataFrame(entries)
        if attachments:
            result["fact_attachments"] = pd.DataFrame(attachments)

        return result

    def _store_unified_tables(
        self, unified_data: Dict[str, pd.DataFrame], project_id: str
    ) -> None:
        """写入统一模型表（按项目隔离）"""
        if not unified_data:
            return

        table_names = [
            "dim_entities",
            "dim_periods",
            "dim_accounts",
            "fact_vouchers",
            "fact_entries",
            "fact_attachments",
        ]

        for table in table_names:
            try:
                if self._column_exists(table, "project_id"):
                    self.conn.execute(
                        f"DELETE FROM {table} WHERE project_id = ?", (project_id,)
                    )
                else:
                    self.conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass

        for table, frame in unified_data.items():
            if frame is None or frame.empty:
                continue
            try:
                frame_to_store = frame.copy()
                if "project_id" not in frame_to_store.columns:
                    frame_to_store["project_id"] = project_id
                frame_to_store.to_sql(table, self.conn, if_exists="append", index=False)
            except Exception as exc:
                logger.warning(f"写入统一模型表 {table} 失败: {exc}")

        self.conn.commit()

    def _create_unified_views(self, project_id: Optional[str] = None) -> None:
        """��������ͳһģ�͵���ȡ��ͼ��"""
        target_project = project_id or self.get_current_project_id() or self.DEFAULT_PROJECT_ID
        sanitized_suffix = self._sanitize_name(target_project)
        project_literal = target_project.replace("'", "''")

        view_templates: Dict[str, Tuple[str, List[str]]] = {
            "vw_account_year_summary": (
                """
                SELECT
                    fv.project_id,
                    e.entity_name,
                    e.entity_code,
                    p.fiscal_year,
                    a.account_code,
                    a.account_name,
                    SUM(fe.debit_amount) AS total_debit,
                    SUM(fe.credit_amount) AS total_credit,
                    SUM(fe.debit_amount - fe.credit_amount) AS net_change
                FROM fact_entries fe
                JOIN fact_vouchers fv ON fe.voucher_id = fv.voucher_id AND fe.project_id = fv.project_id
                LEFT JOIN dim_accounts a ON fe.account_id = a.account_id AND a.project_id = fe.project_id
                LEFT JOIN dim_entities e ON fv.entity_id = e.entity_id AND e.project_id = fv.project_id
                LEFT JOIN dim_periods p ON fv.period_id = p.period_id AND p.project_id = fv.project_id
                WHERE fv.project_id = '{project_literal}'
                GROUP BY fv.project_id, e.entity_name, e.entity_code, p.fiscal_year, a.account_code, a.account_name
                """,
                ["fact_entries", "fact_vouchers", "dim_accounts", "dim_entities", "dim_periods"],
            ),
            "vw_voucher_with_entries": (
                """
                SELECT
                    fv.project_id,
                    fv.voucher_id,
                    fv.voucher_number,
                    fv.voucher_date,
                    fv.summary AS voucher_summary,
                    e.entity_name,
                    e.entity_code,
                    p.fiscal_year,
                    p.fiscal_period,
                    a.account_code,
                    a.account_name,
                    fe.line_number,
                    fe.debit_amount,
                    fe.credit_amount,
                    fe.amount,
                    fe.currency,
                    fe.description AS entry_description
                FROM fact_entries fe
                JOIN fact_vouchers fv ON fe.voucher_id = fv.voucher_id AND fe.project_id = fv.project_id
                LEFT JOIN dim_accounts a ON fe.account_id = a.account_id AND a.project_id = fe.project_id
                LEFT JOIN dim_entities e ON fv.entity_id = e.entity_id AND e.project_id = fv.project_id
                LEFT JOIN dim_periods p ON fv.period_id = p.period_id AND p.project_id = fv.project_id
                WHERE fv.project_id = '{project_literal}'
                """,
                ["fact_entries", "fact_vouchers", "dim_accounts", "dim_entities", "dim_periods"],
            ),
            "vw_voucher_with_attachments": (
                """
                SELECT
                    fv.project_id,
                    fv.voucher_id,
                    fv.voucher_number,
                    fv.voucher_date,
                    e.entity_name,
                    e.entity_code,
                    fa.file_path,
                    fa.description,
                    fa.uploaded_at
                FROM fact_attachments fa
                JOIN fact_vouchers fv ON fa.voucher_id = fv.voucher_id AND fa.project_id = fv.project_id
                LEFT JOIN dim_entities e ON fv.entity_id = e.entity_id AND e.project_id = fv.project_id
                WHERE fv.project_id = '{project_literal}'
                """,
                ["fact_attachments", "fact_vouchers", "dim_entities"],
            ),
        }

        # Clean up legacy global view names to prevent conflicts
        for legacy_name in view_templates.keys():
            try:
                self.conn.execute(f"DROP VIEW IF EXISTS {legacy_name}")
            except Exception as exc:
                logger.warning("ɾ��ͳһ��ͼ %s ʧ��: %s", legacy_name, exc)

        for base_name, (template_sql, base_tables) in view_templates.items():
            view_name = f"{base_name}_{sanitized_suffix}"
            select_sql = template_sql.format(project_literal=project_literal).strip()
            create_sql = f"CREATE VIEW IF NOT EXISTS {view_name} AS\n{select_sql}"

            try:
                self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                self.conn.execute(create_sql)
                self._record_view_metadata(
                    view_name=view_name,
                    view_type="unified",
                    base_tables=base_tables,
                    dimension_key="project_id",
                    dimension_value=target_project,
                    project_id=target_project,
                    sql_definition=create_sql,
                )
            except Exception as exc:
                logger.warning("������ͼ %s ʧ��: %s", view_name, exc)

        self.conn.commit()

    def list_entities_summary(self) -> List[Dict[str, Any]]:
        """列出所有实体及其汇总信息。"""
        if not self._table_exists("dim_entities"):
            return []

        project_id = self.get_current_project_id()
        query = """
            SELECT
                e.entity_id,
                e.entity_code,
                e.entity_name,
                COALESCE(SUM(fv.total_debit), 0) AS total_debit,
                COALESCE(SUM(fv.total_credit), 0) AS total_credit,
                COUNT(DISTINCT fv.voucher_id) AS voucher_count,
                COUNT(DISTINCT p.fiscal_year) AS fiscal_years
            FROM dim_entities e
            LEFT JOIN fact_vouchers fv ON fv.entity_id = e.entity_id AND fv.project_id = e.project_id
            LEFT JOIN dim_periods p ON fv.period_id = p.period_id AND p.project_id = e.project_id
            WHERE e.project_id = ?
            GROUP BY e.entity_id, e.entity_code, e.entity_name
            ORDER BY e.entity_name COLLATE NOCASE
        """

        rows = self.conn.execute(query, (project_id,)).fetchall()
        summaries = []
        for row in rows:
            summaries.append(
                {
                    "entity_id": row["entity_id"],
                    "entity_code": row["entity_code"],
                    "entity_name": row["entity_name"],
                    "total_debit": float(row["total_debit"] or 0),
                    "total_credit": float(row["total_credit"] or 0),
                    "voucher_count": int(row["voucher_count"] or 0),
                    "fiscal_years": int(row["fiscal_years"] or 0),
                }
            )
        return summaries

    def list_years_for_entity(self, entity_id: int) -> List[Dict[str, Any]]:
        """返回指定实体的年度汇总。"""
        if not self._table_exists("fact_vouchers"):
            return []

        project_id = self.get_current_project_id()
        query = """
            SELECT
                p.fiscal_year,
                COUNT(DISTINCT fv.voucher_id) AS voucher_count,
                COUNT(DISTINCT p.period_id) AS period_count,
                COALESCE(SUM(fv.total_debit), 0) AS total_debit,
                COALESCE(SUM(fv.total_credit), 0) AS total_credit,
                MIN(p.period_start) AS period_start,
                MAX(p.period_end) AS period_end
            FROM fact_vouchers fv
            JOIN dim_periods p ON fv.period_id = p.period_id AND fv.project_id = p.project_id
            WHERE fv.entity_id = ? AND fv.project_id = ?
            GROUP BY p.fiscal_year
            ORDER BY p.fiscal_year
        """

        rows = self.conn.execute(query, (entity_id, project_id)).fetchall()
        years = []
        for row in rows:
            years.append(
                {
                    "fiscal_year": row["fiscal_year"] or "",
                    "voucher_count": int(row["voucher_count"] or 0),
                    "period_count": int(row["period_count"] or 0),
                    "total_debit": float(row["total_debit"] or 0),
                    "total_credit": float(row["total_credit"] or 0),
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                }
            )
        return years

    def list_accounts_for_entity_year(
        self, entity_id: int, fiscal_year: str, search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """列出指定实体和年度下的科目信息。"""
        if not self._table_exists("fact_entries"):
            return []

        project_id = self.get_current_project_id()
        conditions = ["fv.entity_id = ?", "p.fiscal_year = ?", "fv.project_id = ?"]
        params: List[Any] = [entity_id, fiscal_year, project_id]

        if search:
            like_term = f"%{search.strip()}%"
            conditions.append("(a.account_code LIKE ? OR a.account_name LIKE ?)")
            params.extend([like_term, like_term])

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                a.account_id,
                a.account_code,
                a.account_name,
                COALESCE(SUM(fe.debit_amount), 0) AS total_debit,
                COALESCE(SUM(fe.credit_amount), 0) AS total_credit,
                COUNT(DISTINCT fv.voucher_id) AS voucher_count
            FROM fact_entries fe
            JOIN fact_vouchers fv ON fe.voucher_id = fv.voucher_id AND fe.project_id = fv.project_id
            JOIN dim_accounts a ON fe.account_id = a.account_id AND a.project_id = fv.project_id
            JOIN dim_periods p ON fv.period_id = p.period_id AND p.project_id = fv.project_id
            WHERE {where_clause}
            GROUP BY a.account_id, a.account_code, a.account_name
            ORDER BY a.account_code COLLATE NOCASE, a.account_name COLLATE NOCASE
        """

        rows = self.conn.execute(query, params).fetchall()
        accounts = []
        for row in rows:
            accounts.append(
                {
                    "account_id": row["account_id"],
                    "account_code": row["account_code"],
                    "account_name": row["account_name"],
                    "total_debit": float(row["total_debit"] or 0),
                    "total_credit": float(row["total_credit"] or 0),
                    "voucher_count": int(row["voucher_count"] or 0),
                }
            )
        return accounts

    def list_vouchers_for_account(
        self,
        entity_id: int,
        fiscal_year: str,
        account_id: int,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """按分页返回指定科目的凭证明细。"""
        if not self._table_exists("fact_entries"):
            return self._empty_page_result(page, page_size)

        project_id = self.get_current_project_id()
        base_condition = """
            FROM fact_entries fe
            JOIN fact_vouchers fv ON fe.voucher_id = fv.voucher_id AND fe.project_id = fv.project_id
            JOIN dim_periods p ON fv.period_id = p.period_id AND p.project_id = fv.project_id
            LEFT JOIN fact_attachments fa ON fv.voucher_id = fa.voucher_id AND fa.project_id = fv.project_id
            WHERE fv.entity_id = ? AND p.fiscal_year = ? AND fe.account_id = ? AND fv.project_id = ?
        """
        params: List[Any] = [entity_id, fiscal_year, account_id, project_id]

        if search:
            like_term = f"%{search.strip()}%"
            base_condition += " AND (fv.voucher_number LIKE ? OR fv.summary LIKE ?)"
            params.extend([like_term, like_term])

        count_sql = f"SELECT COUNT(DISTINCT fv.voucher_id) {base_condition}"
        total = self.conn.execute(count_sql, params).fetchone()[0] or 0

        if total == 0:
            return self._empty_page_result(page, page_size)

        total_pages = max(1, ceil(total / page_size))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size

        select_sql = f"""
            SELECT
                fv.voucher_id,
                fv.voucher_number,
                fv.voucher_date,
                fv.summary,
                SUM(fe.debit_amount) AS account_debit,
                SUM(fe.credit_amount) AS account_credit,
                COUNT(DISTINCT fa.attachment_id) AS attachment_count
            {base_condition}
            GROUP BY fv.voucher_id, fv.voucher_number, fv.voucher_date, fv.summary
            ORDER BY fv.voucher_date, fv.voucher_number
            LIMIT ? OFFSET ?
        """

        rows = self.conn.execute(
            select_sql, params + [page_size, offset]
        ).fetchall()

        data_rows = []
        for row in rows:
            data_rows.append(
                {
                    "voucher_id": row["voucher_id"],
                    "voucher_number": row["voucher_number"],
                    "voucher_date": row["voucher_date"],
                    "summary": row["summary"],
                    "account_debit": float(row["account_debit"] or 0),
                    "account_credit": float(row["account_credit"] or 0),
                    "attachment_count": int(row["attachment_count"] or 0),
                }
            )

        return {
            "columns": [
                "voucher_number",
                "voucher_date",
                "summary",
                "account_debit",
                "account_credit",
                "attachment_count",
            ],
            "rows": data_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_voucher_entries_paginated(
        self,
        voucher_id: int,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """返回指定凭证的分录信息（分页）。"""
        if not self._table_exists("fact_entries"):
            return self._empty_page_result(page, page_size)

        project_id = self.get_current_project_id()
        base_sql = """
            FROM fact_entries fe
            LEFT JOIN dim_accounts a ON fe.account_id = a.account_id AND a.project_id = fe.project_id
            WHERE fe.voucher_id = ? AND fe.project_id = ?
        """
        params: List[Any] = [voucher_id, project_id]

        if search:
            like_term = f"%{search.strip()}%"
            base_sql += " AND (a.account_code LIKE ? OR a.account_name LIKE ? OR fe.description LIKE ?)"
            params.extend([like_term, like_term, like_term])

        count_sql = f"SELECT COUNT(*) {base_sql}"
        total = self.conn.execute(count_sql, params).fetchone()[0] or 0

        if total == 0:
            return self._empty_page_result(page, page_size, columns=[
                "line_number",
                "account_code",
                "account_name",
                "debit_amount",
                "credit_amount",
                "amount",
                "currency",
                "description",
            ])

        total_pages = max(1, ceil(total / page_size))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size

        select_sql = f"""
            SELECT
                fe.entry_id,
                fe.line_number,
                a.account_code,
                a.account_name,
                fe.debit_amount,
                fe.credit_amount,
                fe.amount,
                fe.currency,
                fe.description
            {base_sql}
            ORDER BY fe.line_number
            LIMIT ? OFFSET ?
        """

        rows = self.conn.execute(
            select_sql, params + [page_size, offset]
        ).fetchall()

        data_rows = []
        for row in rows:
            data_rows.append(
                {
                    "entry_id": row["entry_id"],
                    "line_number": row["line_number"],
                    "account_code": row["account_code"],
                    "account_name": row["account_name"],
                    "debit_amount": float(row["debit_amount"] or 0),
                    "credit_amount": float(row["credit_amount"] or 0),
                    "amount": float(row["amount"] or 0),
                    "currency": row["currency"],
                    "description": row["description"],
                }
            )

        return {
            "columns": [
                "line_number",
                "account_code",
                "account_name",
                "debit_amount",
                "credit_amount",
                "amount",
                "currency",
                "description",
            ],
            "rows": data_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_voucher_attachments(self, voucher_id: int) -> List[Dict[str, Any]]:
        """获取凭证对应的附件。"""
        if not self._table_exists("fact_attachments"):
            return []

        query = """
            SELECT
                attachment_id,
                file_path,
                description,
                uploaded_at,
                source_table,
                source_row_id
            FROM fact_attachments
            WHERE voucher_id = ?
        """
        params: List[Any] = [voucher_id]
        if self._column_exists("fact_attachments", "project_id"):
            query += " AND project_id = ?"
            params.append(self.get_current_project_id())

        query += " ORDER BY attachment_id"
        rows = self.conn.execute(query, tuple(params)).fetchall()
        attachments = []
        for row in rows:
            attachments.append(
                {
                    "attachment_id": row["attachment_id"],
                    "file_path": row["file_path"],
                    "description": row["description"],
                    "uploaded_at": row["uploaded_at"],
                    "source_table": row["source_table"],
                    "source_row_id": row["source_row_id"],
                }
            )
        return attachments

    def query_table_paginated(
        self,
        table_or_view: str,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        search: Optional[str] = None,
        search_columns: Optional[List[str]] = None,
        order_by: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """通用分页查询接口，支持过滤与模糊搜索。"""
        safe_table = SQLQueryValidator.validate_table_name(table_or_view)
        page = max(1, page)
        page_size = max(1, page_size)

        where_clauses: List[str] = []
        params: List[Any] = []

        def append_condition(column: str, operator: str, value: Any) -> None:
            safe_col = SQLQueryValidator.validate_column_name(column)
            where_clauses.append(f"\"{safe_col}\" {operator} ?")
            params.append(value)

        project_id = self.get_current_project_id()
        if self._column_exists(safe_table, "project_id"):
            where_clauses.append("\"project_id\" = ?")
            params.append(project_id)

        if filters:
            for column, value in filters.items():
                if isinstance(value, dict):
                    operator = value.get("operator", "=").strip().upper()
                    if operator not in {"=", "!=", ">", ">=", "<", "<=", "LIKE"}:
                        operator = "="
                    append_condition(column, operator, value.get("value"))
                else:
                    operator = "LIKE" if isinstance(value, str) and "%" in value else "="
                    append_condition(column, operator, value)

        if search and search_columns:
            like_term = f"%{search.strip()}%"
            search_parts = []
            for column in search_columns:
                safe_col = SQLQueryValidator.validate_column_name(column)
                search_parts.append(f"\"{safe_col}\" LIKE ?")
                params.append(like_term)
            if search_parts:
                where_clauses.append("(" + " OR ".join(search_parts) + ")")

        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)

        count_sql = f"SELECT COUNT(*) FROM {safe_table}{where_sql}"
        total = self.conn.execute(count_sql, params).fetchone()[0] or 0

        columns = self._get_table_columns(safe_table)

        if total == 0:
            return {
                "columns": columns,
                "rows": [],
                "total": 0,
                "page": 1,
                "page_size": page_size,
                "total_pages": 1,
            }

        total_pages = max(1, ceil(total / page_size))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size

        order_sql = ""
        if order_by:
            ordering = []
            for entry in order_by:
                if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                    column = SQLQueryValidator.validate_column_name(entry[0])
                    direction = entry[1].upper() if len(entry) > 1 else "ASC"
                else:
                    column = SQLQueryValidator.validate_column_name(str(entry))
                    direction = "ASC"
                if direction not in {"ASC", "DESC"}:
                    direction = "ASC"
                ordering.append(f"\"{column}\" {direction}")
            if ordering:
                order_sql = " ORDER BY " + ", ".join(ordering)

        select_sql = (
            f"SELECT * FROM {safe_table}{where_sql}{order_sql} LIMIT ? OFFSET ?"
        )
        rows = self.conn.execute(
            select_sql, params + [page_size, offset]
        ).fetchall()
        data_rows = [dict(row) for row in rows]

        return {
            "columns": columns,
            "rows": data_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }



    def _ensure_unified_schema(self) -> None:
        """Ensure the unified dimensional/fact schema is project-scoped."""
        table_specs: Dict[str, Dict[str, Any]] = {
            "dim_entities": {
                "sql": """
                    CREATE TABLE IF NOT EXISTS dim_entities (
                        project_id TEXT NOT NULL,
                        entity_id INTEGER NOT NULL,
                        entity_code TEXT,
                        entity_name TEXT,
                        source_table TEXT,
                        created_at TIMESTAMP,
                        PRIMARY KEY (project_id, entity_id)
                    )
                """,
                "primary_key": ["project_id", "entity_id"],
            },
            "dim_periods": {
                "sql": """
                    CREATE TABLE IF NOT EXISTS dim_periods (
                        project_id TEXT NOT NULL,
                        period_id INTEGER NOT NULL,
                        entity_id INTEGER NOT NULL,
                        fiscal_year TEXT,
                        fiscal_period TEXT,
                        period_start TIMESTAMP,
                        period_end TIMESTAMP,
                        created_at TIMESTAMP,
                        PRIMARY KEY (project_id, period_id),
                        FOREIGN KEY (project_id, entity_id) REFERENCES dim_entities(project_id, entity_id)
                    )
                """,
                "primary_key": ["project_id", "period_id"],
            },
            "dim_accounts": {
                "sql": """
                    CREATE TABLE IF NOT EXISTS dim_accounts (
                        project_id TEXT NOT NULL,
                        account_id INTEGER NOT NULL,
                        entity_id INTEGER NOT NULL,
                        account_code TEXT,
                        account_name TEXT,
                        parent_account_code TEXT,
                        account_level INTEGER,
                        account_type TEXT,
                        created_at TIMESTAMP,
                        PRIMARY KEY (project_id, account_id),
                        FOREIGN KEY (project_id, entity_id) REFERENCES dim_entities(project_id, entity_id)
                    )
                """,
                "primary_key": ["project_id", "account_id"],
            },
            "fact_vouchers": {
                "sql": """
                    CREATE TABLE IF NOT EXISTS fact_vouchers (
                        project_id TEXT NOT NULL,
                        voucher_id INTEGER NOT NULL,
                        entity_id INTEGER NOT NULL,
                        period_id INTEGER,
                        voucher_number TEXT,
                        voucher_date DATE,
                        summary TEXT,
                        source_table TEXT,
                        source_row_id TEXT,
                        total_debit REAL,
                        total_credit REAL,
                        created_at TIMESTAMP,
                        PRIMARY KEY (project_id, voucher_id),
                        FOREIGN KEY (project_id, entity_id) REFERENCES dim_entities(project_id, entity_id),
                        FOREIGN KEY (project_id, period_id) REFERENCES dim_periods(project_id, period_id)
                    )
                """,
                "primary_key": ["project_id", "voucher_id"],
            },
            "fact_entries": {
                "sql": """
                    CREATE TABLE IF NOT EXISTS fact_entries (
                        project_id TEXT NOT NULL,
                        entry_id INTEGER NOT NULL,
                        voucher_id INTEGER NOT NULL,
                        line_number INTEGER,
                        account_id INTEGER NOT NULL,
                        debit_amount REAL,
                        credit_amount REAL,
                        amount REAL,
                        currency TEXT,
                        description TEXT,
                        source_table TEXT,
                        source_row_id TEXT,
                        PRIMARY KEY (project_id, entry_id),
                        FOREIGN KEY (project_id, voucher_id) REFERENCES fact_vouchers(project_id, voucher_id),
                        FOREIGN KEY (project_id, account_id) REFERENCES dim_accounts(project_id, account_id)
                    )
                """,
                "primary_key": ["project_id", "entry_id"],
            },
            "fact_attachments": {
                "sql": """
                    CREATE TABLE IF NOT EXISTS fact_attachments (
                        project_id TEXT NOT NULL,
                        attachment_id INTEGER NOT NULL,
                        voucher_id INTEGER NOT NULL,
                        file_path TEXT,
                        description TEXT,
                        uploaded_at TIMESTAMP,
                        source_table TEXT,
                        source_row_id TEXT,
                        PRIMARY KEY (project_id, attachment_id),
                        FOREIGN KEY (project_id, voucher_id) REFERENCES fact_vouchers(project_id, voucher_id)
                    )
                """,
                "primary_key": ["project_id", "attachment_id"],
            },
        }

        def _table_info(table: str) -> List[Tuple[Any, ...]]:
            try:
                return self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            except Exception:
                return []

        def _has_expected_pk(table: str, expected: List[str]) -> bool:
            info = _table_info(table)
            if not info:
                return False
            pk_columns = [
                row[1]
                for row in sorted(info, key=lambda item: item[5] or 0)
                if row[5]
            ]
            return pk_columns == expected

        def _rebuild_table(table: str, spec: Dict[str, Any]) -> None:
            temp_table = f"{table}_legacy_{int(time.time())}"
            logger.info("Rebuilding unified table %s to apply project scope.", table)
            self.conn.execute(f"ALTER TABLE {table} RENAME TO {temp_table}")
            self.conn.execute(spec["sql"])

            new_columns = [
                row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")
            ]
            legacy_columns = {
                row[1] for row in self.conn.execute(f"PRAGMA table_info({temp_table})")
            }

            insert_columns: List[str] = []
            select_columns: List[str] = []
            for column in new_columns:
                insert_columns.append(f'"{column}"')
                if column in legacy_columns:
                    select_columns.append(f'"{column}"')
                elif column == "project_id":
                    select_columns.append(
                        f"'{self.DEFAULT_PROJECT_ID}' AS \"{column}\""
                    )
                else:
                    select_columns.append(f"NULL AS \"{column}\"")

            try:
                insert_sql = (
                    f"INSERT INTO {table} ({', '.join(insert_columns)}) "
                    f"SELECT {', '.join(select_columns)} FROM {temp_table}"
                )
                self.conn.execute(insert_sql)
            except Exception as exc:
                logger.warning(
                    "Failed to migrate legacy data for %s: %s. Data left in %s.",
                    table,
                    exc,
                    temp_table,
                )
            else:
                self.conn.execute(f"DROP TABLE {temp_table}")

        for table_name, spec in table_specs.items():
            sql_statement = spec["sql"]
            expected_pk = spec.get("primary_key", [])

            if not self._table_exists(table_name):
                try:
                    self.conn.execute(sql_statement)
                except Exception as exc:
                    logger.warning("Failed to create unified model table %s: %s", table_name, exc)
                continue

            info = _table_info(table_name)
            column_names = {row[1] for row in info}
            needs_rebuild = "project_id" not in column_names or (
                expected_pk and not _has_expected_pk(table_name, expected_pk)
            )

            if needs_rebuild:
                try:
                    _rebuild_table(table_name, spec)
                except Exception as exc:
                    logger.warning("Failed to rebuild unified model table %s: %s", table_name, exc)
            else:
                try:
                    self.conn.execute(sql_statement)
                except Exception as exc:
                    logger.warning("Failed to validate unified model table %s: %s", table_name, exc)

        legacy_indexes = [
            "idx_dim_entities_code",
            "idx_dim_periods_entity",
            "idx_dim_accounts_entity",
            "idx_fact_vouchers_entity",
            "idx_fact_vouchers_period",
            "idx_fact_entries_voucher",
            "idx_fact_entries_account",
            "idx_fact_attachments_voucher",
        ]
        for index in legacy_indexes:
            try:
                self.conn.execute(f"DROP INDEX IF EXISTS {index}")
            except Exception:
                pass

        index_specs = [
            ("idx_dim_entities_project_code", "dim_entities", '"project_id", "entity_code"'),
            ("idx_dim_periods_project_entity", "dim_periods", '"project_id", "entity_id"'),
            ("idx_dim_accounts_project_entity", "dim_accounts", '"project_id", "entity_id"'),
            ("idx_dim_accounts_project_code", "dim_accounts", '"project_id", "account_code"'),
            ("idx_fact_vouchers_project_entity", "fact_vouchers", '"project_id", "entity_id"'),
            ("idx_fact_vouchers_project_period", "fact_vouchers", '"project_id", "period_id"'),
            ("idx_fact_entries_project_voucher", "fact_entries", '"project_id", "voucher_id"'),
            ("idx_fact_entries_project_account", "fact_entries", '"project_id", "account_id"'),
            ("idx_fact_attachments_project_voucher", "fact_attachments", '"project_id", "voucher_id"'),
        ]

        for index_name, table, columns in index_specs:
            try:
                self.conn.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})"
                )
            except Exception as exc:
                logger.warning("Failed to create index %s: %s", index_name, exc)

        self.conn.commit()

    def _detect_column(self, columns: List[str], key: str) -> Optional[str]:
        """根据同义词列表匹配列名。"""
        synonyms = self.COLUMN_SYNONYMS.get(key, [])
        lowered = {col: str(col).strip().lower() for col in columns}

        for col, lower in lowered.items():
            if lower in synonyms:
                return col

        for col, lower in lowered.items():
            for candidate in synonyms:
                if candidate in lower:
                    return col

        return None

    def _safe_str(self, value: Any, default: Optional[str] = None) -> Optional[str]:
        """安全地将值转换为字符串。"""
        if value is None:
            return default
        try:
            if isinstance(value, float) and np.isnan(value):
                return default
        except TypeError:
            pass

        text = str(value).strip()
        return text if text else default

    def _safe_number(self, value: Any) -> float:
        """安全地转换为数值。"""
        if value is None:
            return 0.0
        try:
            if isinstance(value, str):
                value = value.replace(",", "")
            number = float(value)
            if np.isnan(number):
                return 0.0
            return number
        except Exception:
            return 0.0

    def _safe_datetime(self, value: Any) -> Optional[datetime]:
        """安全地解析日期时间。"""
        if value is None:
            return None
        try:
            ts = pd.to_datetime(value, errors="coerce")
            if pd.isna(ts):
                return None
            return ts.to_pydatetime()
        except Exception:
            return None

    def _derive_period_info(
        self,
        voucher_date: Optional[datetime],
        row: pd.Series,
        col_year: Optional[str],
        col_period: Optional[str],
    ) -> tuple:
        """根据日期或列信息推导会计期间。"""
        fiscal_year = self._safe_str(row.get(col_year)) if col_year else None
        fiscal_period = self._safe_str(row.get(col_period)) if col_period else None

        if voucher_date:
            if not fiscal_year:
                fiscal_year = str(voucher_date.year)
            if not fiscal_period:
                fiscal_period = f"{voucher_date.month:02d}"

        period_start = None
        period_end = None
        if voucher_date:
            year = voucher_date.year
            month = voucher_date.month
            period_start = datetime(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            period_end = datetime(year, month, last_day)

        return (
            fiscal_year or "",
            fiscal_period or "",
            period_start,
            period_end,
        )

    def _empty_page_result(
        self,
        page: int,
        page_size: int,
        columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """返回空的分页结果结构。"""
        return {
            "columns": columns or [],
            "rows": [],
            "total": 0,
            "page": max(1, page),
            "page_size": max(1, page_size),
            "total_pages": 1,
        }

    def _get_table_columns(self, table_or_view: str) -> List[str]:
        """尝试获取表或视图的列名。"""
        try:
            info = self.conn.execute(f"PRAGMA table_info({table_or_view})").fetchall()
            if info:
                return [row[1] for row in info]
        except Exception:
            pass

        try:
            cursor = self.conn.execute(f"SELECT * FROM {table_or_view} LIMIT 0")
            if cursor.description:
                return [desc[0] for desc in cursor.description]
        except Exception:
            pass

        return []

    def _table_exists(self, table_or_view: str) -> bool:
        """判断表或视图是否存在。"""
        try:
            query = """
                SELECT 1 FROM sqlite_master
                WHERE type IN ('table', 'view') AND name = ?
                LIMIT 1
            """
            row = self.conn.execute(query, (table_or_view,)).fetchone()
            return row is not None
        except Exception:
            return False

    def _find_company_column(self, data: pd.DataFrame) -> Optional[str]:
        """查找公司列"""
        for col in data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['公司', 'company', 'corp', '企业', '单位']):
                return col
        return None
    
    def _find_project_column(self, data: pd.DataFrame) -> Optional[str]:
        """查找项目列"""
        for col in data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['项目', 'project', 'proj', '工程']):
                return col
        return None
    
    def _find_date_columns(self, data: pd.DataFrame) -> List[str]:
        """查找日期列"""
        date_columns = []
        for col in data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['日期', 'date', 'time', '时间']):
                date_columns.append(col)
            # 也可以通过数据类型判断
            elif data[col].dtype == 'datetime64[ns]':
                date_columns.append(col)
        return date_columns
    
    def _find_amount_columns(self, data: pd.DataFrame) -> List[str]:
        """查找金额列"""
        amount_columns = []
        for col in data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['金额', 'amount', 'money', '价格', 'price']):
                amount_columns.append(col)
        return amount_columns
    
    def _sanitize_name(self, name: str) -> str:
        """清理名称，使其适合作为SQL标识符"""
        import re
        import hashlib
        
        if not name or not str(name).strip():
            return 'unknown_table'
        
        name_str = str(name).strip()
        
        # 特殊中文公司名称映射
        name_mapping = {
            '河南泰田重工机械制造有限公司': 'henan_taitain_heavy_industry',
            '泰田重工': 'taitain_heavy_industry',
            'TaiTain Heavy Industry': 'taitain_heavy_industry'
        }
        
        # 如果是已知中文名称，直接使用映射
        for chinese_name, english_name in name_mapping.items():
            if chinese_name in name_str:
                name_str = name_str.replace(chinese_name, english_name)
        
        # 处理中文字符：转换为拼音或使用hash
        if any(ord(char) > 127 for char in name_str):
            # 对于包含非ASCII字符的名称，使用hash值
            hash_value = hashlib.md5(name_str.encode('utf-8')).hexdigest()[:8]
            # 保留ASCII部分并添加hash
            ascii_part = re.sub(r'[^\w]', '_', ''.join(char for char in name_str if ord(char) < 127))
            if ascii_part:
                sanitized = f"{ascii_part}_{hash_value}"
            else:
                sanitized = f"table_{hash_value}"
        else:
            # 处理纯ASCII名称
            sanitized = re.sub(r'[^\w]', '_', name_str)
        
        # 清理下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = sanitized.strip('_')
        sanitized = sanitized.lower()
        
        # 确保以字母开头
        if sanitized and not sanitized[0].isalpha():
            sanitized = 'table_' + sanitized
        
        # 限制长度
        if len(sanitized) > 50:
            sanitized = sanitized[:50].rstrip('_')
        
        # 确保不为空且符合SQL标识符规范
        if not sanitized or not sanitized[0].isalpha():
            sanitized = 'table_' + hashlib.md5(name_str.encode('utf-8')).hexdigest()[:8]
        
        # 使用验证器进行安全检查（带异常处理）
        try:
            return SQLQueryValidator.validate_table_name(sanitized)
        except Exception as e:
            logger.warning(f"表名验证失败 {sanitized}: {e}，使用安全备选方案")
            # 安全备选方案：使用hash值
            return 'table_' + hashlib.md5(name_str.encode('utf-8')).hexdigest()[:8]
    
    def _record_view_metadata(
        self,
        view_name: str,
        view_type: str,
        base_tables: List[str],
        dimension_key: str,
        dimension_value: str,
        project_id: str,
        sql_definition: Optional[str] = None,
    ):
        """记录视图元数据"""
        try:
            view_meta_sql = '''
                INSERT OR REPLACE INTO meta_views
                (view_name, project_id, view_type, base_tables, dimension_key, dimension_value, sql_definition, last_refreshed)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            '''
            self.conn.execute(
                view_meta_sql,
                (
                    view_name,
                    project_id,
                    view_type,
                    self._safe_json_dumps(base_tables),
                    dimension_key,
                    dimension_value,
                    sql_definition,
                ),
            )
        except Exception as exc:
            logger.warning("记录视图元数据失败 %s: %s", view_name, exc)
    
    def _create_indexes(self):
        """创建优化索引"""
        logger.info("创建数据库索引")
        
        # 获取所有raw_clean表
        tables_query = '''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'raw_clean_%'
        '''
        
        tables = self.conn.execute(tables_query).fetchall()
        
        for (table_name,) in tables:
            try:
                # 获取表的列信息
                columns_query = f"PRAGMA table_info({table_name})"
                columns = self.conn.execute(columns_query).fetchall()
                
                for col_info in columns:
                    col_name = col_info[1]  # 列名在第二个位置
                    col_lower = col_name.lower()
                    
                    # 为常用查询字段创建索引
                    index_patterns = [
                        ('date', ['日期', 'date', 'time', '时间']),
                        ('company', ['公司', 'company', 'corp', '企业']),
                        ('project', ['项目', 'project', 'proj', '工程']),
                        ('amount', ['金额', 'amount', 'money', '价格']),
                        ('account', ['科目', 'account', 'subject', '账户'])
                    ]
                    
                    for index_type, keywords in index_patterns:
                        if any(keyword in col_lower for keyword in keywords):
                            index_name = f"idx_{table_name}_{col_name}"
                            
                            try:
                                create_index_sql = f'''
                                    CREATE INDEX IF NOT EXISTS {index_name}
                                    ON {table_name} ("{col_name}")
                                '''
                                self.conn.execute(create_index_sql)
                                logger.info(f"创建索引: {index_name}")
                                break  # 每列只创建一个索引
                                
                            except Exception as e:
                                logger.warning(f"创建索引失败 {index_name}: {e}")
                
            except Exception as e:
                logger.warning(f"为表创建索引失败 {table_name}: {e}")
        
        self.conn.commit()
    
    def get_table_list(self) -> List[Dict[str, Any]]:
        """获取所有表列表"""
        project_id = self.get_current_project_id()
        query = '''
            SELECT table_name, table_type, business_domain, row_count, 
                   column_count, data_quality_score, created_at
            FROM meta_tables
            WHERE project_id = ?
            ORDER BY created_at DESC
        '''
        
        results = self.conn.execute(query, (project_id,)).fetchall()
        
        tables = []
        for row in results:
            tables.append({
                'table_name': row[0],
                'table_type': row[1],
                'business_domain': row[2],
                'row_count': row[3],
                'column_count': row[4],
                'data_quality_score': row[5],
                'created_at': row[6]
            })
        
        return tables
    
    def get_view_list(self) -> List[Dict[str, Any]]:
        """获取所有视图列表"""
        project_id = self.get_current_project_id()
        query = '''
            SELECT view_name, view_type, dimension_key, dimension_value, 
                   created_at, last_refreshed
            FROM meta_views
            WHERE project_id = ?
            ORDER BY view_type, dimension_value
        '''
        
        results = self.conn.execute(query, (project_id,)).fetchall()
        
        views = []
        for row in results:
            views.append({
                'view_name': row[0],
                'view_type': row[1],
                'dimension_key': row[2],
                'dimension_value': row[3],
                'created_at': row[4],
                'last_refreshed': row[5]
            })
        
        return views
    
    def query_data(
        self, table_or_view: str, limit: int = 1000,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """查询数据 - 增强的查询功能"""
        try:
            safe_name = SQLQueryValidator.validate_table_name(table_or_view)
            project_id = self.get_current_project_id()

            query = f"SELECT * FROM {safe_name}"
            params: List[Any] = []
            where_clauses: List[str] = []

            if self._column_exists(safe_name, "project_id"):
                where_clauses.append('"project_id" = ?')
                params.append(project_id)

            if filters:
                for col, value in filters.items():
                    safe_col = SQLQueryValidator.validate_column_name(col)
                    where_clauses.append(f'"{safe_col}" = ?')
                    params.append(value)

            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)

            if limit > 0:
                query += f" LIMIT {int(limit)}"

            return pd.read_sql_query(query, self.conn, params=params)

        except Exception as e:
            logger.error(f"查询数据失败 {table_or_view}: {e}")
            return pd.DataFrame()

    def get_table_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            stats = {}
            
            # 数据库文件大小
            import os
            if os.path.exists(self.db_path):
                stats['db_size_mb'] = os.path.getsize(self.db_path) / (1024 * 1024)
            
            # 表数量
            table_count_query = "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            stats['table_count'] = self.conn.execute(table_count_query).fetchone()[0]
            
            # 视图数量
            view_count_query = "SELECT COUNT(*) FROM sqlite_master WHERE type='view'"
            stats['view_count'] = self.conn.execute(view_count_query).fetchone()[0]
            
            # 索引数量
            index_count_query = "SELECT COUNT(*) FROM sqlite_master WHERE type='index'"
            stats['index_count'] = self.conn.execute(index_count_query).fetchone()[0]
            
            # 数据表行数统计
            tables_query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'raw_clean_%'"
            tables = self.conn.execute(tables_query).fetchall()
            
            total_rows = 0
            for (table_name,) in tables:
                try:
                    count_query = f"SELECT COUNT(*) FROM {table_name}"
                    count = self.conn.execute(count_query).fetchone()[0]
                    total_rows += count
                except:
                    continue
            
            stats['total_data_rows'] = total_rows
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def close(self):
        """关闭数据库连接 - 增强的清理逻辑"""
        if self.conn:
            try:
                # 执行最后一次优化
                self.conn.execute("PRAGMA optimize")
                self.conn.commit()
            except Exception as e:
                logger.warning(f"关闭前优化失败: {e}")
            finally:
                self.conn.close()
                self.conn = None
                logger.info("数据库连接已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False


    def health_check(self) -> Dict[str, Any]:
        """数据库健康检查"""
        health_status = {
            'status': 'unknown',
            'issues': [],
            'recommendations': []
        }
        
        try:
            # 检查连接是否有效
            self.conn.execute("SELECT 1").fetchone()
            health_status['status'] = 'healthy'
            
            # 检查外键约束是否启用
            fk_result = self.conn.execute("PRAGMA foreign_keys").fetchone()
            if not fk_result or fk_result[0] != 1:
                health_status['issues'].append('外键约束未启用')
                health_status['recommendations'].append('启用外键约束以保证数据完整性')
            
            # 检查是否需要VACUUM
            stats = self.get_table_stats()
            if stats.get('db_size_mb', 0) > 100:  # 大于100MB
                health_status['recommendations'].append('考虑运行VACUUM命令压缩数据库')
            
            # 检查是否有孤立的元数据
            orphan_check = '''
                SELECT COUNT(*) FROM meta_columns mc 
                LEFT JOIN meta_tables mt ON mc.table_name = mt.table_name
                WHERE mt.table_name IS NULL
            '''
            orphan_count = self.conn.execute(orphan_check).fetchone()[0]
            if orphan_count > 0:
                health_status['issues'].append(f'发现{orphan_count}个孤立的列元数据记录')
                health_status['recommendations'].append('清理孤立的元数据记录')
            
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['issues'].append(f'数据库连接错误: {str(e)}')
        
        return health_status

# 测试函数
def test_storage_manager():
    """测试存储管理器"""
    # 创建测试数据
    test_data = {
        'customers': pd.DataFrame({
            'customer_id': [1, 2, 3],
            'customer_name': ['公司A', '公司B', '公司C'],
            'registration_date': ['2023-01-01', '2023-01-02', '2023-01-03'],
            'credit_limit': [100000.00, 200000.00, 150000.00]
        }),
        'sales_orders': pd.DataFrame({
            'order_id': [1001, 1002, 1003],
            'customer_id': [1, 2, 1],
            'order_date': ['2023-02-01', '2023-02-02', '2023-02-03'],
            'order_amount': [50000, 75000, 30000]
        })
    }
    
    # 测试模式
    test_schema = {
        'customers': {
            'columns': {
                'customer_id': {'type': 'integer'},
                'customer_name': {'type': 'text'},
                'registration_date': {'type': 'date'},
                'credit_limit': {'type': 'currency'}
            },
            'primary_keys': ['customer_id'],
            'business_meaning': {
                'table_type': 'customer_master',
                'business_domain': 'sales'
            }
        },
        'sales_orders': {
            'columns': {
                'order_id': {'type': 'integer'},
                'customer_id': {'type': 'integer'},
                'order_date': {'type': 'date'},
                'order_amount': {'type': 'currency'}
            },
            'primary_keys': ['order_id'],
            'business_meaning': {
                'table_type': 'sales_transaction',
                'business_domain': 'sales'
            }
        }
    }
    
    # 测试存储
    storage = StorageManager('test_dap.db')
    success = storage.store_cleaned_data(test_data, test_schema)
    
    if success:
        print("✅ 数据存储成功")
        
        # 测试查询
        tables = storage.get_table_list()
        print(f"存储的表: {[t['table_name'] for t in tables]}")
        
        views = storage.get_view_list()
        print(f"创建的视图: {[v['view_name'] for v in views]}")
        
        # 测试数据查询
        customer_data = storage.query_data('raw_clean_customers')
        print(f"客户数据行数: {len(customer_data)}")
        
    else:
        print("❌ 数据存储失败")
    
    storage.close()


if __name__ == "__main__":
    # 运行测试或健康检查
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'health':
        storage = StorageManager()
        health = storage.health_check()
        print(f"健康状态: {health['status']}")
        if health['issues']:
            print("发现的问题:")
            for issue in health['issues']:
                print(f"  - {issue}")
        if health['recommendations']:
            print("建议:")
            for rec in health['recommendations']:
                print(f"  - {rec}")
        storage.close()
    else:
        test_storage_manager()
