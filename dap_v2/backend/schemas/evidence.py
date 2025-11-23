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


# ============= Advanced Validators =============

class FileUploadValidator:
    """文件上传验证器"""

    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {
        'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic'},
        'document': {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.rtf'},
        'archive': {'.zip', '.rar', '.7z', '.tar', '.gz'}
    }

    # 最大文件大小 (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # MIME类型映射
    MIME_TYPES = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }

    @classmethod
    def validate_file_extension(cls, filename: str) -> bool:
        """验证文件扩展名"""
        if not filename or '.' not in filename:
            return False
        ext = '.' + filename.rsplit('.', 1)[-1].lower()
        all_allowed = set().union(*cls.ALLOWED_EXTENSIONS.values())
        return ext in all_allowed

    @classmethod
    def validate_file_size(cls, size: int) -> bool:
        """验证文件大小"""
        return 0 < size <= cls.MAX_FILE_SIZE

    @classmethod
    def get_file_type(cls, filename: str) -> str:
        """获取文件类型"""
        if not filename or '.' not in filename:
            return 'unknown'
        ext = '.' + filename.rsplit('.', 1)[-1].lower()
        for file_type, extensions in cls.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return file_type
        return 'unknown'

    @classmethod
    def get_mime_type(cls, filename: str) -> Optional[str]:
        """获取MIME类型"""
        if not filename or '.' not in filename:
            return None
        ext = '.' + filename.rsplit('.', 1)[-1].lower()
        return cls.MIME_TYPES.get(ext)

    @classmethod
    def validate_filename(cls, filename: str) -> bool:
        """验证文件名（排除危险字符）"""
        dangerous_chars = {'/', '\\', '..', '<', '>', ':', '"', '|', '?', '*'}
        return not any(char in filename for char in dangerous_chars)


class IDValidator:
    """ID验证器"""

    @staticmethod
    def validate_uuid(value: str) -> bool:
        """验证UUID格式"""
        import re
        if not value:
            return False
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(value))

    @staticmethod
    def validate_evidence_code(value: str) -> bool:
        """验证证据编号格式 (EV + 时间戳)"""
        import re
        if not value:
            return False
        return bool(re.match(r'^EV\d{14,}$', value))


class BusinessValidator:
    """业务逻辑验证器"""

    @staticmethod
    def validate_amount(value: Optional[Decimal]) -> bool:
        """验证金额"""
        if value is None:
            return True
        return Decimal('-999999999.99') <= value <= Decimal('999999999.99')

    @staticmethod
    def validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> bool:
        """验证日期范围"""
        if start_date and end_date:
            return start_date <= end_date
        return True

    @staticmethod
    def validate_confidence(value: Optional[float]) -> bool:
        """验证置信度"""
        if value is None:
            return True
        return 0.0 <= value <= 1.0

    @staticmethod
    def validate_confidentiality_level(value: str) -> bool:
        """验证保密等级"""
        allowed_levels = {'public', 'internal', 'confidential', 'secret', 'top_secret', 'normal'}
        return value.lower() in allowed_levels

    @staticmethod
    def validate_review_decision(value: str) -> bool:
        """验证审核决定"""
        allowed_decisions = {'approved', 'rejected', 'revised', 'pending'}
        return value.lower() in allowed_decisions


class TextValidator:
    """文本内容验证器"""

    @staticmethod
    def validate_no_sql_injection(text: str) -> bool:
        """防止SQL注入"""
        dangerous_patterns = [
            'drop table', 'delete from', 'insert into', 'update set',
            'exec(', 'execute(', 'script>', '--', '/*', '*/',
            'union select', 'or 1=1', 'or true'
        ]
        text_lower = text.lower()
        return not any(pattern in text_lower for pattern in dangerous_patterns)

    @staticmethod
    def validate_no_xss(text: str) -> bool:
        """防止XSS攻击"""
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=', 'onload=']
        text_lower = text.lower()
        return not any(pattern in text_lower for pattern in dangerous_patterns)

    @staticmethod
    def sanitize_text(text: str, max_length: int = 10000) -> str:
        """清理文本"""
        if not text:
            return ""
        # 移除控制字符
        import re
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        # 截断过长文本
        if len(text) > max_length:
            text = text[:max_length]
        return text.strip()


