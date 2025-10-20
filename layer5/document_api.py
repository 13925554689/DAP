"""
FastAPI router exposing document generation and attachment services.
"""

from __future__ import annotations

import logging
from functools import lru_cache
import json
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
    from pydantic import BaseModel, Field

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - FastAPI not installed in all environments
    FASTAPI_AVAILABLE = False

from layer4.document_orchestrator import DocumentOrchestrator

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_orchestrator() -> DocumentOrchestrator:
    """Singleton orchestrator instance reused across requests."""
    return DocumentOrchestrator()


if FASTAPI_AVAILABLE:

    class DocumentGenerateRequest(BaseModel):
        template_name: str = Field(..., description="模板名称")
        project_id: Optional[str] = Field(None, description="项目ID")
        company_id: Optional[str] = Field(None, description="公司ID")
        parameters: Dict[str, Any] = Field(default_factory=dict, description="附加参数")
        requested_by: Optional[str] = Field(None, description="生成人")

    class DocumentGenerateResponse(BaseModel):
        document_id: str
        doc_type: str
        status: str
        storage_path: str
        format: str
        metadata: Dict[str, Any]
        generated_at: str
        project_id: str

    class DocumentListResponse(BaseModel):
        documents: List[Dict[str, Any]]

    class AttachmentUploadResponse(BaseModel):
        attachment_id: str
        file_name: str
        storage_path: str
        file_size: int
        voucher_id: Optional[str]
        category: Optional[str]
        metadata: Dict[str, Any]
        project_id: str

    router = APIRouter(prefix="/documents", tags=["Documents"])

    @router.get("/templates")
    async def list_templates(orchestrator: DocumentOrchestrator = Depends(get_orchestrator)):
        """列出可用模板。"""
        return {"templates": orchestrator.list_templates()}

    @router.post("/generate", response_model=DocumentGenerateResponse)
    async def generate_document(
        request: DocumentGenerateRequest,
        orchestrator: DocumentOrchestrator = Depends(get_orchestrator),
    ):
        """根据模板生成文档元数据并返回存储信息。"""
        try:
            result = orchestrator.generate_document(
                template_name=request.template_name,
                project_id=request.project_id,
                company_id=request.company_id,
                parameters=request.parameters,
                requested_by=request.requested_by,
            )
            return result
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Document generation failed: %s", exc)
            raise HTTPException(status_code=500, detail="文档生成失败") from exc

    @router.get("", response_model=DocumentListResponse)
    async def list_documents(
        project_id: str = Query(..., description="项目ID"),
        doc_type: Optional[str] = None,
        limit: int = 100,
        orchestrator: DocumentOrchestrator = Depends(get_orchestrator),
    ):
        """按项目或类型过滤文档列表。"""
        documents = orchestrator.list_documents(
            project_id=project_id, doc_type=doc_type, limit=limit
        )
        return {"documents": documents}

    @router.get("/{document_id}")
    async def get_document(
        document_id: str,
        project_id: str = Query(..., description="项目ID"),
        orchestrator: DocumentOrchestrator = Depends(get_orchestrator),
    ):
        """获取单个文档详情。"""
        document = orchestrator.get_document(document_id, project_id=project_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        return document

    @router.post("/attachments/upload", response_model=AttachmentUploadResponse)
    async def upload_attachment(
        voucher_id: Optional[str] = None,
        category: Optional[str] = None,
        target_table: Optional[str] = None,
        target_record_id: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        metadata: Optional[str] = None,
        file: UploadFile = File(...),
        project_id: str = Form(..., description="项目ID"),
        orchestrator: DocumentOrchestrator = Depends(get_orchestrator),
    ):
        """上传附件并写入数据库。"""
        try:
            file.file.seek(0)
            metadata_dict: Dict[str, Any] = {}
            if metadata:
                metadata_dict = json.loads(metadata)

            saved = orchestrator.save_attachment(
                file_stream=file.file,
                original_filename=file.filename or "attachment.bin",
                category=category,
                voucher_id=voucher_id,
                target_table=target_table,
                target_record_id=target_record_id,
                metadata=metadata_dict,
                uploaded_by=uploaded_by,
                project_id=project_id,
            )
            return saved
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="metadata 字段需要合法的 JSON") from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Attachment upload failed: %s", exc)
            raise HTTPException(status_code=500, detail="附件上传失败") from exc
        finally:
            await file.close()

else:
    router = None
