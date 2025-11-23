"""
DAP v2.0 - Evidence Pydantic Schemas
Data validation models for audit evidence management
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal


# ============= Evidence Upload Schemas =============

class EvidenceUpload(BaseModel):
    """证据上传请求"""
    workpaper_id: Optional[str] = Field(None, description="关联审计底稿ID")
    project_id: str = Field(..., description="项目ID")
    account_code: Optional[str] = Field(None, description="科目代码")
    account_name: Optional[str] = Field(None, description="科目名称")

    evidence_category: str = Field(..., description="证据类别")
    evidence_type: str = Field(..., description="证据类型")
    business_type: Optional[str] = Field(None, description="业务类型")

    title: str = Field(..., min_length=1, max_length=255, description="证据标题")
    description: Optional[str] = Field(None, description="证据描述")

    # 可选的元数据
    certificate_number: Optional[str] = Field(None, description="证书/合同编号")
    issue_date: Optional[date] = Field(None, description="签发日期")
    expiry_date: Optional[date] = Field(None, description="到期日期")
    issuing_authority: Optional[str] = Field(None, description="签发机关")
    amount: Optional[Decimal] = Field(None, description="涉及金额")

    is_key_evidence: bool = Field(False, description="是否关键证据")
    is_original: bool = Field(True, description="是否原件")
    confidentiality_level: str = Field("normal", description="保密等级")

    tags: Optional[List[str]] = Field(default_factory=list, description="标签")

    enable_ocr: bool = Field(True, description="是否启用OCR")

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "uuid-here",
                "account_code": "1601",
                "evidence_category": "property_certificate",
                "evidence_type": "original",
                "business_type": "fixed_asset",
                "title": "某办公楼产权证明",
                "certificate_number": "京(2023)朝阳不动产权第0001号",
                "is_key_evidence": True,
                "tags": ["产权证明", "固定资产", "重要"]
            }
        }


# ============= Evidence Response Schemas =============

class EvidenceResponse(BaseModel):
    """证据信息响应"""
    id: str
    workpaper_id: Optional[str]
    project_id: str
    account_code: Optional[str]
    account_name: Optional[str]

    evidence_category: str
    evidence_type: str
    business_type: Optional[str]

    title: str
    description: Optional[str]

    # 文件信息
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    file_hash: Optional[str]
    mime_type: Optional[str]

    # 证书信息
    certificate_number: Optional[str]
    issue_date: Optional[date]
    expiry_date: Optional[date]
    issuing_authority: Optional[str]
    amount: Optional[Decimal]
    currency: Optional[str]

    # OCR信息
    ocr_processed: bool
    ocr_confidence: Optional[Decimal]
    extracted_data: Optional[Dict[str, Any]]

    # 审核状态
    review_status: str
    submitted_for_review: bool
    reviewed_by: Optional[str]
    review_date: Optional[datetime]
    review_comments: Optional[str]

    # 标记
    is_key_evidence: bool
    is_original: bool
    confidentiality_level: str

    tags: Optional[List[str]]

    # 时间戳
    uploaded_by: str
    upload_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvidenceListResponse(BaseModel):
    """证据列表项"""
    id: str
    title: str
    evidence_category: str
    evidence_type: str
    file_name: str
    file_size: int
    file_type: str
    review_status: str
    is_key_evidence: bool
    ocr_processed: bool
    upload_date: datetime

    class Config:
        from_attributes = True


class EvidenceDetailResponse(EvidenceResponse):
    """证据详细信息（包含批注和版本）"""
    annotations_count: Optional[int] = 0
    versions_count: Optional[int] = 0
    access_count: Optional[int] = 0


# ============= Evidence Update Schemas =============

class EvidenceUpdate(BaseModel):
    """更新证据信息"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None

    certificate_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    amount: Optional[Decimal] = None

    is_key_evidence: Optional[bool] = None
    is_original: Optional[bool] = None
    confidentiality_level: Optional[str] = None

    tags: Optional[List[str]] = None


