"""
DAP v2.0 - Evidence Management API
审计证据管理API路由 - 28个端点
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
import os
from pathlib import Path

from ..models import (
    Evidence, EvidenceType, EvidenceSource, EvidenceStatus,
    EvidenceField, EvidenceAttachment, EvidenceRelation,
    EvidenceAuditTrail, EvidenceVersion, EvidenceTemplate,
    EvidenceCategory, get_db
)
from ..config import settings
from ..ai.unified_learning_manager import UnifiedLearningManager
from ..ai.deepseek_client import DeepSeekClient
from ..ai.paddleocr_service import get_ocr_service
from ..ai.auto_linking_service import get_auto_linking_service
from ..ai.batch_processing import get_batch_service
from ..ai.export_service import get_export_service

router = APIRouter(prefix="/evidence", tags=["审计证据管理"])

# 初始化AI服务
learning_manager = UnifiedLearningManager()
deepseek_client = DeepSeekClient()
ocr_service = get_ocr_service()
linking_service = get_auto_linking_service()
batch_service = get_batch_service()
export_service = get_export_service()


# ===== 1-10: 证据CRUD操作 =====

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_evidence(
    evidence_name: str = Form(...),
    evidence_type: EvidenceType = Form(...),
    project_id: str = Form(...),
    client_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"  # TODO: from auth
):
    """1. 创建新证据"""
    try:
        # 生成证据编号
        evidence_code = f"EV{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 处理文件上传
        file_path, file_hash = None, None
        if file:
            upload_dir = Path(settings.UPLOAD_DIR) / "evidence" / project_id
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_path = str(upload_dir / f"{evidence_code}_{file.filename}")
            content = await file.read()

            # 计算文件哈希
            file_hash = hashlib.sha256(content).hexdigest()

            # 保存文件
            with open(file_path, "wb") as f:
                f.write(content)

        # 创建证据记录
        evidence = Evidence(
            evidence_code=evidence_code,
            evidence_name=evidence_name,
            evidence_type=evidence_type,
            project_id=project_id,
            client_id=client_id,
            uploaded_by=current_user_id,
            file_path=file_path,
            file_name=file.filename if file else None,
            file_size=len(content) if file else None,
            file_hash=file_hash,
            status=EvidenceStatus.PENDING
        )

        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        return {"message": "证据创建成功", "evidence_id": evidence.id, "evidence_code": evidence_code}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建证据失败: {str(e)}")


@router.get("/")
async def list_evidences(
    project_id: Optional[str] = Query(None),
    status_filter: Optional[EvidenceStatus] = Query(None),
    evidence_type: Optional[EvidenceType] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db)
):
    """2. 获取证据列表 (支持过滤和分页)"""
    query = db.query(Evidence)

    if project_id:
        query = query.filter(Evidence.project_id == project_id)
    if status_filter:
        query = query.filter(Evidence.status == status_filter)
    if evidence_type:
        query = query.filter(Evidence.evidence_type == evidence_type)

    total = query.count()
    evidences = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "evidences": [
            {
                "id": e.id,
                "evidence_code": e.evidence_code,
                "evidence_name": e.evidence_name,
                "evidence_type": e.evidence_type.value,
                "status": e.status.value,
                "created_at": e.created_at.isoformat()
            }
            for e in evidences
        ]
    }


@router.get("/{evidence_id}")
async def get_evidence(evidence_id: str, db: Session = Depends(get_db)):
    """3. 获取单个证据详情"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    return {
        "id": evidence.id,
        "evidence_code": evidence.evidence_code,
        "evidence_name": evidence.evidence_name,
        "evidence_type": evidence.evidence_type.value,
        "evidence_source": evidence.evidence_source.value,
        "status": evidence.status.value,
        "project_id": evidence.project_id,
        "client_id": evidence.client_id,
        "file_name": evidence.file_name,
        "file_size": evidence.file_size,
        "content_text": evidence.content_text,
        "summary": evidence.summary,
        "keywords": evidence.keywords,
        "ocr_text": evidence.ocr_text,
        "ocr_confidence": evidence.ocr_confidence,
        "ai_classification": evidence.ai_classification,
        "ai_confidence": evidence.ai_confidence,
        "ai_extracted_fields": evidence.ai_extracted_fields,
        "is_key_evidence": evidence.is_key_evidence,
        "created_at": evidence.created_at.isoformat(),
        "updated_at": evidence.updated_at.isoformat()
    }


