"""
DeepSeek API Client
集成DeepSeek大模型的客户端
"""
import logging
import httpx
from typing import Dict, List, Optional, Any
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """DeepSeek API客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 30
    ):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL
        self.model = model or settings.DEEPSEEK_MODEL
        self.timeout = timeout or settings.LLM_TIMEOUT

        if not self.api_key:
            logger.warning("DeepSeek API key not configured")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """聊天补全"""
        if not self.api_key:
            raise ValueError("DeepSeek API key is required")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            **kwargs
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"DeepSeek API error: {e}")
            raise

    async def analyze_evidence(
        self,
        evidence_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """分析审计证据"""
        messages = [
            {
                "role": "system",
                "content": "你是专业的审计AI助手,擅长分析审计证据并提取关键信息。"
            },
            {
                "role": "user",
                "content": f"""请分析以下审计证据并提取关键信息:

证据内容:
{evidence_text}

{f"上下文信息: {context}" if context else ""}

请提取:
1. 证据类型
2. 关键字段和数值
3. 相关科目
4. 风险点
5. 建议分类

以JSON格式返回结果。"""
            }
        ]

        result = await self.chat_completion(messages, temperature=0.3)
        return result

    async def classify_evidence(
        self,
        evidence_text: str,
        categories: List[str]
    ) -> Dict[str, Any]:
        """分类审计证据"""
        messages = [
            {
                "role": "system",
                "content": "你是审计证据分类专家,能准确判断证据类型。"
            },
            {
                "role": "user",
                "content": f"""请将以下审计证据分类到合适的类别:

证据内容:
{evidence_text}

可选类别:
{', '.join(categories)}

返回最匹配的类别及置信度。"""
            }
        ]

        result = await self.chat_completion(messages, temperature=0.2)
        return result

    async def extract_fields(
        self,
        evidence_text: str,
        target_fields: List[str]
    ) -> Dict[str, Any]:
        """从证据中提取指定字段"""
        messages = [
            {
                "role": "system",
                "content": "你是信息提取专家,能从文本中准确提取结构化信息。"
            },
            {
                "role": "user",
                "content": f"""请从以下文本中提取指定字段:

文本内容:
{evidence_text}

需要提取的字段:
{', '.join(target_fields)}

以JSON格式返回提取结果,未找到的字段返回null。"""
            }
        ]

        result = await self.chat_completion(messages, temperature=0.1)
        return result

    async def predict_risk(
        self,
        project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """预测项目风险"""
        messages = [
            {
                "role": "system",
                "content": "你是审计风险评估专家,能准确评估项目风险。"
            },
            {
                "role": "user",
                "content": f"""请评估以下审计项目的风险:

项目数据:
{project_data}

请分析:
1. 固有风险等级
2. 控制风险等级
3. 检查风险等级
4. 综合风险评估
5. 重点关注领域
6. 建议审计程序

以结构化JSON格式返回。"""
            }
        ]

        result = await self.chat_completion(messages, temperature=0.4)
        return result

    async def suggest_mapping(
        self,
        source_accounts: List[str],
        target_template: str,
        historical_mappings: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """建议科目映射"""
        messages = [
            {
                "role": "system",
                "content": "你是会计科目映射专家,能准确匹配不同账套的科目。"
            },
            {
                "role": "user",
                "content": f"""请为以下源科目建议映射到目标模板:

源科目:
{', '.join(source_accounts)}

目标模板: {target_template}

{f"历史映射参考: {historical_mappings}" if historical_mappings else ""}

返回每个源科目的建议映射及置信度。"""
            }
        ]

        result = await self.chat_completion(messages, temperature=0.3)
        return result

    async def detect_anomaly(
        self,
        transaction_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """检测交易异常"""
        messages = [
            {
                "role": "system",
                "content": "你是审计异常检测专家,能识别可疑交易和模式。"
            },
            {
                "role": "user",
                "content": f"""请分析以下交易是否存在异常:

交易数据:
{transaction_data}

{f"上下文信息: {context}" if context else ""}

请判断:
1. 是否异常 (是/否)
2. 异常类型
3. 异常原因
4. 风险等级
5. 建议处理措施

以JSON格式返回。"""
            }
        ]

        result = await self.chat_completion(messages, temperature=0.2)
        return result
