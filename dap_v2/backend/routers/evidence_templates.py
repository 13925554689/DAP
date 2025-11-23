"""
DAP v2.0 - Evidence Template Management API
审计证据模板管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import EvidenceTemplate, EvidenceType, get_db

router = APIRouter(prefix="/evidence/templates", tags=["证据模板管理"])


class TemplateCreate(BaseModel):
    """创建模板请求"""
    template_name: str
    evidence_type: str
    required_fields: List[dict]
    optional_fields: Optional[List[dict]] = []
    field_validations: Optional[dict] = {}
    description: Optional[str] = None


class TemplateUpdate(BaseModel):
    """更新模板请求"""
    template_name: Optional[str] = None
    required_fields: Optional[List[dict]] = None
    optional_fields: Optional[List[dict]] = None
    field_validations: Optional[dict] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/")
async def list_templates(
    is_active: Optional[bool] = None,
    evidence_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """1. 获取模板列表"""
    query = db.query(EvidenceTemplate)

    if is_active is not None:
        query = query.filter(EvidenceTemplate.is_active == is_active)

    if evidence_type:
        try:
            ev_type = EvidenceType[evidence_type]
            query = query.filter(EvidenceTemplate.evidence_type == ev_type)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"无效的证据类型: {evidence_type}")

    templates = query.all()

    return {
        'total': len(templates),
        'templates': [
            {
                'id': t.id,
                'template_name': t.template_name,
                'evidence_type': t.evidence_type.value,
                'required_fields': t.required_fields,
                'optional_fields': t.optional_fields,
                'is_active': t.is_active,
                'is_system': t.is_system,
                'created_at': t.created_at.isoformat()
            }
            for t in templates
        ]
    }


@router.get("/{template_id}")
async def get_template(template_id: str, db: Session = Depends(get_db)):
    """2. 获取模板详情"""
    template = db.query(EvidenceTemplate).filter(EvidenceTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    return {
        'id': template.id,
        'template_name': template.template_name,
        'evidence_type': template.evidence_type.value,
        'required_fields': template.required_fields,
        'optional_fields': template.optional_fields,
        'field_validations': template.field_validations,
        'description': template.description,
        'is_active': template.is_active,
        'is_system': template.is_system,
        'created_at': template.created_at.isoformat(),
        'updated_at': template.updated_at.isoformat()
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user_id: str = "admin"
):
    """3. 创建新模板"""
    # 检查模板名是否已存在
    existing = db.query(EvidenceTemplate).filter(
        EvidenceTemplate.template_name == template_data.template_name
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="模板名称已存在")

    # 转换证据类型
    try:
        ev_type = EvidenceType[template_data.evidence_type]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"无效的证据类型: {template_data.evidence_type}")

    # 创建模板
    template = EvidenceTemplate(
        template_name=template_data.template_name,
        evidence_type=ev_type,
        required_fields=template_data.required_fields,
        optional_fields=template_data.optional_fields or [],
        field_validations=template_data.field_validations or {},
        description=template_data.description,
        is_active=True,
        is_system=False,
        created_by=current_user_id
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        'message': '模板创建成功',
        'template_id': template.id,
        'template_name': template.template_name
    }


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db)
):
    """4. 更新模板"""
    template = db.query(EvidenceTemplate).filter(EvidenceTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if template.is_system:
        raise HTTPException(status_code=403, detail="系统模板不可修改")

    # 更新字段
    if template_data.template_name:
        template.template_name = template_data.template_name
    if template_data.required_fields is not None:
        template.required_fields = template_data.required_fields
    if template_data.optional_fields is not None:
        template.optional_fields = template_data.optional_fields
    if template_data.field_validations is not None:
        template.field_validations = template_data.field_validations
    if template_data.description is not None:
        template.description = template_data.description
    if template_data.is_active is not None:
        template.is_active = template_data.is_active

    db.commit()

    return {'message': '模板更新成功'}


@router.delete("/{template_id}")
async def delete_template(template_id: str, db: Session = Depends(get_db)):
    """5. 删除模板"""
    template = db.query(EvidenceTemplate).filter(EvidenceTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if template.is_system:
        raise HTTPException(status_code=403, detail="系统模板不可删除")

    db.delete(template)
    db.commit()

    return {'message': '模板删除成功'}


@router.post("/{template_id}/apply")
async def apply_template_to_evidence(
    template_id: str,
    evidence_id: str,
    db: Session = Depends(get_db)
):
    """6. 将模板应用到证据"""
    from models import Evidence, EvidenceField

    template = db.query(EvidenceTemplate).filter(EvidenceTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="证据不存在")

    # 根据模板创建字段
    created_fields = []

    for field_def in template.required_fields:
        field = EvidenceField(
            evidence_id=evidence_id,
            field_name=field_def.get('name'),
            field_type=field_def.get('type'),
            extraction_method='Template',
            confidence=1.0
        )
        db.add(field)
        created_fields.append(field_def.get('name'))

    db.commit()

    return {
        'message': '模板应用成功',
        'created_fields': created_fields
    }


@router.post("/{template_id}/validate")
async def validate_evidence_against_template(
    template_id: str,
    evidence_data: dict,
    db: Session = Depends(get_db)
):
    """7. 根据模板验证证据数据"""
    template = db.query(EvidenceTemplate).filter(EvidenceTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    validation_errors = []
    validation_warnings = []

    # 检查必填字段
    for required_field in template.required_fields:
        field_name = required_field.get('name')
        if field_name not in evidence_data or not evidence_data[field_name]:
            validation_errors.append(f"缺少必填字段: {field_name}")

    # 检查字段验证规则
    validations = template.field_validations or {}
    for field_name, rules in validations.items():
        if field_name in evidence_data:
            value = evidence_data[field_name]

            # 类型验证
            if 'type' in rules:
                expected_type = rules['type']
                # TODO: 实现类型检查

            # 范围验证
            if 'min' in rules and value < rules['min']:
                validation_errors.append(f"{field_name}值小于最小值{rules['min']}")
            if 'max' in rules and value > rules['max']:
                validation_errors.append(f"{field_name}值大于最大值{rules['max']}")

            # 正则验证
            if 'pattern' in rules:
                import re
                if not re.match(rules['pattern'], str(value)):
                    validation_errors.append(f"{field_name}格式不符合要求")

    # 检查可选字段
    for optional_field in template.optional_fields or []:
        field_name = optional_field.get('name')
        if field_name not in evidence_data:
            validation_warnings.append(f"建议补充可选字段: {field_name}")

    return {
        'valid': len(validation_errors) == 0,
        'errors': validation_errors,
        'warnings': validation_warnings
    }


@router.post("/init-system-templates")
async def initialize_system_templates(db: Session = Depends(get_db)):
    """8. 初始化系统模板"""
    system_templates = [
        {
            'template_name': '银行对账单模板',
            'evidence_type': EvidenceType.BANK_STATEMENT,
            'required_fields': [
                {'name': '银行名称', 'type': 'string'},
                {'name': '账号', 'type': 'string'},
                {'name': '交易日期', 'type': 'date'},
                {'name': '交易金额', 'type': 'number'},
                {'name': '余额', 'type': 'number'}
            ],
            'optional_fields': [
                {'name': '对方账号', 'type': 'string'},
                {'name': '交易摘要', 'type': 'string'}
            ],
            'description': '标准银行对账单模板'
        },
        {
            'template_name': '发票模板',
            'evidence_type': EvidenceType.INVOICE,
            'required_fields': [
                {'name': '发票代码', 'type': 'string'},
                {'name': '发票号码', 'type': 'string'},
                {'name': '开票日期', 'type': 'date'},
                {'name': '金额', 'type': 'number'},
                {'name': '税额', 'type': 'number'}
            ],
            'optional_fields': [
                {'name': '购买方名称', 'type': 'string'},
                {'name': '销售方名称', 'type': 'string'},
                {'name': '商品名称', 'type': 'string'}
            ],
            'description': '标准增值税发票模板'
        }
    ]

    created_count = 0
    for tmpl_data in system_templates:
        # 检查是否已存在
        existing = db.query(EvidenceTemplate).filter(
            EvidenceTemplate.template_name == tmpl_data['template_name']
        ).first()

        if not existing:
            template = EvidenceTemplate(
                **tmpl_data,
                is_active=True,
                is_system=True,
                created_by='system'
            )
            db.add(template)
            created_count += 1

    db.commit()

    return {
        'message': f'初始化完成,创建了{created_count}个系统模板',
        'created_count': created_count
    }