@router.put("/{evidence_id}")
async def update_evidence(
    evidence_id: str,
    evidence_name: Optional[str] = Form(None),
    status_update: Optional[EvidenceStatus] = Form(None),
    summary: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_key_evidence: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """4. 更新证据信息"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 记录审计追踪
    changes = []

    if evidence_name:
        changes.append(("evidence_name", evidence.evidence_name, evidence_name))
        evidence.evidence_name = evidence_name
    if status_update:
        changes.append(("status", evidence.status.value, status_update.value))
        evidence.status = status_update
    if summary:
        evidence.summary = summary
    if tags:
        evidence.tags = tags
    if is_key_evidence is not None:
        evidence.is_key_evidence = is_key_evidence

    # 保存审计追踪
    for field, old_val, new_val in changes:
        audit_entry = EvidenceAuditTrail(
            evidence_id=evidence_id,
            action="UPDATE",
            action_description=f"更新{field}",
            old_value=str(old_val),
            new_value=str(new_val),
            performed_by=current_user_id
        )
        db.add(audit_entry)

    db.commit()
    return {"message": "证据更新成功"}


@router.delete("/{evidence_id}")
async def delete_evidence(evidence_id: str, db: Session = Depends(get_db), current_user_id: str = "admin"):
    """5. 删除证据"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 记录删除操作
    audit_entry = EvidenceAuditTrail(
        evidence_id=evidence_id,
        action="DELETE",
        action_description="删除证据",
        performed_by=current_user_id
    )
    db.add(audit_entry)

    db.delete(evidence)
    db.commit()

    return {"message": "证据删除成功"}


# ===== 6-10: 文件操作 =====

@router.get("/{evidence_id}/download")
async def download_evidence_file(evidence_id: str, db: Session = Depends(get_db)):
    """6. 下载证据文件"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence or not evidence.file_path:
        raise HTTPException(status_code=404, detail="文件不存在")

    if not os.path.exists(evidence.file_path):
        raise HTTPException(status_code=404, detail="文件已丢失")

    return FileResponse(evidence.file_path, filename=evidence.file_name)


@router.post("/{evidence_id}/ocr")
async def ocr_extract(evidence_id: str, db: Session = Depends(get_db), current_user_id: str = "admin"):
    """7. OCR文字提取"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    if not evidence.file_path or not os.path.exists(evidence.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        # 使用PaddleOCR提取文字
        ocr_result = ocr_service.extract_text(
            evidence.file_path,
            return_boxes=True,
            return_confidence=True
        )

        if 'error' in ocr_result:
            raise HTTPException(status_code=500, detail=f"OCR提取失败: {ocr_result['error']}")

        # 更新证据信息
        evidence.ocr_text = ocr_result['text']
        evidence.ocr_confidence = ocr_result['confidence']
        evidence.content_text = ocr_result['text']
        evidence.status = EvidenceStatus.PROCESSING

        # 保存详细信息到字段表
        for idx, detail in enumerate(ocr_result.get('details', [])):
            field = EvidenceField(
                evidence_id=evidence_id,
                field_name=f"line_{idx + 1}",
                field_value=detail['text'],
                field_type="text",
                extraction_method="OCR",
                confidence=detail['confidence'],
                position_x=int(detail['box'][0][0]),
                position_y=int(detail['box'][0][1]),
                position_width=int(detail['box'][1][0] - detail['box'][0][0]),
                position_height=int(detail['box'][2][1] - detail['box'][0][1])
            )
            db.add(field)

        db.commit()

        return {
            "message": "OCR提取完成",
            "ocr_text": ocr_result['text'],
            "confidence": ocr_result['confidence'],
            "line_count": ocr_result['line_count'],
            "lines": ocr_result['lines']
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"OCR提取失败: {str(e)}")


@router.post("/{evidence_id}/ocr/correct")
async def ocr_correct(
    evidence_id: str,
    corrected_text: str = Form(...),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """8. OCR纠错并学习"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    original_text = evidence.ocr_text

    # 更新纠正后的文本
    evidence.ocr_corrected_text = corrected_text
    evidence.ocr_corrected = True

    # AI学习
    learning_result = await learning_manager.learn_from_ocr_correction(
        original_text=original_text,
        corrected_text=corrected_text,
        evidence_id=evidence_id,
        user_id=current_user_id
    )

    db.commit()

    return {
        "message": "OCR纠错成功,已加入学习样本",
        "learning_status": learning_result
    }


@router.post("/{evidence_id}/ai-analyze")
async def ai_analyze_evidence(evidence_id: str, db: Session = Depends(get_db)):
    """9. AI智能分析证据"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 使用DeepSeek分析
    analysis_result = await deepseek_client.analyze_evidence(
        evidence_text=evidence.ocr_corrected_text or evidence.ocr_text or evidence.content_text or "",
        context={"project_id": evidence.project_id, "evidence_type": evidence.evidence_type.value}
    )

    # TODO: 解析AI返回结果并更新

    evidence.status = EvidenceStatus.PROCESSED

    db.commit()

    return {
        "message": "AI分析完成",
        "analysis": analysis_result
    }


@router.post("/{evidence_id}/classify")
async def classify_evidence(
    evidence_id: str,
    user_classification: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """10. 证据分类 (AI+人工)"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # AI自动分类
    categories = ["银行对账单", "发票", "合同", "凭证", "报表", "说明", "其他"]
    ai_result = await deepseek_client.classify_evidence(
        evidence_text=evidence.content_text or "",
        categories=categories
    )

    ai_classification = None  # TODO: 从ai_result解析

    # 如果有人工分类,使用人工分类并学习
    if user_classification:
        # AI学习
        await learning_manager.learn_from_evidence_classification(
            evidence_text=evidence.content_text or "",
            user_classification=user_classification,
            ai_classification=ai_classification,
            evidence_id=evidence_id,
            user_id=current_user_id
        )

    evidence.ai_classification = ai_classification or user_classification

    db.commit()

    return {
        "message": "证据分类完成",
        "ai_classification": ai_classification,
        "user_classification": user_classification
    }


# ===== 11-15: 字段提取 =====

@router.get("/{evidence_id}/fields")
async def get_evidence_fields(evidence_id: str, db: Session = Depends(get_db)):
    """11. 获取证据字段列表"""
    fields = db.query(EvidenceField).filter(EvidenceField.evidence_id == evidence_id).all()

    return {
        "total": len(fields),
        "fields": [
            {
                "id": f.id,
                "field_name": f.field_name,
                "field_value": f.field_value,
                "extraction_method": f.extraction_method,
                "confidence": f.confidence,
                "is_verified": f.is_verified
            }
            for f in fields
        ]
    }


@router.post("/{evidence_id}/fields")
async def extract_evidence_fields(
    evidence_id: str,
    target_fields: List[str] = Form(...),
    db: Session = Depends(get_db)
):
    """12. AI提取证据字段"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 使用DeepSeek提取字段
    extraction_result = await deepseek_client.extract_fields(
        evidence_text=evidence.content_text or "",
        target_fields=target_fields
    )

    # TODO: 解析提取结果并保存到EvidenceField表

    return {
        "message": "字段提取完成",
        "extracted_fields": extraction_result
    }


@router.put("/fields/{field_id}/verify")
async def verify_field(
    field_id: str,
    verified_value: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """13. 人工验证字段"""
    field = db.query(EvidenceField).filter(EvidenceField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")

    if verified_value:
        field.field_value = verified_value

    field.is_verified = True
    field.verified_by = current_user_id
    field.verified_at = datetime.utcnow()

    db.commit()

    return {"message": "字段验证完成"}


@router.delete("/fields/{field_id}")
async def delete_field(field_id: str, db: Session = Depends(get_db)):
    """14. 删除字段"""
    field = db.query(EvidenceField).filter(EvidenceField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")

    db.delete(field)
    db.commit()

    return {"message": "字段删除成功"}


@router.post("/{evidence_id}/fields/batch")
async def batch_add_fields(
    evidence_id: str,
    fields_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """15. 批量添加字段"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    for field_data in fields_data:
        field = EvidenceField(
            evidence_id=evidence_id,
            field_name=field_data.get("field_name"),
            field_value=field_data.get("field_value"),
            field_type=field_data.get("field_type"),
            extraction_method=field_data.get("extraction_method", "Manual")
        )
        db.add(field)

    db.commit()

    return {"message": f"成功添加{len(fields_data)}个字段"}


# ===== 16-20: 证据关联 =====

@router.get("/{evidence_id}/relations")
async def get_evidence_relations(evidence_id: str, db: Session = Depends(get_db)):
    """16. 获取证据关联关系"""
    relations = db.query(EvidenceRelation).filter(EvidenceRelation.evidence_id == evidence_id).all()

    return {
        "total": len(relations),
        "relations": [
            {
                "id": r.id,
                "related_evidence_id": r.related_evidence_id,
                "relation_type": r.relation_type,
                "confidence": r.confidence
            }
            for r in relations
        ]
    }


@router.post("/{evidence_id}/relations")
async def create_evidence_relation(
    evidence_id: str,
    related_evidence_id: str = Form(...),
    relation_type: str = Form(...),
    relation_description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """17. 创建证据关联"""
    relation = EvidenceRelation(
        evidence_id=evidence_id,
        related_evidence_id=related_evidence_id,
        relation_type=relation_type,
        relation_description=relation_description,
        created_by=current_user_id
    )

    db.add(relation)
    db.commit()

    return {"message": "证据关联创建成功"}


@router.delete("/relations/{relation_id}")
async def delete_evidence_relation(relation_id: str, db: Session = Depends(get_db)):
    """18. 删除证据关联"""
    relation = db.query(EvidenceRelation).filter(EvidenceRelation.id == relation_id).first()
    if not relation:
        raise HTTPException(status_code=404, detail="关联关系不存在")

    db.delete(relation)
    db.commit()

    return {"message": "关联关系删除成功"}


@router.post("/{evidence_id}/auto-link")
async def auto_link_evidences(evidence_id: str, db: Session = Depends(get_db)):
    """19. AI智能关联证据"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 获取同项目的所有证据
    all_evidences = db.query(Evidence).filter(
        Evidence.project_id == evidence.project_id,
        Evidence.id != evidence_id
    ).all()

    # 转换为字典格式
    current_evidence = {
        'id': evidence.id,
        'evidence_name': evidence.evidence_name,
        'evidence_type': evidence.evidence_type.value,
        'content_text': evidence.content_text or evidence.ocr_text or '',
        'amount': evidence.amount,
        'related_accounts': evidence.related_accounts,
        'created_at': evidence.created_at.isoformat()
    }

    other_evidences = [
        {
            'id': e.id,
            'evidence_name': e.evidence_name,
            'evidence_type': e.evidence_type.value,
            'content_text': e.content_text or e.ocr_text or '',
            'amount': e.amount,
            'related_accounts': e.related_accounts,
            'created_at': e.created_at.isoformat()
        }
        for e in all_evidences
    ]

    # 智能关联分析
    related_evidences = linking_service.find_related_evidences(
        current_evidence,
        other_evidences,
        max_results=10
    )

    return {
        "message": "智能关联分析完成",
        "evidence_id": evidence_id,
        "suggested_relations": related_evidences,
        "total_candidates": len(other_evidences)
    }


@router.get("/{evidence_id}/graph")
async def get_evidence_graph(evidence_id: str, depth: int = Query(2, ge=1, le=5), db: Session = Depends(get_db)):
    """20. 获取证据关系图谱"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 获取所有关联关系
    all_relations = db.query(EvidenceRelation).filter(
        (EvidenceRelation.evidence_id == evidence_id) |
        (EvidenceRelation.related_evidence_id == evidence_id)
    ).all()

    # 转换为字典格式
    relations_data = [
        {
            'evidence_id': r.evidence_id,
            'related_evidence_id': r.related_evidence_id,
            'relation_type': r.relation_type,
            'confidence': r.confidence or 1.0
        }
        for r in all_relations
    ]

    # 构建图谱
    graph = linking_service.build_evidence_graph(
        evidence_id,
        relations_data,
        depth=depth
    )

    # 补充节点信息
    node_ids = [node['id'] for node in graph['nodes']]
    evidences = db.query(Evidence).filter(Evidence.id.in_(node_ids)).all()

    evidence_map = {
        e.id: {
            'evidence_name': e.evidence_name,
            'evidence_type': e.evidence_type.value,
            'status': e.status.value,
            'created_at': e.created_at.isoformat()
        }
        for e in evidences
    }

    # 更新节点信息
    for node in graph['nodes']:
        if node['id'] in evidence_map:
            node.update(evidence_map[node['id']])

    return {
        "message": "证据关系图谱生成完成",
        "graph": graph
    }


# ===== 21-25: 版本和审计追踪 =====

@router.get("/{evidence_id}/versions")
async def get_evidence_versions(evidence_id: str, db: Session = Depends(get_db)):
    """21. 获取证据版本历史"""
    versions = db.query(EvidenceVersion).filter(EvidenceVersion.evidence_id == evidence_id).order_by(
        EvidenceVersion.version_number.desc()
    ).all()

    return {
        "total": len(versions),
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "change_description": v.change_description,
                "changed_at": v.changed_at.isoformat()
            }
            for v in versions
        ]
    }


@router.get("/{evidence_id}/audit-trail")
async def get_evidence_audit_trail(evidence_id: str, db: Session = Depends(get_db)):
    """22. 获取证据操作日志"""
    audit_entries = db.query(EvidenceAuditTrail).filter(
        EvidenceAuditTrail.evidence_id == evidence_id
    ).order_by(EvidenceAuditTrail.performed_at.desc()).all()

    return {
        "total": len(audit_entries),
        "audit_trail": [
            {
                "id": a.id,
                "action": a.action,
                "action_description": a.action_description,
                "performed_at": a.performed_at.isoformat(),
                "performed_by": a.performed_by
            }
            for a in audit_entries
        ]
    }


@router.post("/{evidence_id}/versions")
async def create_evidence_version(
    evidence_id: str,
    change_description: str = Form(...),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """23. 创建新版本"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 获取最新版本号
    latest_version = db.query(EvidenceVersion).filter(
        EvidenceVersion.evidence_id == evidence_id
    ).order_by(EvidenceVersion.version_number.desc()).first()

    next_version = (latest_version.version_number + 1) if latest_version else 1

    # 创建版本快照
    version = EvidenceVersion(
        evidence_id=evidence_id,
        version_number=next_version,
        content_snapshot={
            "evidence_name": evidence.evidence_name,
            "content_text": evidence.content_text,
            "summary": evidence.summary
        },
        change_description=change_description,
        changed_by=current_user_id
    )

    db.add(version)
    db.commit()

    return {"message": "版本创建成功", "version_number": next_version}


@router.post("/{evidence_id}/verify")
async def verify_evidence(
    evidence_id: str,
    verification_note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """24. 核验证据"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    evidence.status = EvidenceStatus.VERIFIED
    evidence.verified_by = current_user_id
    evidence.verified_at = datetime.utcnow()
    evidence.verification_note = verification_note

    # 记录审计追踪
    audit_entry = EvidenceAuditTrail(
        evidence_id=evidence_id,
        action="VERIFY",
        action_description="核验证据",
        performed_by=current_user_id
    )
    db.add(audit_entry)

    db.commit()

    return {"message": "证据核验完成"}


@router.post("/{evidence_id}/archive")
async def archive_evidence(evidence_id: str, db: Session = Depends(get_db), current_user_id: str = "admin"):
    """25. 归档证据"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    evidence.is_archived = True
    evidence.status = EvidenceStatus.ARCHIVED

    # 记录操作
    audit_entry = EvidenceAuditTrail(
        evidence_id=evidence_id,
        action="ARCHIVE",
        action_description="归档证据",
        performed_by=current_user_id
    )
    db.add(audit_entry)

    db.commit()

    return {"message": "证据已归档"}


# ===== 26-28: 统计和批量操作 =====

@router.get("/stats/summary")
async def get_evidence_stats(project_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """26. 获取证据统计信息"""
    query = db.query(Evidence)
    if project_id:
        query = query.filter(Evidence.project_id == project_id)

    total = query.count()
    by_type = db.query(Evidence.evidence_type, db.func.count()).group_by(Evidence.evidence_type).all()
    by_status = db.query(Evidence.status, db.func.count()).group_by(Evidence.status).all()

    return {
        "total": total,
        "by_type": {et.value: count for et, count in by_type},
        "by_status": {es.value: count for es, count in by_status},
        "key_evidence_count": query.filter(Evidence.is_key_evidence == True).count()
    }


@router.post("/batch/upload")
async def batch_upload_evidences(
    project_id: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """27. 批量上传证据"""
    results = []

    for file in files:
        try:
            evidence_code = f"EV{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            upload_dir = Path(settings.UPLOAD_DIR) / "evidence" / project_id
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_path = str(upload_dir / f"{evidence_code}_{file.filename}")
            content = await file.read()

            with open(file_path, "wb") as f:
                f.write(content)

            evidence = Evidence(
                evidence_code=evidence_code,
                evidence_name=file.filename,
                evidence_type=EvidenceType.OTHER,
                project_id=project_id,
                uploaded_by=current_user_id,
                file_path=file_path,
                file_name=file.filename,
                file_size=len(content),
                file_hash=hashlib.sha256(content).hexdigest()
            )

            db.add(evidence)
            results.append({"file": file.filename, "status": "success", "evidence_id": evidence.id})

        except Exception as e:
            results.append({"file": file.filename, "status": "failed", "error": str(e)})

    db.commit()

    return {
        "message": f"批量上传完成,成功{sum(1 for r in results if r['status'] == 'success')}个",
        "results": results
    }


@router.post("/batch/delete")
async def batch_delete_evidences(
    evidence_ids: List[str],
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """28. 批量删除证据"""
    deleted_count = 0

    for evidence_id in evidence_ids:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if evidence:
            # 记录删除操作
            audit_entry = EvidenceAuditTrail(
                evidence_id=evidence_id,
                action="DELETE",
                action_description="批量删除",
                performed_by=current_user_id
            )
            db.add(audit_entry)

            db.delete(evidence)
            deleted_count += 1

    db.commit()

    return {"message": f"成功删除{deleted_count}个证据"}
