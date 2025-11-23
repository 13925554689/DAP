"""
DAP v2.0 - Evidence Export Service
证据导出服务 (PDF/Excel)
"""
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class EvidenceExportService:
    """证据导出服务"""

    def __init__(self, output_dir: str = "./exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_to_excel(
        self,
        evidences: List[Dict],
        filename: Optional[str] = None
    ) -> Dict[str, str]:
        """
        导出为Excel

        Args:
            evidences: 证据列表
            filename: 文件名

        Returns:
            {file_path, message}
        """
        try:
            import pandas as pd

            if not filename:
                filename = f"evidences_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

            output_path = self.output_dir / filename

            # 转换为DataFrame
            df = pd.DataFrame(evidences)

            # 导出
            df.to_excel(output_path, index=False, engine='openpyxl')

            logger.info(f"Exported {len(evidences)} evidences to {output_path}")

            return {
                'file_path': str(output_path),
                'message': f'成功导出{len(evidences)}条证据',
                'record_count': len(evidences)
            }

        except ImportError:
            return {
                'error': 'pandas或openpyxl未安装。请运行: pip install pandas openpyxl'
            }
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            return {
                'error': str(e)
            }

    def export_to_pdf(
        self,
        evidence: Dict,
        include_ocr: bool = True,
        filename: Optional[str] = None
    ) -> Dict[str, str]:
        """
        导出单个证据为PDF

        Args:
            evidence: 证据数据
            include_ocr: 是否包含OCR结果
            filename: 文件名

        Returns:
            {file_path, message}
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.utils import ImageReader

            if not filename:
                filename = f"evidence_{evidence.get('evidence_code')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            output_path = self.output_dir / filename

            # 创建PDF
            c = canvas.Canvas(str(output_path), pagesize=A4)
            width, height = A4

            # 添加中文字体支持 (需要字体文件)
            # pdfmetrics.registerFont(TTFont('SimSun', 'simsun.ttc'))
            # c.setFont('SimSun', 12)

            y = height - 50

            # 标题
            c.setFont('Helvetica-Bold', 16)
            c.drawString(50, y, f"Evidence: {evidence.get('evidence_name', '')}")
            y -= 30

            # 基本信息
            c.setFont('Helvetica', 12)
            c.drawString(50, y, f"Code: {evidence.get('evidence_code', '')}")
            y -= 20
            c.drawString(50, y, f"Type: {evidence.get('evidence_type', '')}")
            y -= 20
            c.drawString(50, y, f"Status: {evidence.get('status', '')}")
            y -= 30

            # OCR结果
            if include_ocr and evidence.get('ocr_text'):
                c.setFont('Helvetica-Bold', 12)
                c.drawString(50, y, "OCR Text:")
                y -= 20

                c.setFont('Helvetica', 10)
                # TODO: 处理中文和换行
                text = evidence.get('ocr_text', '')
                for line in text.split('\n')[:20]:  # 限制行数
                    if y < 50:
                        break
                    c.drawString(50, y, line[:80])  # 限制长度
                    y -= 15

            # 原始图像 (如果有)
            if evidence.get('file_path'):
                file_path = evidence.get('file_path')
                if Path(file_path).exists() and Path(file_path).suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    try:
                        # TODO: 添加图像到PDF
                        pass
                    except:
                        pass

            c.save()

            logger.info(f"Exported evidence to PDF: {output_path}")

            return {
                'file_path': str(output_path),
                'message': 'PDF导出成功'
            }

        except ImportError:
            return {
                'error': 'reportlab未安装。请运行: pip install reportlab'
            }
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return {
                'error': str(e)
            }

    def export_evidence_summary(
        self,
        evidences: List[Dict],
        project_info: Dict,
        filename: Optional[str] = None
    ) -> Dict[str, str]:
        """
        导出证据汇总报表

        Args:
            evidences: 证据列表
            project_info: 项目信息
            filename: 文件名

        Returns:
            导出结果
        """
        try:
            import pandas as pd

            if not filename:
                filename = f"evidence_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

            output_path = self.output_dir / filename

            # 创建多个sheet
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Sheet 1: 证据清单
                df_list = pd.DataFrame(evidences)
                df_list.to_excel(writer, sheet_name='证据清单', index=False)

                # Sheet 2: 统计汇总
                stats = {
                    '总证据数': [len(evidences)],
                    '已核验': [sum(1 for e in evidences if e.get('status') == 'VERIFIED')],
                    '待处理': [sum(1 for e in evidences if e.get('status') == 'PENDING')],
                    '关键证据': [sum(1 for e in evidences if e.get('is_key_evidence'))]
                }
                df_stats = pd.DataFrame(stats)
                df_stats.to_excel(writer, sheet_name='统计汇总', index=False)

                # Sheet 3: 按类型分组
                if evidences:
                    type_counts = {}
                    for e in evidences:
                        et = e.get('evidence_type', 'UNKNOWN')
                        type_counts[et] = type_counts.get(et, 0) + 1

                    df_types = pd.DataFrame(list(type_counts.items()), columns=['类型', '数量'])
                    df_types.to_excel(writer, sheet_name='类型分布', index=False)

            logger.info(f"Exported evidence summary: {output_path}")

            return {
                'file_path': str(output_path),
                'message': f'成功导出证据汇总报表 ({len(evidences)}条)',
                'record_count': len(evidences)
            }

        except Exception as e:
            logger.error(f"Summary export failed: {e}")
            return {
                'error': str(e)
            }


# 全局实例
_export_service = None


def get_export_service() -> EvidenceExportService:
    """获取导出服务单例"""
    global _export_service
    if _export_service is None:
        _export_service = EvidenceExportService()
    return _export_service
