"""
Document orchestrator for audit document generation and attachment handling.
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from layer1.storage_manager import StorageManager
from utils.validators import SQLQueryValidator
from utils.encryption import AttachmentEncryptionManager, EncryptionConfig


logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = REPO_ROOT / "config" / "document_templates.yaml"


@dataclass
class DocumentTemplateSummary:
    """Lightweight template metadata for UI consumption."""

    name: str
    description: str
    output_formats: List[str] = field(default_factory=list)
    has_appendices: bool = False


class DocumentTemplateRegistry:
    """
    YAML-backed registry that loads document templates and default settings.
    """

    def __init__(self, template_path: Path = DEFAULT_TEMPLATE_PATH):
        self.template_path = template_path
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._default_settings: Dict[str, Any] = {}
        self._validation: Dict[str, Any] = {}
        self._last_mtime: float = 0.0
        self.refresh()

    def refresh(self) -> None:
        """Reload templates when the YAML file changes."""
        if not self.template_path.exists():
            logger.warning("Template file %s not found", self.template_path)
            self._templates = {}
            self._default_settings = {}
            self._validation = {}
            return

        try:
            content = yaml.safe_load(self.template_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.error("Failed to parse template file: %s", exc)
            raise

        self._templates = content.get("templates", {}) or {}
        self._default_settings = content.get("default_settings", {}) or {}
        self._validation = content.get("validation", {}) or {}
        self._last_mtime = self.template_path.stat().st_mtime
        logger.info(
            "Document templates loaded (%d templates)", len(self._templates)
        )

    def _ensure_fresh(self) -> None:
        if not self.template_path.exists():
            return
        current_mtime = self.template_path.stat().st_mtime
        if current_mtime > self._last_mtime:
            self.refresh()

    def list_templates(self) -> List[DocumentTemplateSummary]:
        self._ensure_fresh()
        summaries: List[DocumentTemplateSummary] = []
        for name, template in self._templates.items():
            summaries.append(
                DocumentTemplateSummary(
                    name=name,
                    description=template.get("description", ""),
                    output_formats=template.get("output_formats", []),
                    has_appendices="appendices" in template.get("layout", {}),
                )
            )
        return summaries

    def get_template(self, template_name: str) -> Dict[str, Any]:
        self._ensure_fresh()
        if template_name not in self._templates:
            raise KeyError(f"Template '{template_name}' not found")
        return self._templates[template_name]

    @property
    def default_settings(self) -> Dict[str, Any]:
        self._ensure_fresh()
        return self._default_settings

    @property
    def validation_rules(self) -> Dict[str, Any]:
        self._ensure_fresh()
        return self._validation


class DocumentOrchestrator:
    """
    Coordinates document template rendering, metadata recording, and attachment storage.
    """

    def __init__(
        self,
        storage_manager: Optional[StorageManager] = None,
        template_path: Path = DEFAULT_TEMPLATE_PATH,
    ):
        self.storage_manager = storage_manager or StorageManager()
        self.template_registry = DocumentTemplateRegistry(template_path)
        defaults = self.template_registry.default_settings
        self._project_column_cache: Dict[str, bool] = {}

        self.output_root = self._ensure_directory(
            defaults.get("output_path", "data/generated_documents")
        )
        attachment_storage = defaults.get("attachment_storage", {})
        attachments_path = attachment_storage.get("path") or defaults.get(
            "attachments_path", "data/attachments"
        )
        self.attachments_root = self._ensure_directory(attachments_path)
        self.lineage_fields: Iterable[str] = defaults.get(
            "lineage_fields", ["source_tables", "rule_versions", "generated_by"]
        )
        self.chunk_size = int(attachment_storage.get("chunk_size", 1024 * 1024))
        self.max_file_size = int(
            attachment_storage.get("max_file_size", 5 * 1024 * 1024 * 1024)
        )

        encryption_conf = attachment_storage.get("encryption", {}) or {}
        self.encryption_manager: Optional[AttachmentEncryptionManager] = None
        if encryption_conf.get("enabled"):
            try:
                config = EncryptionConfig(
                    enabled=True,
                    algorithm=encryption_conf.get("algorithm", "xor"),
                    key=encryption_conf.get("key"),
                    key_env_var=encryption_conf.get("key_env_var", "DAP_ATTACHMENT_KEY"),
                    key_id=encryption_conf.get("key_id"),
                )
                self.encryption_manager = AttachmentEncryptionManager(config)
                logger.info(
                    "Attachment encryption enabled using %s",
                    self.encryption_manager.algorithm,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to initialise encryption manager: %s", exc)
                self.encryption_manager = None

    def _ensure_project_context(self, project_id: Optional[str]) -> str:
        """
        Align the storage manager's current project with the requested identifier.
        """
        target = project_id or getattr(
            self.storage_manager, "DEFAULT_PROJECT_ID", None
        )
        if not target:
            target = self.storage_manager.get_current_project_id()
        try:
            self.storage_manager.set_current_project(target)
        except ValueError as exc:
            logger.error("Project %s not found in storage manager", target)
            raise
        return self.storage_manager.get_current_project_id()

    def _table_has_project_column(self, table: str) -> bool:
        """Check once whether the given table stores project_id."""
        cached = self._project_column_cache.get(table)
        if cached is not None:
            return cached
        has_column = False
        column_check = getattr(self.storage_manager, "_column_exists", None)
        if callable(column_check):
            try:
                has_column = bool(column_check(table, "project_id"))
            except Exception:
                has_column = False
        self._project_column_cache[table] = has_column
        return has_column
    def _ensure_directory(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_templates(self) -> List[Dict[str, Any]]:
        """Expose template summaries."""
        return [
            {
                "name": summary.name,
                "description": summary.description,
                "output_formats": summary.output_formats,
                "has_appendices": summary.has_appendices,
            }
            for summary in self.template_registry.list_templates()
        ]

    def list_documents(
        self,
        *,
        project_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent document metadata filtered by project or type."""
        resolved_project_id = self._ensure_project_context(project_id)
        query = [
            "SELECT document_id, doc_type, project_id, company_id, template_name,",
            "status, storage_path, format, generated_by, generated_at, metadata",
            "FROM audit_documents",
        ]
        params: List[Any] = []
        predicates: List[str] = []

        if resolved_project_id:
            predicates.append("project_id = ?")
            params.append(resolved_project_id)
        if doc_type:
            predicates.append("doc_type = ?")
            params.append(doc_type)

        if predicates:
            query.append("WHERE " + " AND ".join(predicates))
        query.append("ORDER BY generated_at DESC")
        if limit > 0:
            query.append("LIMIT ?")
            params.append(limit)

        sql = " ".join(query)
        with self.storage_manager.connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for record in records:
            metadata = record.get("metadata")
            if isinstance(metadata, str):
                try:
                    record["metadata"] = json.loads(metadata)
                except json.JSONDecodeError:
                    record["metadata"] = {}
        return records

    def get_document(
        self, document_id: str, *, project_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single document record with versions."""
        resolved_project_id = self._ensure_project_context(project_id)
        base_query = (
            "SELECT document_id, doc_type, project_id, company_id, template_name, "
            "status, storage_path, format, generated_by, generated_at, "
            "updated_at, metadata FROM audit_documents "
            "WHERE document_id = ? AND project_id = ?"
        )
        versions_query = (
            "SELECT version_id, version_number, storage_path, checksum, format, "
            "notes, created_by, created_at, metadata "
            "FROM audit_document_versions WHERE document_id = ? "
            "ORDER BY version_number DESC"
        )

        with self.storage_manager.connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(base_query, (document_id, resolved_project_id))
            row = cursor.fetchone()
            if not row:
                return None

            columns = [col[0] for col in cursor.description]
            record = dict(zip(columns, row))

            cursor.execute(versions_query, (document_id,))
            version_columns = [col[0] for col in cursor.description]
            versions = [dict(zip(version_columns, vrow)) for vrow in cursor.fetchall()]

        for entry in [record, *versions]:
            meta = entry.get("metadata")
            if isinstance(meta, str):
                try:
                    entry["metadata"] = json.loads(meta)
                except json.JSONDecodeError:
                    entry["metadata"] = {}
        record["versions"] = versions
        return record

    def generate_document(
        self,
        template_name: str,
        *,
        project_id: Optional[str] = None,
        company_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a template, materialise a JSON payload, and register metadata.
        """
        template = self.template_registry.get_template(template_name)

        resolved_project_id = self._ensure_project_context(project_id)
        context = {
            "project_id": resolved_project_id,
            "company_id": company_id,
            **(parameters or {}),
        }

        bindings = self._collect_bindings(template.get("data_bindings", {}), context)
        document_id = str(uuid.uuid4())
        generated_at = datetime.utcnow().isoformat()

        payload = {
            "document_id": document_id,
            "template_name": template_name,
            "generated_at": generated_at,
            "context": context,
            "data": bindings,
            "intended_formats": template.get("output_formats", []),
        }

        storage_path = self._materialise_payload(document_id, payload)
        metadata = {
            "template": template_name,
            "bindings": list(bindings.keys()),
            "requested_by": requested_by,
            "lineage": {
                field: context.get(field)
                for field in self.lineage_fields
                if context.get(field) is not None
            },
        }

        self._insert_document_records(
            document_id=document_id,
            template_name=template_name,
            project_id=resolved_project_id,
            company_id=company_id,
            storage_path=storage_path,
            metadata=metadata,
            requested_by=requested_by,
       )

        return {
            "document_id": document_id,
            "doc_type": template_name,
            "status": "generated",
            "storage_path": storage_path,
            "format": "json",
            "metadata": metadata,
            "generated_at": generated_at,
            "project_id": resolved_project_id,
        }

    def _collect_bindings(
        self, bindings_config: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for name, config in bindings_config.items():
            try:
                results[name] = self._resolve_binding(config, params)
            except Exception as exc:
                logger.error("Failed to resolve binding %s: %s", name, exc)
                results[name] = {"error": str(exc)}
        return results

    def _resolve_binding(self, config: Any, params: Dict[str, Any]) -> Any:
        if isinstance(config, dict):
            if "query" in config:
                return self._execute_query(config["query"], params)
            if "source" in config:
                return self._fetch_table(
                    source=config["source"],
                    select=config.get("select"),
                    filters=config.get("filters"),
                    params=params,
                    limit=config.get("limit", 1000),
                )
        return config

    def _execute_query(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        cleaned_params = {k: v for k, v in params.items() if v is not None}
        with self.storage_manager.connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, cleaned_params)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _fetch_table(
        self,
        *,
        source: str,
        select: Optional[Iterable[str]],
        filters: Optional[Dict[str, str]],
        params: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        safe_table = SQLQueryValidator.validate_table_name(source)
        if select:
            safe_columns = [
                f"\"{SQLQueryValidator.validate_column_name(col)}\"" for col in select
            ]
            column_clause = ", ".join(safe_columns)
        else:
            column_clause = "*"

        query_parts = [f"SELECT {column_clause} FROM {safe_table}"]
        query_params: List[Any] = []
        if filters:
            where_clauses: List[str] = []
            for key, param_name in filters.items():
                safe_col = SQLQueryValidator.validate_column_name(key)
                if params.get(param_name) is not None:
                    where_clauses.append(f"\"{safe_col}\" = ?")
                    query_params.append(params[param_name])
            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))
        if limit > 0:
            query_parts.append(f"LIMIT {int(limit)}")

        sql = " ".join(query_parts)
        with self.storage_manager.connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, query_params)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _materialise_payload(self, document_id: str, payload: Dict[str, Any]) -> str:
        filename = f"{document_id}.json"
        file_path = self.output_root / filename
        with file_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        try:
            relative_path = os.path.relpath(file_path, REPO_ROOT)
        except ValueError:
            relative_path = str(file_path)
        return relative_path.replace("\\", "/")

    def _insert_document_records(
        self,
        *,
        document_id: str,
        template_name: str,
        project_id: Optional[str],
        company_id: Optional[str],
        storage_path: str,
        metadata: Dict[str, Any],
        requested_by: Optional[str],
    ) -> None:
        with self.storage_manager.connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_documents (
                    document_id, doc_type, project_id, company_id, template_name,
                    status, storage_path, checksum, format, generated_by,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    template_name,
                    project_id,
                    company_id,
                    template_name,
                    "generated",
                    storage_path,
                    None,
                    "json",
                    requested_by,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            cursor.execute(
                """
                INSERT INTO audit_document_versions (
                    document_id, version_number, storage_path, checksum,
                    format, notes, created_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    1,
                    storage_path,
                    None,
                    "json",
                    "Initial auto-generated version",
                    requested_by,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            conn.commit()

    def save_attachment(
        self,
        *,
        file_stream,
        original_filename: str,
        category: Optional[str] = None,
        voucher_id: Optional[str] = None,
        target_table: Optional[str] = None,
        target_record_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        uploaded_by: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist attachment file and metadata."""
        resolved_project_id = self._ensure_project_context(project_id)
        attachment_id = str(uuid.uuid4())
        suffix = Path(original_filename).suffix or ".bin"
        folder = self.attachments_root / (category or "general")
        folder.mkdir(parents=True, exist_ok=True)
        stored_name = f"{attachment_id}{suffix}"
        destination = folder / stored_name

        file_stream.seek(0, os.SEEK_END)
        original_size = file_stream.tell()
        file_stream.seek(0)

        if original_size > self.max_file_size:
            raise ValueError("Attachment exceeds configured size limit")

        checksum = hashlib.sha256()
        if self.encryption_manager:
            with destination.open("wb") as handle:
                bytes_read, bytes_written = self.encryption_manager.encrypt_stream(
                    file_stream, handle, self.chunk_size, checksum
                )
            encryption_key_id = self.encryption_manager.export_key_material()
            upload_status = "encrypted"
        else:
            bytes_read = 0
            bytes_written = 0
            with destination.open("wb") as handle:
                while True:
                    chunk = file_stream.read(self.chunk_size)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    checksum.update(chunk)
                    handle.write(chunk)
                    bytes_written += len(chunk)
            encryption_key_id = None
            upload_status = "uploaded"

        file_size = bytes_written
        try:
            relative_path = os.path.relpath(destination, REPO_ROOT)
        except ValueError:
            relative_path = str(destination)
        relative_path = relative_path.replace("\\", "/")

        metadata_payload = metadata or {}
        metadata_payload = {
            **metadata_payload,
            "original_size": bytes_read,
            "checksum": checksum.hexdigest(),
        }
        metadata_payload.setdefault("project_id", resolved_project_id)
        if self.encryption_manager:
            metadata_payload["encryption"] = {
                "algorithm": self.encryption_manager.algorithm,
                "key_id": encryption_key_id,
            }

        metadata_json = json.dumps(metadata_payload, ensure_ascii=False)
        include_project_col = self._table_has_project_column("attachments")
        include_link_project_col = self._table_has_project_column("attachment_links")
        attachment_columns = [
            "attachment_id",
            "source_table",
            "source_record_id",
            "voucher_id",
            "category",
            "file_name",
            "storage_path",
            "storage_backend",
            "mime_type",
            "file_size",
            "checksum",
            "encryption_key_id",
            "upload_status",
            "uploaded_by",
            "metadata",
        ]
        attachment_values = [
            attachment_id,
            target_table,
            target_record_id,
            voucher_id,
            category,
            original_filename,
            relative_path,
            "local",
            self._guess_mime_type(original_filename),
            file_size,
            checksum.hexdigest(),
            encryption_key_id,
            upload_status,
            uploaded_by,
            metadata_json,
        ]
        if include_project_col:
            attachment_columns.append("project_id")
            attachment_values.append(resolved_project_id)

        attachment_columns_clause = ", ".join(attachment_columns)
        attachment_placeholders = ", ".join(["?"] * len(attachment_columns))

        with self.storage_manager.connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO attachments (
                    {attachment_columns_clause}
                ) VALUES ({attachment_placeholders})
                """,
                attachment_values,
            )

            if target_table and target_record_id:
                link_columns = [
                    "attachment_id",
                    "target_table",
                    "target_record_id",
                    "relation_type",
                ]
                link_values = [
                    attachment_id,
                    target_table,
                    target_record_id,
                    "primary",
                ]
                if include_link_project_col:
                    link_columns.append("project_id")
                    link_values.append(resolved_project_id)
                link_columns_clause = ", ".join(link_columns)
                link_placeholders = ", ".join(["?"] * len(link_columns))
                cursor.execute(
                    f"""
                    INSERT INTO attachment_links (
                        {link_columns_clause}
                    ) VALUES ({link_placeholders})
                    """,
                    link_values,
                )

            conn.commit()

        return {
            "attachment_id": attachment_id,
            "file_name": original_filename,
            "storage_path": relative_path,
            "file_size": file_size,
            "voucher_id": voucher_id,
            "category": category,
            "metadata": metadata_payload,
            "project_id": resolved_project_id,
        }

    def list_attachments(
        self,
        *,
        voucher_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch attachment metadata for UI display."""
        resolved_project_id = self._ensure_project_context(project_id)
        query = [
            "SELECT attachment_id, voucher_id, category, file_name, storage_path,",
            "file_size, uploaded_by, uploaded_at, metadata",
            "FROM attachments",
        ]
        params: List[Any] = []
        predicates: List[str] = []
        if self._table_has_project_column("attachments") and resolved_project_id:
            predicates.append("project_id = ?")
            params.append(resolved_project_id)
        if voucher_id:
            predicates.append("voucher_id = ?")
            params.append(voucher_id)
        if category:
            predicates.append("category = ?")
            params.append(category)
        if predicates:
            query.append("WHERE " + " AND ".join(predicates))
        query.append("ORDER BY uploaded_at DESC")
        if limit > 0:
            query.append("LIMIT ?")
            params.append(limit)

        sql = " ".join(query)
        with self.storage_manager.connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for record in records:
            meta = record.get("metadata")
            if isinstance(meta, str):
                try:
                    record["metadata"] = json.loads(meta)
                except json.JSONDecodeError:
                    record["metadata"] = {}
            if resolved_project_id:
                record.setdefault("project_id", resolved_project_id)
        return records

    def _guess_mime_type(self, filename: str) -> Optional[str]:
        import mimetypes

        mime, _ = mimetypes.guess_type(filename)
        return mime

    def close(self) -> None:
        """Release resources held by the storage manager."""
        try:
            self.storage_manager.close()
        except Exception as exc:
            logger.warning("Failed to close storage manager: %s", exc)
