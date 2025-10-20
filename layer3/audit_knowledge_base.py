"""
审计知识库 - Layer 3
累积审计知识和模式

核心功能：
1. 审计专家知识图谱
2. 最佳实践模式库
3. 审计案例学习系统
4. 智能推荐引擎
5. 知识演化和更新
"""

import asyncio
import logging
import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, Counter
import pickle
import hashlib
import re
from enum import Enum

from utils.async_utils import schedule_async_task

# 图数据库支持（可选）
try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

# 向量数据库支持
try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# NLP支持
try:
    import jieba
    import jieba.analyse

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# 机器学习库
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import KMeans
    from sklearn.decomposition import LatentDirichletAllocation

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# 推荐系统
try:
    from surprise import SVD, Dataset, Reader
    from surprise.model_selection import train_test_split

    SURPRISE_AVAILABLE = True
except ImportError:
    SURPRISE_AVAILABLE = False


class KnowledgeType(Enum):
    """知识类型"""

    RULE = "rule"  # 审计规则
    PATTERN = "pattern"  # 审计模式
    CASE = "case"  # 审计案例
    BEST_PRACTICE = "best_practice"  # 最佳实践
    EXPERIENCE = "experience"  # 专家经验
    REGULATION = "regulation"  # 法规要求


class KnowledgeStatus(Enum):
    """知识状态"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    UNDER_REVIEW = "under_review"
    DRAFT = "draft"


@dataclass
class KnowledgeItem:
    """知识条目"""

    knowledge_id: str
    title: str
    knowledge_type: KnowledgeType
    content: str
    tags: List[str]
    category: str
    subcategory: str
    source: str
    expert_name: str
    confidence: float
    usage_count: int
    effectiveness_score: float
    created_at: datetime
    updated_at: datetime
    status: KnowledgeStatus
    metadata: Dict[str, Any]


@dataclass
class AuditCase:
    """审计案例"""

    case_id: str
    case_title: str
    industry: str
    company_size: str
    audit_type: str
    problem_description: str
    solution_approach: str
    lessons_learned: str
    effectiveness: float
    difficulty_level: int
    time_cost: float
    tools_used: List[str]
    created_by: str
    created_at: datetime


@dataclass
class ExpertProfile:
    """专家档案"""

    expert_id: str
    expert_name: str
    expertise_areas: List[str]
    experience_years: int
    knowledge_contributions: int
    accuracy_score: float
    reputation_score: float
    specializations: List[str]
    contact_info: Dict[str, str]


class AuditKnowledgeBase:
    """审计知识库"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 数据库配置
        self.kb_db_path = self.config.get("kb_db_path", "data/audit_knowledge_base.db")
        self.models_path = self.config.get("models_path", "data/models/knowledge/")

        # 知识图谱
        if NETWORKX_AVAILABLE:
            self.knowledge_graph = nx.DiGraph()
        else:
            self.knowledge_graph = None

        # 向量数据库
        if CHROMADB_AVAILABLE:
            try:
                self.chroma_client = chromadb.Client()
                self.knowledge_collection = self.chroma_client.get_or_create_collection(
                    "audit_knowledge"
                )
            except:
                self.chroma_client = None
                self.knowledge_collection = None
        else:
            self.chroma_client = None
            self.knowledge_collection = None

        # 缓存
        self.knowledge_cache = {}
        self.recommendation_cache = {}
        self.expert_cache = {}

        # 模型
        self.tfidf_vectorizer = None
        self.topic_model = None
        self.recommendation_model = None

        # 并发控制
        self.max_workers = self.config.get("max_workers", 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._lock = threading.RLock()

        # 推荐配置
        self.similarity_threshold = self.config.get("similarity_threshold", 0.7)
        self.max_recommendations = self.config.get("max_recommendations", 10)

        # 确保模型目录存在
        Path(self.models_path).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 加载知识库
        schedule_async_task(
            self._load_knowledge_base,
            logger=self.logger,
            task_name="load_knowledge_base",
        )
        schedule_async_task(
            self._load_models, logger=self.logger, task_name="load_knowledge_models"
        )

    def _init_database(self):
        """初始化知识库数据库"""
        try:
            Path(self.kb_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.kb_db_path) as conn:
                cursor = conn.cursor()

                # 知识条目表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_items (
                        knowledge_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        knowledge_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT,
                        category TEXT NOT NULL,
                        subcategory TEXT,
                        source TEXT,
                        expert_name TEXT,
                        confidence REAL DEFAULT 1.0,
                        usage_count INTEGER DEFAULT 0,
                        effectiveness_score REAL DEFAULT 0.0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        status TEXT DEFAULT 'active',
                        metadata TEXT
                    )
                """
                )

                # 审计案例表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_cases (
                        case_id TEXT PRIMARY KEY,
                        case_title TEXT NOT NULL,
                        industry TEXT,
                        company_size TEXT,
                        audit_type TEXT NOT NULL,
                        problem_description TEXT NOT NULL,
                        solution_approach TEXT NOT NULL,
                        lessons_learned TEXT,
                        effectiveness REAL DEFAULT 0.0,
                        difficulty_level INTEGER DEFAULT 1,
                        time_cost REAL DEFAULT 0.0,
                        tools_used TEXT,
                        created_by TEXT,
                        created_at TEXT NOT NULL
                    )
                """
                )

                # 专家档案表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS expert_profiles (
                        expert_id TEXT PRIMARY KEY,
                        expert_name TEXT NOT NULL,
                        expertise_areas TEXT,
                        experience_years INTEGER DEFAULT 0,
                        knowledge_contributions INTEGER DEFAULT 0,
                        accuracy_score REAL DEFAULT 0.0,
                        reputation_score REAL DEFAULT 0.0,
                        specializations TEXT,
                        contact_info TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 知识关系表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_relationships (
                        relationship_id TEXT PRIMARY KEY,
                        source_knowledge_id TEXT NOT NULL,
                        target_knowledge_id TEXT NOT NULL,
                        relationship_type TEXT NOT NULL,
                        strength REAL DEFAULT 1.0,
                        description TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (source_knowledge_id) REFERENCES knowledge_items (knowledge_id),
                        FOREIGN KEY (target_knowledge_id) REFERENCES knowledge_items (knowledge_id)
                    )
                """
                )

                # 使用反馈表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usage_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        knowledge_id TEXT NOT NULL,
                        user_id TEXT,
                        usage_context TEXT,
                        effectiveness_rating REAL,
                        feedback_comments TEXT,
                        feedback_time TEXT NOT NULL,
                        FOREIGN KEY (knowledge_id) REFERENCES knowledge_items (knowledge_id)
                    )
                """
                )

                # 推荐记录表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS recommendation_history (
                        recommendation_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        query_context TEXT NOT NULL,
                        recommended_items TEXT NOT NULL,
                        selected_item TEXT,
                        recommendation_time TEXT NOT NULL,
                        effectiveness REAL
                    )
                """
                )

                # 索引
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_items (knowledge_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_items (category)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_items (status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cases_industry ON audit_cases (industry)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cases_type ON audit_cases (audit_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_experts_name ON expert_profiles (expert_name)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_relationships_source ON knowledge_relationships (source_knowledge_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_feedback_knowledge ON usage_feedback (knowledge_id)"
                )

                conn.commit()

            self.logger.info("审计知识库数据库初始化完成")

        except Exception as e:
            self.logger.error(f"审计知识库数据库初始化失败: {e}")
            raise

    async def _load_knowledge_base(self):
        """加载知识库内容"""
        try:
            # 加载基础审计知识
            await self._load_basic_audit_knowledge()

            # 从数据库加载现有知识
            await self._load_existing_knowledge()

            # 构建知识图谱
            if self.knowledge_graph:
                await self._build_knowledge_graph()

            self.logger.info("知识库加载完成")

        except Exception as e:
            self.logger.error(f"加载知识库失败: {e}")

    async def _load_basic_audit_knowledge(self):
        """加载基础审计知识"""
        try:
            # 基础审计规则
            basic_rules = [
                {
                    "title": "资产负债表平衡原理",
                    "knowledge_type": "rule",
                    "content": "资产总额必须等于负债总额加所有者权益总额。这是会计恒等式的基本要求。",
                    "category": "基础会计",
                    "subcategory": "资产负债表",
                    "tags": ["资产", "负债", "所有者权益", "平衡"],
                },
                {
                    "title": "收入确认原则",
                    "knowledge_type": "rule",
                    "content": "收入应当在履行履约义务时确认，即在客户取得相关商品控制权时确认收入。",
                    "category": "收入审计",
                    "subcategory": "收入确认",
                    "tags": ["收入", "确认", "履约义务"],
                },
                {
                    "title": "成本配比原则",
                    "knowledge_type": "rule",
                    "content": "费用应当与其相关的收入进行配比，在确认收入的同时确认相关费用。",
                    "category": "成本审计",
                    "subcategory": "成本配比",
                    "tags": ["成本", "费用", "配比", "收入"],
                },
            ]

            # 审计模式
            audit_patterns = [
                {
                    "title": "现金流量异常模式",
                    "knowledge_type": "pattern",
                    "content": "经营活动现金流量与净利润长期背离，可能存在收入确认问题或盈余管理。",
                    "category": "现金流量审计",
                    "subcategory": "异常模式",
                    "tags": ["现金流量", "净利润", "异常", "盈余管理"],
                },
                {
                    "title": "关联交易识别模式",
                    "knowledge_type": "pattern",
                    "content": "通过交易对手分析、价格对比、交易条件异常等方式识别潜在关联交易。",
                    "category": "关联交易审计",
                    "subcategory": "识别技术",
                    "tags": ["关联交易", "识别", "价格", "条件"],
                },
            ]

            # 最佳实践
            best_practices = [
                {
                    "title": "分析性程序应用技巧",
                    "knowledge_type": "best_practice",
                    "content": "使用多种分析性程序结合，包括比率分析、趋势分析、回归分析等，提高审计效率。",
                    "category": "审计技术",
                    "subcategory": "分析性程序",
                    "tags": ["分析性程序", "比率分析", "趋势分析", "回归分析"],
                },
                {
                    "title": "信息化审计策略",
                    "knowledge_type": "best_practice",
                    "content": "利用数据分析工具进行全量测试，提高审计覆盖面和发现问题的能力。",
                    "category": "信息化审计",
                    "subcategory": "审计策略",
                    "tags": ["信息化", "数据分析", "全量测试"],
                },
            ]

            # 保存到数据库
            all_knowledge = basic_rules + audit_patterns + best_practices

            for knowledge_data in all_knowledge:
                await self._save_knowledge_item(
                    knowledge_data, source="system", expert_name="system"
                )

        except Exception as e:
            self.logger.error(f"加载基础审计知识失败: {e}")

    async def _load_existing_knowledge(self):
        """从数据库加载现有知识"""
        try:
            with sqlite3.connect(self.kb_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT knowledge_id, title, knowledge_type, content, tags, category,
                           subcategory, confidence, usage_count, effectiveness_score
                    FROM knowledge_items
                    WHERE status = 'active'
                """
                )

                knowledge_loaded = 0
                for row in cursor.fetchall():
                    knowledge_id = row[0]
                    tags = json.loads(row[4]) if row[4] else []

                    knowledge_item = KnowledgeItem(
                        knowledge_id=knowledge_id,
                        title=row[1],
                        knowledge_type=KnowledgeType(row[2]),
                        content=row[3],
                        tags=tags,
                        category=row[5],
                        subcategory=row[6] or "",
                        source="database",
                        expert_name="",
                        confidence=row[7],
                        usage_count=row[8],
                        effectiveness_score=row[9],
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        status=KnowledgeStatus.ACTIVE,
                        metadata={},
                    )

                    with self._lock:
                        self.knowledge_cache[knowledge_id] = knowledge_item

                    knowledge_loaded += 1

            self.logger.info(f"从数据库加载知识: {knowledge_loaded} 条")

        except Exception as e:
            self.logger.error(f"加载现有知识失败: {e}")

    async def _build_knowledge_graph(self):
        """构建知识图谱"""
        try:
            if not self.knowledge_graph:
                return

            # 添加知识节点
            for knowledge_id, knowledge_item in self.knowledge_cache.items():
                self.knowledge_graph.add_node(
                    knowledge_id,
                    title=knowledge_item.title,
                    type=knowledge_item.knowledge_type.value,
                    category=knowledge_item.category,
                    tags=knowledge_item.tags,
                    confidence=knowledge_item.confidence,
                )

            # 基于标签建立关系
            await self._create_tag_based_relationships()

            # 基于内容相似性建立关系
            await self._create_similarity_based_relationships()

            # 加载显式关系
            await self._load_explicit_relationships()

            self.logger.info(
                f"知识图谱构建完成: {self.knowledge_graph.number_of_nodes()} 节点, {self.knowledge_graph.number_of_edges()} 边"
            )

        except Exception as e:
            self.logger.error(f"构建知识图谱失败: {e}")

    async def _create_tag_based_relationships(self):
        """基于标签创建关系"""
        try:
            if not self.knowledge_graph:
                return

            nodes = list(self.knowledge_graph.nodes(data=True))

            for i, (node1_id, node1_data) in enumerate(nodes):
                for j, (node2_id, node2_data) in enumerate(nodes[i + 1 :], i + 1):
                    tags1 = set(node1_data.get("tags", []))
                    tags2 = set(node2_data.get("tags", []))

                    # 计算标签重叠
                    common_tags = tags1.intersection(tags2)
                    if len(common_tags) >= 2:  # 至少有2个共同标签
                        similarity = len(common_tags) / len(tags1.union(tags2))

                        if similarity > 0.3:  # 相似度阈值
                            self.knowledge_graph.add_edge(
                                node1_id,
                                node2_id,
                                relationship_type="tag_similarity",
                                strength=similarity,
                                common_tags=list(common_tags),
                            )

        except Exception as e:
            self.logger.error(f"创建标签关系失败: {e}")

    async def _create_similarity_based_relationships(self):
        """基于内容相似性创建关系"""
        try:
            if not SKLEARN_AVAILABLE or not self.knowledge_cache:
                return

            # 准备文本数据
            knowledge_ids = list(self.knowledge_cache.keys())
            knowledge_texts = []

            for knowledge_id in knowledge_ids:
                item = self.knowledge_cache[knowledge_id]
                text = f"{item.title} {item.content} {' '.join(item.tags)}"
                knowledge_texts.append(text)

            # TF-IDF向量化
            if not self.tfidf_vectorizer:
                self.tfidf_vectorizer = TfidfVectorizer(
                    max_features=1000, stop_words=None
                )

            tfidf_matrix = self.tfidf_vectorizer.fit_transform(knowledge_texts)

            # 计算相似性
            similarity_matrix = cosine_similarity(tfidf_matrix)

            # 建立相似性关系
            for i, knowledge_id1 in enumerate(knowledge_ids):
                for j, knowledge_id2 in enumerate(knowledge_ids[i + 1 :], i + 1):
                    similarity = similarity_matrix[i][j]

                    if similarity > self.similarity_threshold:
                        if self.knowledge_graph:
                            self.knowledge_graph.add_edge(
                                knowledge_id1,
                                knowledge_id2,
                                relationship_type="content_similarity",
                                strength=float(similarity),
                            )

        except Exception as e:
            self.logger.error(f"创建相似性关系失败: {e}")

    async def _load_explicit_relationships(self):
        """加载显式关系"""
        try:
            with sqlite3.connect(self.kb_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT source_knowledge_id, target_knowledge_id, relationship_type, strength
                    FROM knowledge_relationships
                """
                )

                for row in cursor.fetchall():
                    source_id, target_id, rel_type, strength = row

                    if (
                        self.knowledge_graph
                        and source_id in self.knowledge_graph
                        and target_id in self.knowledge_graph
                    ):
                        self.knowledge_graph.add_edge(
                            source_id,
                            target_id,
                            relationship_type=rel_type,
                            strength=strength,
                        )

        except Exception as e:
            self.logger.error(f"加载显式关系失败: {e}")

    async def _load_models(self):
        """加载模型"""
        try:
            # 加载主题模型
            if SKLEARN_AVAILABLE:
                topic_model_path = Path(self.models_path) / "topic_model.pkl"
                if topic_model_path.exists():
                    with open(topic_model_path, "rb") as f:
                        self.topic_model = pickle.load(f)
                    self.logger.info("主题模型加载成功")

            # 加载推荐模型
            if SURPRISE_AVAILABLE:
                rec_model_path = Path(self.models_path) / "recommendation_model.pkl"
                if rec_model_path.exists():
                    with open(rec_model_path, "rb") as f:
                        self.recommendation_model = pickle.load(f)
                    self.logger.info("推荐模型加载成功")

        except Exception as e:
            self.logger.error(f"加载模型失败: {e}")

    async def search_knowledge(
        self, query: str, search_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """搜索知识"""
        try:
            config = search_config or {}
            search_id = f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(query.encode()).hexdigest()[:8]}"

            result = {
                "search_id": search_id,
                "query": query,
                "started_at": datetime.now().isoformat(),
                "results": [],
                "total_found": 0,
                "search_methods": [],
                "suggestions": [],
                "status": "success",
            }

            # 多种搜索方法
            search_methods = [
                ("keyword_search", self._keyword_search),
                ("semantic_search", self._semantic_search),
                ("graph_search", self._graph_search),
                ("tag_search", self._tag_search),
            ]

            all_results = []

            for method_name, search_method in search_methods:
                try:
                    method_results = await search_method(query, config)
                    if method_results:
                        all_results.extend(method_results)
                        result["search_methods"].append(method_name)

                except Exception as e:
                    self.logger.error(f"搜索方法 {method_name} 失败: {e}")

            # 结果去重和排序
            unique_results = await self._deduplicate_and_rank_results(
                all_results, query
            )

            # 应用过滤器
            filtered_results = await self._apply_search_filters(unique_results, config)

            # 限制结果数量
            max_results = config.get("max_results", 20)
            final_results = filtered_results[:max_results]

            result["results"] = final_results
            result["total_found"] = len(final_results)
            result["completed_at"] = datetime.now().isoformat()

            # 生成搜索建议
            if len(final_results) < 5:
                result["suggestions"] = await self._generate_search_suggestions(query)

            self.logger.info(f"知识搜索完成: 查询='{query}', 找到={len(final_results)}条结果")

            return result

        except Exception as e:
            self.logger.error(f"知识搜索失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "query": query,
                "started_at": datetime.now().isoformat(),
            }

    async def _keyword_search(
        self, query: str, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """关键词搜索"""
        try:
            results = []

            # 提取查询关键词
            if JIEBA_AVAILABLE:
                keywords = jieba.lcut(query)
            else:
                keywords = query.split()

            # 在知识库中搜索
            for knowledge_id, knowledge_item in self.knowledge_cache.items():
                score = 0.0

                # 在标题中搜索
                title_matches = sum(
                    1
                    for keyword in keywords
                    if keyword.lower() in knowledge_item.title.lower()
                )
                score += title_matches * 3.0

                # 在内容中搜索
                content_matches = sum(
                    1
                    for keyword in keywords
                    if keyword.lower() in knowledge_item.content.lower()
                )
                score += content_matches * 2.0

                # 在标签中搜索
                tag_matches = sum(
                    1
                    for keyword in keywords
                    for tag in knowledge_item.tags
                    if keyword.lower() in tag.lower()
                )
                score += tag_matches * 1.5

                if score > 0:
                    results.append(
                        {
                            "knowledge_id": knowledge_id,
                            "knowledge_item": knowledge_item,
                            "relevance_score": score,
                            "search_method": "keyword",
                            "matched_keywords": [
                                kw
                                for kw in keywords
                                if any(
                                    kw.lower() in text.lower()
                                    for text in [
                                        knowledge_item.title,
                                        knowledge_item.content,
                                    ]
                                    + knowledge_item.tags
                                )
                            ],
                        }
                    )

            return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

        except Exception as e:
            self.logger.error(f"关键词搜索失败: {e}")
            return []

    async def _semantic_search(
        self, query: str, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """语义搜索"""
        try:
            if not self.tfidf_vectorizer or not SKLEARN_AVAILABLE:
                return []

            results = []

            # 向量化查询
            try:
                query_vector = self.tfidf_vectorizer.transform([query])
            except:
                return []

            # 准备知识文本
            knowledge_texts = []
            knowledge_ids = []

            for knowledge_id, knowledge_item in self.knowledge_cache.items():
                text = f"{knowledge_item.title} {knowledge_item.content} {' '.join(knowledge_item.tags)}"
                knowledge_texts.append(text)
                knowledge_ids.append(knowledge_id)

            if not knowledge_texts:
                return []

            # 计算语义相似性
            knowledge_vectors = self.tfidf_vectorizer.transform(knowledge_texts)
            similarities = cosine_similarity(query_vector, knowledge_vectors).flatten()

            # 生成结果
            for i, (knowledge_id, similarity) in enumerate(
                zip(knowledge_ids, similarities)
            ):
                if similarity > 0.1:  # 最小相似性阈值
                    results.append(
                        {
                            "knowledge_id": knowledge_id,
                            "knowledge_item": self.knowledge_cache[knowledge_id],
                            "relevance_score": float(similarity),
                            "search_method": "semantic",
                            "similarity_score": float(similarity),
                        }
                    )

            return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

        except Exception as e:
            self.logger.error(f"语义搜索失败: {e}")
            return []

    async def _graph_search(
        self, query: str, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """图搜索"""
        try:
            if not self.knowledge_graph:
                return []

            results = []

            # 先找到与查询最相关的节点
            initial_matches = await self._keyword_search(query, config)

            if not initial_matches:
                return []

            # 从最相关的节点开始图遍历
            start_nodes = [match["knowledge_id"] for match in initial_matches[:3]]

            visited_nodes = set()
            for start_node in start_nodes:
                if start_node not in self.knowledge_graph:
                    continue

                # 使用广度优先搜索
                queue = [(start_node, 1.0, 0)]  # (node, score, depth)
                max_depth = config.get("graph_search_depth", 2)

                while queue:
                    current_node, current_score, depth = queue.pop(0)

                    if current_node in visited_nodes or depth > max_depth:
                        continue

                    visited_nodes.add(current_node)

                    if current_node in self.knowledge_cache:
                        results.append(
                            {
                                "knowledge_id": current_node,
                                "knowledge_item": self.knowledge_cache[current_node],
                                "relevance_score": current_score * (0.8**depth),
                                "search_method": "graph",
                                "graph_depth": depth,
                            }
                        )

                    # 添加邻居节点
                    for neighbor in self.knowledge_graph.neighbors(current_node):
                        if neighbor not in visited_nodes:
                            edge_data = self.knowledge_graph.get_edge_data(
                                current_node, neighbor
                            )
                            edge_strength = edge_data.get("strength", 0.5)
                            new_score = current_score * edge_strength
                            queue.append((neighbor, new_score, depth + 1))

            return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

        except Exception as e:
            self.logger.error(f"图搜索失败: {e}")
            return []

    async def _tag_search(
        self, query: str, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """标签搜索"""
        try:
            results = []

            # 提取查询中的潜在标签
            if JIEBA_AVAILABLE:
                potential_tags = jieba.lcut(query)
            else:
                potential_tags = query.split()

            # 收集所有标签
            all_tags = set()
            for knowledge_item in self.knowledge_cache.values():
                all_tags.update(knowledge_item.tags)

            # 找到匹配的标签
            matched_tags = []
            for tag in all_tags:
                for potential_tag in potential_tags:
                    if (
                        potential_tag.lower() in tag.lower()
                        or tag.lower() in potential_tag.lower()
                    ):
                        matched_tags.append(tag)

            # 基于匹配标签搜索知识
            for knowledge_id, knowledge_item in self.knowledge_cache.items():
                tag_matches = [
                    tag for tag in knowledge_item.tags if tag in matched_tags
                ]

                if tag_matches:
                    results.append(
                        {
                            "knowledge_id": knowledge_id,
                            "knowledge_item": knowledge_item,
                            "relevance_score": len(tag_matches),
                            "search_method": "tag",
                            "matched_tags": tag_matches,
                        }
                    )

            return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

        except Exception as e:
            self.logger.error(f"标签搜索失败: {e}")
            return []

    async def recommend_knowledge(
        self, context: Dict[str, Any], recommendation_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """推荐知识"""
        try:
            config = recommendation_config or {}
            rec_id = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(context).encode()).hexdigest()[:8]}"

            result = {
                "recommendation_id": rec_id,
                "context": context,
                "started_at": datetime.now().isoformat(),
                "recommendations": [],
                "recommendation_methods": [],
                "total_recommendations": 0,
                "status": "success",
            }

            # 多种推荐策略
            recommendation_methods = [
                ("context_based", self._context_based_recommendation),
                (
                    "collaborative_filtering",
                    self._collaborative_filtering_recommendation,
                ),
                ("content_based", self._content_based_recommendation),
                ("graph_based", self._graph_based_recommendation),
            ]

            all_recommendations = []

            for method_name, rec_method in recommendation_methods:
                try:
                    method_recs = await rec_method(context, config)
                    if method_recs:
                        all_recommendations.extend(method_recs)
                        result["recommendation_methods"].append(method_name)

                except Exception as e:
                    self.logger.error(f"推荐方法 {method_name} 失败: {e}")

            # 合并和排序推荐
            final_recommendations = await self._merge_and_rank_recommendations(
                all_recommendations
            )

            # 限制推荐数量
            max_recs = config.get("max_recommendations", self.max_recommendations)
            result["recommendations"] = final_recommendations[:max_recs]
            result["total_recommendations"] = len(result["recommendations"])
            result["completed_at"] = datetime.now().isoformat()

            # 记录推荐历史
            await self._save_recommendation_history(
                rec_id, context, result["recommendations"]
            )

            self.logger.info(f"知识推荐完成: {len(result['recommendations'])} 条推荐")

            return result

        except Exception as e:
            self.logger.error(f"知识推荐失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "context": context,
                "started_at": datetime.now().isoformat(),
            }

    async def _context_based_recommendation(
        self, context: Dict[str, Any], config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """基于上下文的推荐"""
        try:
            recommendations = []

            # 从上下文提取关键信息
            audit_type = context.get("audit_type", "")
            industry = context.get("industry", "")
            problem_area = context.get("problem_area", "")
            difficulty_level = context.get("difficulty_level", 1)

            # 根据上下文过滤和评分知识
            for knowledge_id, knowledge_item in self.knowledge_cache.items():
                score = knowledge_item.effectiveness_score

                # 审计类型匹配
                if audit_type and audit_type.lower() in knowledge_item.content.lower():
                    score += 2.0

                # 行业匹配
                if industry and industry.lower() in knowledge_item.content.lower():
                    score += 1.5

                # 问题领域匹配
                if (
                    problem_area
                    and problem_area.lower() in knowledge_item.category.lower()
                ):
                    score += 2.5

                # 难度匹配（假设有难度信息）
                knowledge_difficulty = knowledge_item.metadata.get(
                    "difficulty_level", 1
                )
                if abs(knowledge_difficulty - difficulty_level) <= 1:
                    score += 1.0

                if score > 1.0:
                    recommendations.append(
                        {
                            "knowledge_id": knowledge_id,
                            "knowledge_item": knowledge_item,
                            "recommendation_score": score,
                            "recommendation_method": "context_based",
                            "context_matches": {
                                "audit_type": audit_type.lower()
                                in knowledge_item.content.lower()
                                if audit_type
                                else False,
                                "industry": industry.lower()
                                in knowledge_item.content.lower()
                                if industry
                                else False,
                                "problem_area": problem_area.lower()
                                in knowledge_item.category.lower()
                                if problem_area
                                else False,
                            },
                        }
                    )

            return sorted(
                recommendations, key=lambda x: x["recommendation_score"], reverse=True
            )

        except Exception as e:
            self.logger.error(f"基于上下文的推荐失败: {e}")
            return []

    async def add_knowledge(self, knowledge_data: Dict[str, Any]) -> Dict[str, Any]:
        """添加知识"""
        try:
            # 生成知识ID
            knowledge_id = (
                knowledge_data.get("knowledge_id")
                or f"kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(knowledge_data).encode()).hexdigest()[:8]}"
            )

            # 创建知识条目
            knowledge_item = KnowledgeItem(
                knowledge_id=knowledge_id,
                title=knowledge_data["title"],
                knowledge_type=KnowledgeType(
                    knowledge_data.get("knowledge_type", "experience")
                ),
                content=knowledge_data["content"],
                tags=knowledge_data.get("tags", []),
                category=knowledge_data.get("category", "其他"),
                subcategory=knowledge_data.get("subcategory", ""),
                source=knowledge_data.get("source", "user"),
                expert_name=knowledge_data.get("expert_name", ""),
                confidence=knowledge_data.get("confidence", 1.0),
                usage_count=0,
                effectiveness_score=0.0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status=KnowledgeStatus(knowledge_data.get("status", "active")),
                metadata=knowledge_data.get("metadata", {}),
            )

            # 保存到数据库
            await self._save_knowledge_item_to_db(knowledge_item)

            # 更新缓存
            with self._lock:
                self.knowledge_cache[knowledge_id] = knowledge_item

            # 更新知识图谱
            if self.knowledge_graph:
                await self._add_to_knowledge_graph(knowledge_item)

            # 向量化存储（如果支持）
            if self.knowledge_collection:
                await self._add_to_vector_db(knowledge_item)

            result = {
                "status": "success",
                "knowledge_id": knowledge_id,
                "message": f"知识 '{knowledge_item.title}' 添加成功",
            }

            self.logger.info(f"知识添加成功: {knowledge_id}")
            return result

        except Exception as e:
            self.logger.error(f"添加知识失败: {e}")
            return {"status": "error", "error": str(e)}

    async def _save_knowledge_item(
        self, knowledge_data: Dict[str, Any], source: str, expert_name: str
    ):
        """保存知识条目（内部方法）"""
        try:
            knowledge_id = f"kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(knowledge_data).encode()).hexdigest()[:8]}"

            knowledge_item = KnowledgeItem(
                knowledge_id=knowledge_id,
                title=knowledge_data["title"],
                knowledge_type=KnowledgeType(knowledge_data["knowledge_type"]),
                content=knowledge_data["content"],
                tags=knowledge_data.get("tags", []),
                category=knowledge_data["category"],
                subcategory=knowledge_data.get("subcategory", ""),
                source=source,
                expert_name=expert_name,
                confidence=1.0,
                usage_count=0,
                effectiveness_score=0.0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status=KnowledgeStatus.ACTIVE,
                metadata={},
            )

            await self._save_knowledge_item_to_db(knowledge_item)

            with self._lock:
                self.knowledge_cache[knowledge_id] = knowledge_item

        except Exception as e:
            self.logger.error(f"保存知识条目失败: {e}")

    async def _save_knowledge_item_to_db(self, knowledge_item: KnowledgeItem):
        """保存知识条目到数据库"""
        try:
            with sqlite3.connect(self.kb_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO knowledge_items
                    (knowledge_id, title, knowledge_type, content, tags, category,
                     subcategory, source, expert_name, confidence, usage_count,
                     effectiveness_score, created_at, updated_at, status, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        knowledge_item.knowledge_id,
                        knowledge_item.title,
                        knowledge_item.knowledge_type.value,
                        knowledge_item.content,
                        json.dumps(knowledge_item.tags),
                        knowledge_item.category,
                        knowledge_item.subcategory,
                        knowledge_item.source,
                        knowledge_item.expert_name,
                        knowledge_item.confidence,
                        knowledge_item.usage_count,
                        knowledge_item.effectiveness_score,
                        knowledge_item.created_at.isoformat(),
                        knowledge_item.updated_at.isoformat(),
                        knowledge_item.status.value,
                        json.dumps(knowledge_item.metadata),
                    ),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"保存知识条目到数据库失败: {e}")
            raise

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, "executor"):
                self.executor.shutdown(wait=True)

            # 保存模型
            await self._save_models()

            self.logger.info("审计知识库资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")

    async def _save_models(self):
        """保存模型"""
        try:
            if self.tfidf_vectorizer:
                tfidf_path = Path(self.models_path) / "tfidf_vectorizer.pkl"
                with open(tfidf_path, "wb") as f:
                    pickle.dump(self.tfidf_vectorizer, f)

            if self.topic_model:
                topic_path = Path(self.models_path) / "topic_model.pkl"
                with open(topic_path, "wb") as f:
                    pickle.dump(self.topic_model, f)

            self.logger.info("模型保存完成")

        except Exception as e:
            self.logger.error(f"保存模型失败: {e}")


async def main():
    """测试主函数"""
    config = {
        "kb_db_path": "data/test_audit_knowledge_base.db",
        "models_path": "data/test_models/knowledge/",
        "similarity_threshold": 0.7,
        "max_recommendations": 10,
    }

    async with AuditKnowledgeBase(config) as kb:
        # 测试搜索知识
        search_result = await kb.search_knowledge(
            query="收入确认审计", search_config={"max_results": 10}
        )
        print(f"搜索结果: {json.dumps(search_result, indent=2, ensure_ascii=False)}")

        # 测试推荐知识
        context = {
            "audit_type": "财务报表审计",
            "industry": "制造业",
            "problem_area": "收入确认",
            "difficulty_level": 2,
        }

        recommendation_result = await kb.recommend_knowledge(
            context=context, recommendation_config={"max_recommendations": 5}
        )
        print(
            f"推荐结果: {json.dumps(recommendation_result, indent=2, ensure_ascii=False)}"
        )

        # 测试添加知识
        new_knowledge = {
            "title": "存货计价审计要点",
            "knowledge_type": "best_practice",
            "content": "存货计价审计需要重点关注计价方法的一致性、跌价准备的充分性等方面。",
            "category": "存货审计",
            "tags": ["存货", "计价", "跌价准备"],
            "expert_name": "test_expert",
        }

        add_result = await kb.add_knowledge(new_knowledge)
        print(f"添加知识结果: {json.dumps(add_result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
