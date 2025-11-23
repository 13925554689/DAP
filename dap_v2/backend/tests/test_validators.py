"""
DAP v2.0 - Validators Tests
测试输入验证器
"""
import pytest
from decimal import Decimal
from datetime import date

from backend.schemas.evidence import (
    FileUploadValidator,
    IDValidator,
    BusinessValidator,
    TextValidator,
    PaginationValidator,
    EvidenceUploadEnhanced,
    EvidenceQueryEnhanced
)


class TestFileUploadValidator:
    """文件上传验证器测试"""

    def test_validate_file_extension(self):
        """测试文件扩展名验证"""
        assert FileUploadValidator.validate_file_extension('document.pdf') is True
        assert FileUploadValidator.validate_file_extension('image.jpg') is True
        assert FileUploadValidator.validate_file_extension('archive.zip') is True
        assert FileUploadValidator.validate_file_extension('malware.exe') is False
        assert FileUploadValidator.validate_file_extension('script.sh') is False

    def test_validate_file_size(self):
        """测试文件大小验证"""
        assert FileUploadValidator.validate_file_size(1024) is True  # 1KB
        assert FileUploadValidator.validate_file_size(1024 * 1024 * 10) is True  # 10MB
        assert FileUploadValidator.validate_file_size(1024 * 1024 * 50) is True  # 50MB (边界)
        assert FileUploadValidator.validate_file_size(1024 * 1024 * 51) is False  # 51MB (超出)
        assert FileUploadValidator.validate_file_size(0) is False  # 0字节
        assert FileUploadValidator.validate_file_size(-100) is False  # 负数

    def test_get_file_type(self):
        """测试获取文件类型"""
        assert FileUploadValidator.get_file_type('doc.pdf') == 'document'
        assert FileUploadValidator.get_file_type('photo.jpg') == 'image'
        assert FileUploadValidator.get_file_type('files.zip') == 'archive'
        assert FileUploadValidator.get_file_type('unknown.xyz') == 'unknown'

    def test_get_mime_type(self):
        """测试获取MIME类型"""
        assert FileUploadValidator.get_mime_type('doc.pdf') == 'application/pdf'
        assert FileUploadValidator.get_mime_type('photo.jpg') == 'image/jpeg'
        assert FileUploadValidator.get_mime_type('image.png') == 'image/png'
        assert FileUploadValidator.get_mime_type('unknown.xyz') is None

    def test_validate_filename(self):
        """测试文件名安全验证"""
        assert FileUploadValidator.validate_filename('normal_file.pdf') is True
        assert FileUploadValidator.validate_filename('文件名.pdf') is True
        assert FileUploadValidator.validate_filename('../../../etc/passwd') is False
        assert FileUploadValidator.validate_filename('file<script>.pdf') is False
        assert FileUploadValidator.validate_filename('file|pipe.pdf') is False


class TestIDValidator:
    """ID验证器测试"""

    def test_validate_uuid(self):
        """测试UUID验证"""
        valid_uuid = '123e4567-e89b-12d3-a456-426614174000'
        assert IDValidator.validate_uuid(valid_uuid) is True
        assert IDValidator.validate_uuid('not-a-uuid') is False
        assert IDValidator.validate_uuid('12345') is False
        assert IDValidator.validate_uuid('') is False

    def test_validate_evidence_code(self):
        """测试证据编号验证"""
        assert IDValidator.validate_evidence_code('EV20251123120000') is True
        assert IDValidator.validate_evidence_code('EV202511231200001234') is True
        assert IDValidator.validate_evidence_code('INVALID') is False
        assert IDValidator.validate_evidence_code('EV123') is False  # 太短
        assert IDValidator.validate_evidence_code('') is False


class TestBusinessValidator:
    """业务逻辑验证器测试"""

    def test_validate_amount(self):
        """测试金额验证"""
        assert BusinessValidator.validate_amount(Decimal('100.00')) is True
        assert BusinessValidator.validate_amount(Decimal('999999999.99')) is True
        assert BusinessValidator.validate_amount(Decimal('-999999999.99')) is True
        assert BusinessValidator.validate_amount(Decimal('1000000000')) is False  # 超出范围
        assert BusinessValidator.validate_amount(None) is True  # 允许None

    def test_validate_date_range(self):
        """测试日期范围验证"""
        start = date(2025, 1, 1)
        end = date(2025, 12, 31)
        assert BusinessValidator.validate_date_range(start, end) is True
        assert BusinessValidator.validate_date_range(end, start) is False  # 倒序
        assert BusinessValidator.validate_date_range(None, end) is True
        assert BusinessValidator.validate_date_range(start, None) is True

    def test_validate_confidence(self):
        """测试置信度验证"""
        assert BusinessValidator.validate_confidence(0.0) is True
        assert BusinessValidator.validate_confidence(0.5) is True
        assert BusinessValidator.validate_confidence(1.0) is True
        assert BusinessValidator.validate_confidence(1.5) is False  # 超出范围
        assert BusinessValidator.validate_confidence(-0.1) is False  # 负数
        assert BusinessValidator.validate_confidence(None) is True

    def test_validate_confidentiality_level(self):
        """测试保密等级验证"""
        assert BusinessValidator.validate_confidentiality_level('normal') is True
        assert BusinessValidator.validate_confidentiality_level('confidential') is True
        assert BusinessValidator.validate_confidentiality_level('top_secret') is True
        assert BusinessValidator.validate_confidentiality_level('NORMAL') is True  # 大小写不敏感
        assert BusinessValidator.validate_confidentiality_level('invalid') is False

    def test_validate_review_decision(self):
        """测试审核决定验证"""
        assert BusinessValidator.validate_review_decision('approved') is True
        assert BusinessValidator.validate_review_decision('rejected') is True
        assert BusinessValidator.validate_review_decision('pending') is True
        assert BusinessValidator.validate_review_decision('APPROVED') is True  # 大小写不敏感
        assert BusinessValidator.validate_review_decision('invalid') is False


