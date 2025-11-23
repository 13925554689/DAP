"""
DAP v2.0 - PaddleOCR Integration Module
PaddleOCR文字识别集成模块
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np
from PIL import Image
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

logger = logging.getLogger(__name__)


class PaddleOCRService:
    """PaddleOCR服务类"""

    def __init__(self):
        self.ocr = None
        self.enabled = settings.PADDLEOCR_ENABLED
        self.lang = settings.PADDLEOCR_LANG
        self.use_gpu = settings.PADDLEOCR_USE_GPU

        if self.enabled:
            self._init_paddleocr()

    def _init_paddleocr(self):
        """初始化PaddleOCR"""
        try:
            from paddleocr import PaddleOCR

            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False,
                det_model_dir=settings.PADDLEOCR_DET_MODEL_DIR,
                rec_model_dir=settings.PADDLEOCR_REC_MODEL_DIR
            )
            logger.info(f"PaddleOCR initialized successfully (lang={self.lang}, gpu={self.use_gpu})")
        except ImportError:
            logger.warning("PaddleOCR not installed. Run: pip install paddleocr")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            self.enabled = False

    def extract_text(
        self,
        image_path: str,
        return_boxes: bool = False,
        return_confidence: bool = True
    ) -> Dict[str, Any]:
        """
        从图像中提取文字

        Args:
            image_path: 图像文件路径
            return_boxes: 是否返回文字框坐标
            return_confidence: 是否返回置信度

        Returns:
            {
                'text': 完整文本,
                'lines': [行文本列表],
                'boxes': [文字框坐标] (可选),
                'confidence': 平均置信度,
                'line_confidences': [每行置信度] (可选),
                'details': [详细信息] (可选)
            }
        """
        if not self.enabled:
            return {
                'text': '',
                'lines': [],
                'confidence': 0.0,
                'error': 'PaddleOCR not enabled or not installed'
            }

        try:
            # 检查文件是否存在
            if not Path(image_path).exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")

            # OCR识别
            result = self.ocr.ocr(image_path, cls=True)

            if not result or not result[0]:
                return {
                    'text': '',
                    'lines': [],
                    'confidence': 0.0,
                    'error': 'No text detected'
                }

            # 解析结果
            lines = []
            boxes = []
            confidences = []
            details = []

            for line in result[0]:
                box = line[0]  # 文字框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text = line[1][0]  # 识别的文字
                confidence = line[1][1]  # 置信度

                lines.append(text)
                confidences.append(confidence)

                if return_boxes:
                    boxes.append(box)

                details.append({
                    'text': text,
                    'confidence': confidence,
                    'box': box
                })

            # 组合完整文本
            full_text = '\n'.join(lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            result_dict = {
                'text': full_text,
                'lines': lines,
                'confidence': avg_confidence,
                'line_count': len(lines)
            }

            if return_boxes:
                result_dict['boxes'] = boxes

            if return_confidence:
                result_dict['line_confidences'] = confidences

            result_dict['details'] = details

            logger.info(f"OCR extracted {len(lines)} lines with avg confidence {avg_confidence:.2f}")
            return result_dict

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                'text': '',
                'lines': [],
                'confidence': 0.0,
                'error': str(e)
            }

    def extract_from_multiple(
        self,
        image_paths: List[str]
    ) -> List[Dict[str, Any]]:
        """
        批量处理多个图像

        Args:
            image_paths: 图像文件路径列表

        Returns:
            提取结果列表
        """
        results = []
        for image_path in image_paths:
            result = self.extract_text(image_path)
            result['image_path'] = image_path
            results.append(result)

        return results

    def extract_table(
        self,
        image_path: str
    ) -> Dict[str, Any]:
        """
        从图像中提取表格数据

        Args:
            image_path: 图像文件路径

        Returns:
            {
                'rows': [[单元格数据]],
                'confidence': 平均置信度,
                'text': 纯文本形式
            }
        """
        if not self.enabled:
            return {
                'rows': [],
                'confidence': 0.0,
                'text': '',
                'error': 'PaddleOCR not enabled'
            }

        try:
            # 使用structure识别表格
            # TODO: 需要安装paddleocr的table模块
            # from paddleocr import PPStructure

            # 暂时使用普通OCR + 启发式规则
            ocr_result = self.extract_text(image_path, return_boxes=True, return_confidence=True)

            if 'error' in ocr_result:
                return ocr_result

            # TODO: 实现表格结构解析
            # 1. 根据box位置判断行列
            # 2. 组织成表格结构

            return {
                'rows': [],  # 待实现
                'confidence': ocr_result['confidence'],
                'text': ocr_result['text'],
                'note': 'Table extraction not fully implemented'
            }

        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return {
                'rows': [],
                'confidence': 0.0,
                'text': '',
                'error': str(e)
            }

    def preprocess_image(
        self,
        image_path: str,
        output_path: Optional[str] = None,
        enhance: bool = True,
        denoise: bool = True,
        binarize: bool = False
    ) -> str:
        """
        图像预处理以提高OCR准确率

        Args:
            image_path: 输入图像路径
            output_path: 输出图像路径
            enhance: 是否增强对比度
            denoise: 是否降噪
            binarize: 是否二值化

        Returns:
            处理后的图像路径
        """
        try:
            from PIL import Image, ImageEnhance, ImageFilter

            img = Image.open(image_path)

            # 增强对比度
            if enhance:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)

            # 降噪
            if denoise:
                img = img.filter(ImageFilter.MedianFilter(size=3))

            # 二值化
            if binarize:
                img = img.convert('L')  # 转灰度
                threshold = 128
                img = img.point(lambda x: 255 if x > threshold else 0, mode='1')

            # 保存
            if not output_path:
                output_path = str(Path(image_path).parent / f"{Path(image_path).stem}_processed{Path(image_path).suffix}")

            img.save(output_path)
            logger.info(f"Image preprocessed: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image_path  # 返回原图路径

    def get_field_by_keyword(
        self,
        ocr_result: Dict[str, Any],
        keyword: str,
        search_right: bool = True,
        max_distance: int = 100
    ) -> Optional[str]:
        """
        根据关键词查找字段值

        Args:
            ocr_result: OCR识别结果
            keyword: 关键词 (如 "金额:", "日期:")
            search_right: 在关键词右侧查找
            max_distance: 最大查找距离(像素)

        Returns:
            字段值或None
        """
        if 'details' not in ocr_result:
            return None

        try:
            # 查找关键词
            keyword_detail = None
            for detail in ocr_result['details']:
                if keyword in detail['text']:
                    keyword_detail = detail
                    break

            if not keyword_detail:
                return None

            # 获取关键词位置
            keyword_box = keyword_detail['box']
            keyword_x = (keyword_box[0][0] + keyword_box[1][0]) / 2
            keyword_y = (keyword_box[0][1] + keyword_box[2][1]) / 2

            # 查找最近的字段
            min_distance = float('inf')
            closest_value = None

            for detail in ocr_result['details']:
                if detail == keyword_detail:
                    continue

                box = detail['box']
                x = (box[0][0] + box[1][0]) / 2
                y = (box[0][1] + box[2][1]) / 2

                # 判断方向
                if search_right and x <= keyword_x:
                    continue
                if not search_right and x >= keyword_x:
                    continue

                # 计算距离
                distance = ((x - keyword_x) ** 2 + (y - keyword_y) ** 2) ** 0.5

                if distance < min_distance and distance < max_distance:
                    min_distance = distance
                    closest_value = detail['text']

            return closest_value

        except Exception as e:
            logger.error(f"Field extraction by keyword failed: {e}")
            return None


# 全局OCR服务实例
_ocr_service = None


def get_ocr_service() -> PaddleOCRService:
    """获取OCR服务单例"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = PaddleOCRService()
    return _ocr_service