class PaginationValidator:
    """分页参数验证器"""

    MAX_PAGE_SIZE = 100
    DEFAULT_PAGE_SIZE = 20

    @classmethod
    def validate_pagination(cls, skip: int, limit: int) -> tuple:
        """验证并修正分页参数"""
        # 确保skip >= 0
        skip = max(0, skip)
        # 确保limit在合理范围内
        limit = max(1, min(limit, cls.MAX_PAGE_SIZE))
        return skip, limit

    @classmethod
    def calculate_pagination(cls, total: int, skip: int, limit: int) -> Dict[str, Any]:
        """计算分页信息"""
        skip, limit = cls.validate_pagination(skip, limit)
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        current_page = (skip // limit) + 1 if limit > 0 else 1

        return {
            'total': total,
            'skip': skip,
            'limit': limit,
            'current_page': current_page,
            'total_pages': total_pages,
            'has_next': skip + limit < total,
            'has_prev': skip > 0
        }


# ============= Enhanced Request Schemas with Validation =============

class EvidenceUploadEnhanced(EvidenceUpload):
    """增强的证据上传请求（带完整验证）"""

    @validator('title')
    def validate_title(cls, v):
        """验证标题"""
        if not v or not v.strip():
            raise ValueError("证据标题不能为空")
        if not TextValidator.validate_no_xss(v):
            raise ValueError("标题包含不允许的字符")
        if not TextValidator.validate_no_sql_injection(v):
            raise ValueError("标题包含危险字符")
        return TextValidator.sanitize_text(v, 255)

    @validator('description')
    def validate_description(cls, v):
        """验证描述"""
        if v:
            if not TextValidator.validate_no_xss(v):
                raise ValueError("描述包含不允许的字符")
            return TextValidator.sanitize_text(v, 2000)
        return v

    @validator('amount')
    def validate_amount(cls, v):
        """验证金额"""
        if v is not None:
            if not BusinessValidator.validate_amount(v):
                raise ValueError("金额超出允许范围")
        return v

    @validator('expiry_date')
    def validate_expiry_date(cls, v, values):
        """验证到期日期"""
        if v and 'issue_date' in values:
            issue_date = values['issue_date']
            if issue_date and v < issue_date:
                raise ValueError("到期日期不能早于签发日期")
        return v

    @validator('confidentiality_level')
    def validate_confidentiality(cls, v):
        """验证保密等级"""
        if not BusinessValidator.validate_confidentiality_level(v):
            raise ValueError("无效的保密等级")
        return v.lower()

    @validator('tags')
    def validate_tags(cls, v):
        """验证标签"""
        if v:
            if len(v) > 20:
                raise ValueError("标签数量不能超过20个")
            # 清理每个标签
            cleaned_tags = []
            for tag in v:
                if tag and tag.strip():
                    cleaned = TextValidator.sanitize_text(tag, 50)
                    if cleaned:
                        cleaned_tags.append(cleaned)
            return cleaned_tags[:20]  # 最多20个
        return []


class EvidenceQueryEnhanced(EvidenceQuery):
    """增强的查询参数（带验证）"""

    @validator('search')
    def validate_search(cls, v):
        """验证搜索关键词"""
        if v:
            if len(v) > 200:
                raise ValueError("搜索关键词过长")
            if not TextValidator.validate_no_sql_injection(v):
                raise ValueError("搜索关键词包含危险字符")
            return TextValidator.sanitize_text(v, 200)
        return v

    @validator('limit')
    def validate_limit(cls, v):
        """验证每页数量"""
        return min(v, PaginationValidator.MAX_PAGE_SIZE)

    @validator('skip')
    def validate_skip(cls, v):
        """验证跳过数量"""
        return max(0, v)