class TestTextValidator:
    """文本验证器测试"""

    def test_validate_no_sql_injection(self):
        """测试SQL注入防护"""
        assert TextValidator.validate_no_sql_injection('Normal text') is True
        assert TextValidator.validate_no_sql_injection('ORDER BY name') is True
        # 危险模式
        assert TextValidator.validate_no_sql_injection('DROP TABLE users') is False
        assert TextValidator.validate_no_sql_injection('DELETE FROM records') is False
        assert TextValidator.validate_no_sql_injection('SELECT * FROM users WHERE 1=1') is False
        assert TextValidator.validate_no_sql_injection("OR 'a'='a'") is False

    def test_validate_no_xss(self):
        """测试XSS攻击防护"""
        assert TextValidator.validate_no_xss('Normal text') is True
        assert TextValidator.validate_no_xss('Hello <b>World</b>') is True  # 普通HTML标签
        # 危险模式
        assert TextValidator.validate_no_xss('<script>alert(1)</script>') is False
        assert TextValidator.validate_no_xss('javascript:void(0)') is False
        assert TextValidator.validate_no_xss('<img onerror="alert(1)">') is False
        assert TextValidator.validate_no_xss('<div onclick="hack()">') is False

    def test_sanitize_text(self):
        """测试文本清理"""
        assert TextValidator.sanitize_text('  Normal text  ') == 'Normal text'
        assert TextValidator.sanitize_text('Line1\nLine2') == 'Line1\nLine2'  # 保留换行
        # 移除控制字符
        sanitized = TextValidator.sanitize_text('Text\x00\x01\x02')
        assert '\x00' not in sanitized
        # 截断过长文本
        long_text = 'a' * 20000
        sanitized = TextValidator.sanitize_text(long_text, max_length=100)
        assert len(sanitized) == 100


class TestPaginationValidator:
    """分页验证器测试"""

    def test_validate_pagination(self):
        """测试分页参数验证"""
        skip, limit = PaginationValidator.validate_pagination(0, 20)
        assert skip == 0
        assert limit == 20

        # 修正负数skip
        skip, limit = PaginationValidator.validate_pagination(-10, 20)
        assert skip == 0

        # 修正过大的limit
        skip, limit = PaginationValidator.validate_pagination(0, 200)
        assert limit == 100  # MAX_PAGE_SIZE

        # 修正过小的limit
        skip, limit = PaginationValidator.validate_pagination(0, 0)
        assert limit == 1

    def test_calculate_pagination(self):
        """测试分页信息计算"""
        result = PaginationValidator.calculate_pagination(total=100, skip=0, limit=20)
        assert result['total'] == 100
        assert result['skip'] == 0
        assert result['limit'] == 20
        assert result['current_page'] == 1
        assert result['total_pages'] == 5
        assert result['has_next'] is True
        assert result['has_prev'] is False

        # 测试最后一页
        result = PaginationValidator.calculate_pagination(total=100, skip=80, limit=20)
        assert result['current_page'] == 5
        assert result['has_next'] is False
        assert result['has_prev'] is True


class TestEnhancedSchemas:
    """增强的Schema测试"""

    def test_evidence_upload_enhanced_valid(self):
        """测试有效的证据上传数据"""
        data = {
            'project_id': 'proj-123',
            'evidence_category': 'property_certificate',
            'evidence_type': 'original',
            'title': 'Valid Title',
            'description': 'Valid description',
            'amount': 10000.50,
            'confidentiality_level': 'normal',
            'tags': ['tag1', 'tag2', 'tag3']
        }

        evidence = EvidenceUploadEnhanced(**data)
        assert evidence.title == 'Valid Title'
        assert evidence.confidentiality_level == 'normal'
        assert len(evidence.tags) == 3

    def test_evidence_upload_enhanced_xss_protection(self):
        """测试XSS防护"""
        with pytest.raises(ValueError, match="标题包含不允许的字符"):
            EvidenceUploadEnhanced(
                project_id='proj-123',
                evidence_category='invoice',
                evidence_type='original',
                title='<script>alert(1)</script>',
                confidentiality_level='normal'
            )

    def test_evidence_upload_enhanced_tag_limit(self):
        """测试标签数量限制"""
        tags = [f'tag{i}' for i in range(25)]  # 25个标签
        evidence = EvidenceUploadEnhanced(
            project_id='proj-123',
            evidence_category='invoice',
            evidence_type='original',
            title='Title',
            confidentiality_level='normal',
            tags=tags
        )
        # 应该被截断为20个
        assert len(evidence.tags) <= 20

    def test_evidence_query_enhanced_valid(self):
        """测试有效的查询参数"""
        query = EvidenceQueryEnhanced(
            project_id='proj-123',
            search='search term',
            skip=0,
            limit=20
        )
        assert query.search == 'search term'
        assert query.limit == 20

    def test_evidence_query_enhanced_limit_correction(self):
        """测试limit自动修正"""
        query = EvidenceQueryEnhanced(
            search='term',
            skip=0,
            limit=200  # 超出最大值
        )
        assert query.limit == 100  # 应该被修正为最大值

    def test_evidence_query_enhanced_skip_correction(self):
        """测试skip自动修正"""
        query = EvidenceQueryEnhanced(
            search='term',
            skip=-10,  # 负数
            limit=20
        )
        assert query.skip == 0  # 应该被修正为0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
