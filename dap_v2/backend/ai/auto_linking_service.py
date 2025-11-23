"""
DAP v2.0 - Evidence Auto-Linking Service
证据智能关联服务
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class EvidenceAutoLinkingService:
    """证据智能关联服务"""

    def __init__(self):
        self.similarity_threshold = 0.6  # 相似度阈值
        self.time_window_days = 7  # 时间窗口(天)
        self.amount_tolerance = 0.01  # 金额容差(1%)

    def find_related_evidences(
        self,
        evidence: Dict,
        all_evidences: List[Dict],
        max_results: int = 10
    ) -> List[Dict]:
        """
        查找相关证据

        Args:
            evidence: 当前证据
            all_evidences: 所有证据列表
            max_results: 最大返回数量

        Returns:
            关联证据列表,按相似度排序
        """
        related = []

        for other in all_evidences:
            if other['id'] == evidence['id']:
                continue

            # 计算关联分数
            score, reasons = self._calculate_relation_score(evidence, other)

            if score > 0:
                related.append({
                    'evidence_id': other['id'],
                    'evidence_name': other.get('evidence_name', ''),
                    'evidence_type': other.get('evidence_type', ''),
                    'relation_score': score,
                    'relation_reasons': reasons,
                    'suggested_type': self._suggest_relation_type(reasons)
                })

        # 按分数排序
        related.sort(key=lambda x: x['relation_score'], reverse=True)

        return related[:max_results]

    def _calculate_relation_score(
        self,
        evidence1: Dict,
        evidence2: Dict
    ) -> Tuple[float, List[str]]:
        """
        计算两个证据的关联分数

        Returns:
            (分数, 关联原因列表)
        """
        score = 0.0
        reasons = []

        # 1. 关键词相似度 (权重: 0.3)
        keyword_score = self._calculate_keyword_similarity(
            evidence1.get('content_text', ''),
            evidence2.get('content_text', '')
        )
        if keyword_score > self.similarity_threshold:
            score += keyword_score * 0.3
            reasons.append(f"关键词相似度: {keyword_score:.2f}")

        # 2. 金额匹配 (权重: 0.4)
        amount_match = self._check_amount_match(
            evidence1.get('amount'),
            evidence2.get('amount')
        )
        if amount_match:
            score += 0.4
            reasons.append(f"金额匹配: {evidence1.get('amount')}")

        # 3. 时间关联 (权重: 0.15)
        time_score = self._calculate_time_proximity(
            evidence1.get('created_at'),
            evidence2.get('created_at')
        )
        if time_score > 0:
            score += time_score * 0.15
            reasons.append(f"时间接近: {time_score:.2f}")

        # 4. 科目关联 (权重: 0.15)
        account_match = self._check_account_match(
            evidence1.get('related_accounts'),
            evidence2.get('related_accounts')
        )
        if account_match:
            score += 0.15
            reasons.append(f"科目关联: {account_match}")

        return score, reasons

    def _calculate_keyword_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """计算关键词相似度"""
        if not text1 or not text2:
            return 0.0

        try:
            # 提取关键词
            keywords1 = self._extract_keywords(text1)
            keywords2 = self._extract_keywords(text2)

            if not keywords1 or not keywords2:
                return 0.0

            # 计算Jaccard相似度
            intersection = len(keywords1 & keywords2)
            union = len(keywords1 | keywords2)

            return intersection / union if union > 0 else 0.0

        except Exception as e:
            logger.error(f"Keyword similarity calculation failed: {e}")
            return 0.0

    def _extract_keywords(self, text: str) -> set:
        """提取关键词"""
        # 简单实现: 提取中文词组和数字
        keywords = set()

        # 提取金额
        amounts = re.findall(r'\d+(?:\.\d+)?(?:元|万|亿)?', text)
        keywords.update(amounts)

        # 提取日期
        dates = re.findall(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?', text)
        keywords.update(dates)

        # 提取关键业务词
        business_keywords = [
            '银行', '发票', '合同', '付款', '收款', '采购', '销售',
            '费用', '资产', '负债', '利润', '现金', '存款', '借款'
        ]
        for kw in business_keywords:
            if kw in text:
                keywords.add(kw)

        # TODO: 使用jieba分词提取更多关键词

        return keywords

    def _check_amount_match(
        self,
        amount1: Optional[float],
        amount2: Optional[float]
    ) -> bool:
        """检查金额是否匹配"""
        if amount1 is None or amount2 is None:
            return False

        if amount1 == 0 or amount2 == 0:
            return False

        # 检查是否在容差范围内
        diff = abs(amount1 - amount2)
        tolerance = max(amount1, amount2) * self.amount_tolerance

        return diff <= tolerance

    def _calculate_time_proximity(
        self,
        time1: Optional[str],
        time2: Optional[str]
    ) -> float:
        """计算时间接近度"""
        if not time1 or not time2:
            return 0.0

        try:
            # 解析时间
            if isinstance(time1, str):
                time1 = datetime.fromisoformat(time1.replace('Z', '+00:00'))
            if isinstance(time2, str):
                time2 = datetime.fromisoformat(time2.replace('Z', '+00:00'))

            # 计算时间差(使用总秒数,更精确)
            diff_seconds = abs((time1 - time2).total_seconds())
            diff_days = diff_seconds / 86400.0  # 转换为天数(浮点数)

            if diff_days > self.time_window_days:
                return 0.0

            # 转换为0-1分数
            return 1.0 - (diff_days / self.time_window_days)

        except Exception as e:
            logger.error(f"Time proximity calculation failed: {e}")
            return 0.0

    def _check_account_match(
        self,
        accounts1: Optional[str],
        accounts2: Optional[str]
    ) -> Optional[str]:
        """检查科目是否匹配"""
        if not accounts1 or not accounts2:
            return None

        # 解析科目列表
        acc_list1 = set(accounts1.split(','))
        acc_list2 = set(accounts2.split(','))

        # 查找交集
        common = acc_list1 & acc_list2

        if common:
            return ', '.join(common)

        return None

    def _suggest_relation_type(self, reasons: List[str]) -> str:
        """建议关联类型"""
        if any('金额匹配' in r for r in reasons):
            return "金额关联"
        elif any('科目关联' in r for r in reasons):
            return "科目关联"
        elif any('关键词相似' in r for r in reasons):
            return "内容相关"
        elif any('时间接近' in r for r in reasons):
            return "时间相关"
        else:
            return "其他关联"

    def build_evidence_graph(
        self,
        evidence_id: str,
        all_relations: List[Dict],
        depth: int = 2
    ) -> Dict:
        """
        构建证据关系图谱

        Args:
            evidence_id: 起始证据ID
            all_relations: 所有关联关系
            depth: 递归深度

        Returns:
            {
                'nodes': [节点列表],
                'edges': [边列表],
                'center': 中心节点ID
            }
        """
        nodes = {}
        edges = []
        visited = set()

        def add_node(eid: str, level: int = 0):
            """添加节点"""
            if eid not in nodes:
                nodes[eid] = {
                    'id': eid,
                    'level': level,
                    'type': 'evidence'
                }

        def traverse(eid: str, current_depth: int = 0):
            """递归遍历"""
            if current_depth > depth or eid in visited:
                return

            visited.add(eid)
            add_node(eid, current_depth)

            # 查找相关证据
            for rel in all_relations:
                if rel['evidence_id'] == eid:
                    related_id = rel['related_evidence_id']
                    add_node(related_id, current_depth + 1)

                    edges.append({
                        'from': eid,
                        'to': related_id,
                        'type': rel.get('relation_type', 'related'),
                        'confidence': rel.get('confidence', 1.0)
                    })

                    traverse(related_id, current_depth + 1)

                elif rel['related_evidence_id'] == eid:
                    from_id = rel['evidence_id']
                    add_node(from_id, current_depth + 1)

                    edges.append({
                        'from': from_id,
                        'to': eid,
                        'type': rel.get('relation_type', 'related'),
                        'confidence': rel.get('confidence', 1.0)
                    })

                    traverse(from_id, current_depth + 1)

        # 开始遍历
        traverse(evidence_id)

        return {
            'nodes': list(nodes.values()),
            'edges': edges,
            'center': evidence_id,
            'node_count': len(nodes),
            'edge_count': len(edges)
        }


# 全局服务实例
_auto_linking_service = None


def get_auto_linking_service() -> EvidenceAutoLinkingService:
    """获取智能关联服务单例"""
    global _auto_linking_service
    if _auto_linking_service is None:
        _auto_linking_service = EvidenceAutoLinkingService()
    return _auto_linking_service
