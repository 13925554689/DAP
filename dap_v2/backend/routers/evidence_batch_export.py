# 在evidence.py文件末尾添加这些新端点

# ===== 29-35: 批量处理和导出 =====

from fastapi import BackgroundTasks
from fastapi.responses import FileResponse


@router.post("/batch/ocr")
async def batch_ocr_process(
    evidence_ids: List[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """29. 批量OCR处理"""
    # 创建批量任务
    task_id = batch_service.create_task('ocr_batch', len(evidence_ids))

    # 添加后台任务
    background_tasks.add_task(
        batch_service.process_batch_ocr,
        task_id,
        evidence_ids,
        ocr_service,
        db
    )

    return {
        'message': '批量OCR任务已创建',
        'task_id': task_id,
        'total_items': len(evidence_ids)
    }


@router.post("/batch/classify")
async def batch_classify(
    evidence_ids: List[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """30. 批量证据分类"""
    task_id = batch_service.create_task('classification_batch', len(evidence_ids))

    background_tasks.add_task(
        batch_service.process_batch_classification,
        task_id,
        evidence_ids,
        deepseek_client,
        db
    )

    return {
        'message': '批量分类任务已创建',
        'task_id': task_id,
        'total_items': len(evidence_ids)
    }


@router.get("/batch/tasks/{task_id}")
async def get_batch_task_status(task_id: str):
    """31. 获取批量任务状态"""
    status = batch_service.get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")

    return status


@router.get("/batch/tasks")
async def list_batch_tasks(status_filter: Optional[str] = Query(None), limit: int = Query(50, le=100)):
    """32. 列出批量任务"""
    from ..ai.batch_processing import TaskStatus

    status_enum = None
    if status_filter:
        try:
            status_enum = TaskStatus[status_filter.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"无效的状态: {status_filter}")

    tasks = batch_service.list_tasks(status=status_enum, limit=limit)

    return {
        'total': len(tasks),
        'tasks': tasks
    }


@router.post("/export/excel")
async def export_to_excel(
    project_id: Optional[str] = Query(None),
    evidence_type: Optional[EvidenceType] = Query(None),
    db: Session = Depends(get_db)
):
    """33. 导出为Excel"""
    query = db.query(Evidence)

    if project_id:
        query = query.filter(Evidence.project_id == project_id)
    if evidence_type:
        query = query.filter(Evidence.evidence_type == evidence_type)

    evidences = query.all()

    # 转换为字典列表
    evidence_dicts = [
        {
            'evidence_code': e.evidence_code,
            'evidence_name': e.evidence_name,
            'evidence_type': e.evidence_type.value,
            'evidence_source': e.evidence_source.value,
            'status': e.status.value,
            'amount': e.amount,
            'created_at': e.created_at.isoformat()
        }
        for e in evidences
    ]

    # 导出
    result = export_service.export_to_excel(evidence_dicts)

    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])

    return result


@router.get("/export/excel/{filename}")
async def download_excel(filename: str):
    """34. 下载Excel文件"""
    file_path = export_service.output_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@router.post("/{evidence_id}/export/pdf")
async def export_single_evidence_to_pdf(
    evidence_id: str,
    include_ocr: bool = Query(True),
    db: Session = Depends(get_db)
):
    """35. 导出单个证据为PDF"""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()

    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 转换为字典
    evidence_dict = {
        'evidence_code': evidence.evidence_code,
        'evidence_name': evidence.evidence_name,
        'evidence_type': evidence.evidence_type.value,
        'status': evidence.status.value,
        'ocr_text': evidence.ocr_text,
        'file_path': evidence.file_path
    }

    # 导出PDF
    result = export_service.export_to_pdf(evidence_dict, include_ocr=include_ocr)

    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])

    return result
