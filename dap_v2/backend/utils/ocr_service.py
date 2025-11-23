"""
DAP v2.0 - OCR Service Module
调用本地PaddleOCR-VL进行文件OCR识别
支持证书、合同、发票等各类审计证据的智能提取
"""
import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# PaddleOCR-VL本地部署配置
PADDLEOCR_VL_PATH = os.getenv("PADDLEOCR_VL_PATH", "paddleocr")  # 本地PaddleOCR-VL命令路径
PADDLEOCR_MODEL_DIR = os.getenv("PADDLEOCR_MODEL_DIR", None)    # 模型目录


class OCRService:
    """OCR识别服务 - 调用本地PaddleOCR-VL"""

    def __init__(self):
        self.ocr_available = self._check_ocr_availability()

    def _check_ocr_availability(self) -> bool:
        """检查本地OCR服务是否可用"""
        try:
            result = subprocess.run(
                [PADDLEOCR_VL_PATH, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info(f"PaddleOCR-VL available: {result.returncode == 0}")
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"PaddleOCR-VL not available: {str(e)}")
            return False

    async def process_image(self, image_path: str) -> Dict:
        """
        处理图片文件进行OCR识别

        Args:
            image_path: 图片文件路径

        Returns:
            OCR识别结果字典
        """
        if not self.ocr_available:
            logger.warning("OCR service not available, returning empty result")
            return self._empty_ocr_result()

        try:
            # 构建OCR命令
            cmd = [
                PADDLEOCR_VL_PATH,
                "--image_dir", image_path,
                "--use_angle_cls", "true",
                "--use_gpu", "false",  # 根据环境调整
                "--lang", "ch"  # 中文识别
            ]

            if PADDLEOCR_MODEL_DIR:
                cmd.extend(["--det_model_dir", PADDLEOCR_MODEL_DIR])

            # 执行OCR
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8'
            )

            if result.returncode == 0:
                ocr_result = self._parse_paddleocr_output(result.stdout)
                logger.info(f"OCR completed for {image_path}")
                return ocr_result
            else:
                logger.error(f"OCR failed: {result.stderr}")
                return self._empty_ocr_result()

        except subprocess.TimeoutExpired:
            logger.error(f"OCR timeout for {image_path}")
            return self._empty_ocr_result()
        except Exception as e:
            logger.error(f"OCR error: {str(e)}")
            return self._empty_ocr_result()

    async def process_pdf(self, pdf_path: str) -> Dict:
        """
        处理PDF文件进行OCR识别

        Args:
            pdf_path: PDF文件路径

        Returns:
            OCR识别结果字典
        """
        # PDF需要先转图片再OCR
        try:
            # 使用pdf2image转换 (如果已安装)
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=5)  # 最多处理前5页

            all_results = []
            for i, image in enumerate(images, 1):
                # 保存临时图片
                temp_image = f"{pdf_path}_page_{i}.jpg"
                image.save(temp_image, 'JPEG')

                # OCR识别
                page_result = await self.process_image(temp_image)
                page_result['page_number'] = i
                all_results.append(page_result)

                # 删除临时文件
                Path(temp_image).unlink(missing_ok=True)

            return {
                'success': True,
                'pages': all_results,
                'total_pages': len(all_results),
                'extracted_text': '\n\n'.join([r.get('text', '') for r in all_results]),
                'confidence': sum([r.get('confidence', 0) for r in all_results]) / len(all_results) if all_results else 0
            }

        except ImportError:
            logger.warning("pdf2image not installed, skipping PDF OCR")
            return self._empty_ocr_result()
        except Exception as e:
            logger.error(f"PDF OCR error: {str(e)}")
            return self._empty_ocr_result()

    def _parse_paddleocr_output(self, output: str) -> Dict:
        """
        解析PaddleOCR输出结果

        Args:
            output: PaddleOCR标准输出

        Returns:
            结构化OCR结果
        """
        try:
            # PaddleOCR输出格式: [[坐标], (文本, 置信度)]
            lines = []
            total_confidence = 0
            count = 0

            # 简单解析 (实际需要根据PaddleOCR输出格式调整)
            for line in output.split('\n'):
                if line.strip():
                    lines.append(line.strip())
                    # 尝试提取置信度
                    match = re.search(r'(\d+\.\d+)', line)
                    if match:
                        confidence = float(match.group(1))
                        total_confidence += confidence
                        count += 1

            avg_confidence = (total_confidence / count * 100) if count > 0 else 0

            return {
                'success': True,
                'text': '\n'.join(lines),
                'lines': lines,
                'confidence': round(avg_confidence, 2),
                'line_count': len(lines),
                'processed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error parsing OCR output: {str(e)}")
            return self._empty_ocr_result()

    def extract_structured_data(self, ocr_result: Dict, evidence_type: str) -> Dict:
        """
        从OCR结果中提取结构化数据

        Args:
            ocr_result: OCR识别结果
            evidence_type: 证据类型 (property_certificate/contract/invoice等)

        Returns:
            结构化提取的数据
        """
        text = ocr_result.get('text', '')
        if not text:
            return {}

        # 根据证据类型进行智能提取
        extractors = {
            'property_certificate': self._extract_property_certificate,
            'contract': self._extract_contract,
            'invoice': self._extract_invoice,
            'certificate': self._extract_certificate,
            'bank_statement': self._extract_bank_statement,
        }

        extractor = extractors.get(evidence_type, self._extract_general)
        return extractor(text)

    def _extract_property_certificate(self, text: str) -> Dict:
        """提取产权证明信息"""
        result = {}

        # 证书编号
        cert_number = re.search(r'[证号|编号|字第][:：]?\s*([A-Z0-9\-（）()]+)', text)
        if cert_number:
            result['certificate_number'] = cert_number.group(1)

        # 权利人
        owner = re.search(r'[权利人|所有权人|产权人][:：]?\s*([^\n]+)', text)
        if owner:
            result['owner'] = owner.group(1).strip()

        # 坐落/地址
        location = re.search(r'[坐落|地址][:：]?\s*([^\n]+)', text)
        if location:
            result['location'] = location.group(1).strip()

        # 面积
        area = re.search(r'([建筑|土地|房屋])面积[:：]?\s*([\d.,]+)\s*平方米', text)
        if area:
            result['area'] = f"{area.group(2)}平方米"

        # 用途
        usage = re.search(r'[用途|规划用途][:：]?\s*([^\n]+)', text)
        if usage:
            result['usage'] = usage.group(1).strip()

        return result

    def _extract_contract(self, text: str) -> Dict:
        """提取合同信息"""
        result = {}

        # 合同编号
        contract_no = re.search(r'[合同编号|合同号][:：]?\s*([A-Z0-9\-（）()]+)', text)
        if contract_no:
            result['contract_number'] = contract_no.group(1)

        # 甲方
        party_a = re.search(r'甲方[:：]?\s*([^\n]+)', text)
        if party_a:
            result['party_a'] = party_a.group(1).strip()

        # 乙方
        party_b = re.search(r'乙方[:：]?\s*([^\n]+)', text)
        if party_b:
            result['party_b'] = party_b.group(1).strip()

        # 合同金额
        amount = re.search(r'[合同金额|总价|价款][:：]?\s*[￥¥]?\s*([\d,]+\.?\d*)\s*元', text)
        if amount:
            result['amount'] = amount.group(1).replace(',', '')

        # 签订日期
        date = re.search(r'签订日期[:：]?\s*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2})', text)
        if date:
            result['contract_date'] = date.group(1)

        return result

    def _extract_invoice(self, text: str) -> Dict:
        """提取发票信息"""
        result = {}

        # 发票代码
        code = re.search(r'发票代码[:：]?\s*(\d+)', text)
        if code:
            result['invoice_code'] = code.group(1)

        # 发票号码
        number = re.search(r'发票号码[:：]?\s*(\d+)', text)
        if number:
            result['invoice_number'] = number.group(1)

        # 金额
        amount = re.search(r'[金额|价税合计][:：]?\s*[￥¥]?\s*([\d,]+\.?\d*)', text)
        if amount:
            result['amount'] = amount.group(1).replace(',', '')

        # 开票日期
        date = re.search(r'开票日期[:：]?\s*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2})', text)
        if date:
            result['invoice_date'] = date.group(1)

        # 购买方
        buyer = re.search(r'购买方[:：]?\s*([^\n]+)', text)
        if buyer:
            result['buyer'] = buyer.group(1).strip()

        # 销售方
        seller = re.search(r'销售方[:：]?\s*([^\n]+)', text)
        if seller:
            result['seller'] = seller.group(1).strip()

        return result

    def _extract_certificate(self, text: str) -> Dict:
        """提取证书信息 (专利、商标等)"""
        result = {}

        # 证书编号
        cert_no = re.search(r'[证书编号|专利号|注册号][:：]?\s*([A-Z0-9\-（）()]+)', text)
        if cert_no:
            result['certificate_number'] = cert_no.group(1)

        # 权利人/持有人
        holder = re.search(r'[权利人|专利权人|商标注册人][:：]?\s*([^\n]+)', text)
        if holder:
            result['holder'] = holder.group(1).strip()

        # 有效期
        valid_until = re.search(r'有效期[至到][:：]?\s*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2})', text)
        if valid_until:
            result['valid_until'] = valid_until.group(1)

        return result

    def _extract_bank_statement(self, text: str) -> Dict:
        """提取银行对账单信息"""
        result = {}

        # 账号
        account = re.search(r'账号[:：]?\s*(\d+)', text)
        if account:
            result['account_number'] = account.group(1)

        # 户名
        account_name = re.search(r'户名[:：]?\s*([^\n]+)', text)
        if account_name:
            result['account_name'] = account_name.group(1).strip()

        # 提取所有金额 (收入/支出)
        amounts = re.findall(r'[收入|支出|余额][:：]?\s*[￥¥]?\s*([\d,]+\.?\d*)', text)
        if amounts:
            result['amounts'] = [a.replace(',', '') for a in amounts]

        return result

    def _extract_general(self, text: str) -> Dict:
        """通用信息提取"""
        result = {}

        # 提取所有日期
        dates = re.findall(r'\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}', text)
        if dates:
            result['dates'] = dates

        # 提取所有金额
        amounts = re.findall(r'[￥¥]\s*([\d,]+\.?\d*)\s*元', text)
        if amounts:
            result['amounts'] = [a.replace(',', '') for a in amounts]

        # 提取所有编号
        numbers = re.findall(r'编号[:：]?\s*([A-Z0-9\-（）()]+)', text)
        if numbers:
            result['numbers'] = numbers

        return result

    def _empty_ocr_result(self) -> Dict:
        """返回空OCR结果"""
        return {
            'success': False,
            'text': '',
            'lines': [],
            'confidence': 0,
            'line_count': 0,
            'processed_at': datetime.now().isoformat()
        }


# 全局OCR服务实例
ocr_service = OCRService()