# ============= Annotation Schemas =============

class AnnotationCreate(BaseModel):
    """创建批注"""
    page_number: Optional[int] = Field(None, description="页码(PDF)")
    position_x: Optional[Decimal] = Field(None, description="X坐标")
    position_y: Optional[Decimal] = Field(None, description="Y坐标")
    width: Optional[Decimal] = Field(None, description="宽度")
    height: Optional[Decimal] = Field(None, description="高度")

    annotation_type: str = Field(..., description="批注类型")
    content: str = Field(..., description="批注内容")
    color: str = Field("#FFFF00", description="颜色")

    mark_type: Optional[str] = Field(None, description="标记类型")
    severity: Optional[str] = Field(None, description="严重程度")


class AnnotationResponse(BaseModel):
    """批注响应"""
    id: str
    evidence_id: str
    page_number: Optional[int]
    position_x: Optional[Decimal]
    position_y: Optional[Decimal]
    width: Optional[Decimal]
    height: Optional[Decimal]
    annotation_type: str
    content: str
    color: str
    mark_type: Optional[str]
    severity: Optional[str]
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============= Review Schemas =============

class EvidenceReviewSubmit(BaseModel):
    """提交审核"""
    review_level: int = Field(..., ge=1, le=3, description="审核级别 1/2/3")
    comments: Optional[str] = Field(None, description="备注")


class EvidenceReviewDecision(BaseModel):
    """审核决定"""
    decision: str = Field(..., description="approved/rejected/revised")
    comments: str = Field(..., description="审核意见")

    completeness_score: Optional[int] = Field(None, ge=1, le=5, description="完整性评分")
    authenticity_score: Optional[int] = Field(None, ge=1, le=5, description="真实性评分")
    relevance_score: Optional[int] = Field(None, ge=1, le=5, description="相关性评分")


class ReviewHistoryResponse(BaseModel):
    """审核历史响应"""
    id: str
    evidence_id: str
    review_level: int
    reviewer_id: str
    review_status: str
    review_comments: Optional[str]
    completeness_score: Optional[int]
    authenticity_score: Optional[int]
    relevance_score: Optional[int]
    review_date: datetime

    class Config:
        from_attributes = True


# ============= Query Schemas =============

class EvidenceQuery(BaseModel):
    """证据查询参数"""
    project_id: Optional[str] = None
    workpaper_id: Optional[str] = None
    account_code: Optional[str] = None
    evidence_category: Optional[str] = None
    evidence_type: Optional[str] = None
    business_type: Optional[str] = None
    review_status: Optional[str] = None
    is_key_evidence: Optional[bool] = None
    search: Optional[str] = Field(None, description="搜索关键词")
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


# ============= Batch Operations =============

class BatchUploadResult(BaseModel):
    """批量上传结果"""
    total: int
    success: int
    failed: int
    results: List[Dict[str, Any]]


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    evidence_ids: List[str] = Field(..., min_length=1)


# ============= Statistics Schemas =============

class EvidenceStatistics(BaseModel):
    """证据统计"""
    total_evidences: int
    by_category: Dict[str, int]
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    key_evidences: int
    ocr_processed: int
    total_file_size: int  # bytes


# ============= Checklist Schemas =============

class ChecklistItemResponse(BaseModel):
    """检查清单项"""
    name: str
    type: str
    description: str
    required: bool
    uploaded: bool
    evidence_id: Optional[str]


class EvidenceChecklistResponse(BaseModel):
    """证据检查清单"""
    business_type: str
    account_code: Optional[str]
    checklist_name: str
    required_items: List[ChecklistItemResponse]
    optional_items: List[ChecklistItemResponse]
    completion_rate: float


# ============= OCR Result Schema =============

class OCRResult(BaseModel):
    """OCR识别结果"""
    success: bool
    text: str
    confidence: float
    line_count: int
    extracted_data: Optional[Dict[str, Any]]
    processed_at: str
