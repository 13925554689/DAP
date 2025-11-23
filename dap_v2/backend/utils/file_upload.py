"""
DAP v2.0 - File Upload Utility
Handle file uploads for audit evidence with security and validation
"""
import os
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime
import logging
import shutil

from fastapi import UploadFile, HTTPException, status
from config import settings

logger = logging.getLogger(__name__)

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    # 文档
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    # 图片
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
    # 压缩文件
    '.zip', '.rar', '.7z',
    # 其他
    '.txt', '.csv', '.xml', '.json'
}

# 文件类型MIME映射
MIME_TYPE_MAPPING = {
    # 产权证明类
    'property_certificate': ['.pdf', '.jpg', '.jpeg', '.png'],
    # 合同协议类
    'contract': ['.pdf', '.doc', '.docx'],
    # 发票凭证类
    'invoice': ['.pdf', '.jpg', '.jpeg', '.png'],
    # 计算表类
    'calculation_sheet': ['.xlsx', '.xls', '.pdf'],
    # 照片类
    'photo': ['.jpg', '.jpeg', '.png'],
    # 证书类
    'certificate': ['.pdf', '.jpg', '.jpeg', '.png'],
}

# 最大文件大小 (50MB)
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class FileUploadService:
    """文件上传服务"""

    def __init__(self, upload_dir: str = None):
        """
        初始化文件上传服务

        Args:
            upload_dir: 上传文件存储目录
        """
        self.upload_dir = Path(upload_dir or settings.UPLOAD_DIR)
        self._ensure_upload_dir()

    def _ensure_upload_dir(self):
        """确保上传目录存在"""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directory: {self.upload_dir}")

    def validate_file(
        self,
        file: UploadFile,
        allowed_types: Optional[List[str]] = None,
        max_size: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        验证上传文件

        Args:
            file: 上传的文件
            allowed_types: 允许的文件类型列表
            max_size: 最大文件大小(字节)

        Returns:
            (是否通过, 错误信息)
        """
        # 检查文件名
        if not file.filename:
            return False, "文件名不能为空"

        # 检查文件扩展名
        file_ext = Path(file.filename).suffix.lower()
        allowed = allowed_types or ALLOWED_EXTENSIONS

        if file_ext not in allowed:
            return False, f"不支持的文件类型: {file_ext}。允许的类型: {', '.join(allowed)}"

        # 检查文件大小
        max_allowed = max_size or MAX_FILE_SIZE
        if file.size and file.size > max_allowed:
            size_mb = max_allowed / (1024 * 1024)
            return False, f"文件大小超过限制 ({size_mb}MB)"

        return True, "验证通过"

    def calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件SHA256哈希值

        Args:
            file_path: 文件路径

        Returns:
            SHA256哈希值
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def generate_unique_filename(self, original_filename: str) -> str:
        """
        生成唯一的文件名

        Args:
            original_filename: 原始文件名

        Returns:
            唯一文件名 (时间戳_随机数_原始名)
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_ext = Path(original_filename).suffix
        name_part = Path(original_filename).stem[:50]  # 限制长度

        # 生成随机字符串
        import secrets
        random_str = secrets.token_hex(8)

        return f"{timestamp}_{random_str}_{name_part}{file_ext}"

    def get_storage_path(
        self,
        project_id: str,
        evidence_category: str,
        filename: str
    ) -> Path:
        """
        获取文件存储路径

        组织结构: uploads/项目ID/证据类别/年月/文件名

        Args:
            project_id: 项目ID
            evidence_category: 证据类别
            filename: 文件名

        Returns:
            完整存储路径
        """
        year_month = datetime.now().strftime('%Y%m')
        storage_path = self.upload_dir / project_id / evidence_category / year_month
        storage_path.mkdir(parents=True, exist_ok=True)

        return storage_path / filename

    async def save_upload_file(
        self,
        file: UploadFile,
        project_id: str,
        evidence_category: str,
        allowed_types: Optional[List[str]] = None
    ) -> dict:
        """
        保存上传文件

        Args:
            file: 上传的文件
            project_id: 项目ID
            evidence_category: 证据类别
            allowed_types: 允许的文件类型

        Returns:
            文件信息字典
        """
        # 验证文件
        is_valid, error_msg = self.validate_file(file, allowed_types)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # 生成唯一文件名
        unique_filename = self.generate_unique_filename(file.filename)

        # 获取存储路径
        storage_path = self.get_storage_path(project_id, evidence_category, unique_filename)

        # 保存文件
        try:
            with open(storage_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 计算文件哈希
            file_hash = self.calculate_file_hash(storage_path)

            # 获取文件大小
            file_size = storage_path.stat().st_size

            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(str(storage_path))

            logger.info(f"File saved: {storage_path} ({file_size} bytes)")

            return {
                "filename": unique_filename,
                "original_filename": file.filename,
                "file_path": str(storage_path.relative_to(self.upload_dir)),
                "file_size": file_size,
                "file_type": Path(file.filename).suffix.lower(),
                "file_hash": file_hash,
                "mime_type": mime_type or "application/octet-stream",
                "storage_path": str(storage_path)
            }

        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            # 清理已创建的文件
            if storage_path.exists():
                storage_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文件保存失败: {str(e)}"
            )
        finally:
            file.file.close()

    def delete_file(self, file_path: str) -> bool:
        """
        删除文件

        Args:
            file_path: 相对文件路径

        Returns:
            是否删除成功
        """
        try:
            full_path = self.upload_dir / file_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"File deleted: {full_path}")
                return True
            else:
                logger.warning(f"File not found: {full_path}")
                return False
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False

    def get_file_path(self, relative_path: str) -> Path:
        """
        获取文件完整路径

        Args:
            relative_path: 相对路径

        Returns:
            完整路径
        """
        return self.upload_dir / relative_path

    def check_file_exists(self, file_hash: str) -> Optional[str]:
        """
        通过哈希值检查文件是否已存在(去重)

        Args:
            file_hash: 文件哈希值

        Returns:
            如果存在返回文件路径，否则返回None
        """
        # TODO: 实现文件哈希索引查询
        # 可以在数据库中查询是否有相同哈希的文件
        return None

    def get_file_info(self, file_path: str) -> dict:
        """
        获取文件信息

        Args:
            file_path: 文件路径

        Returns:
            文件信息字典
        """
        full_path = self.get_file_path(file_path)

        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )

        stat = full_path.stat()
        mime_type, _ = mimetypes.guess_type(str(full_path))

        return {
            "filename": full_path.name,
            "file_size": stat.st_size,
            "file_type": full_path.suffix.lower(),
            "mime_type": mime_type or "application/octet-stream",
            "created_time": datetime.fromtimestamp(stat.st_ctime),
            "modified_time": datetime.fromtimestamp(stat.st_mtime)
        }


# 全局文件上传服务实例
file_upload_service = FileUploadService()
