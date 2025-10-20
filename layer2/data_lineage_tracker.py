"""
数据血缘追踪器 - Layer 2
完整的数据血缘追踪和审计轨迹管理

核心功能：
1. 数据血缘关系建立和维护
2. 变更历史完整记录
3. 审计轨迹可视化
4. 合规性检查和报告
5. 智能影响分析
"""

import asyncio
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
import hashlib
import pickle
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading

# 图形数据库支持（可选）
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# 可视化支持（可选）
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

@dataclass
class LineageNode:
    """数据血缘节点"""
    node_id: str
    node_type: str  # source, transformation, target
    name: str
    schema: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    version: str

@dataclass
class LineageEdge:
    """数据血缘边关系"""
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str  # input, output, derived_from, transformed_to
    transformation_logic: str
    confidence: float
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class DataChange:
    """数据变更记录"""
    change_id: str
    node_id: str
    change_type: str  # insert, update, delete, schema_change
    old_value: Any
    new_value: Any
    change_reason: str
    changed_by: str
    changed_at: datetime
    impact_scope: List[str]

class DataLineageTracker:
    """数据血缘追踪器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 数据库配置
        self.db_path = self.config.get('lineage_db_path', 'data/lineage.db')
        self.cache_ttl = self.config.get('cache_ttl', 3600)

        # 并发控制
        self.max_workers = self.config.get('max_workers', 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # 内存缓存
        self._node_cache = {}
        self._edge_cache = {}
        self._change_cache = {}
        self._lock = threading.RLock()

        # 图形数据库（内存）
        if NETWORKX_AVAILABLE:
            self.lineage_graph = nx.DiGraph()
        else:
            self.lineage_graph = None

        # Redis缓存（可选）
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=self.config.get('redis_host', 'localhost'),
                    port=self.config.get('redis_port', 6379),
                    db=self.config.get('redis_db', 3),
                    decode_responses=True
                )
                self.redis_client.ping()
            except:
                self.redis_client = None
        else:
            self.redis_client = None

        # 初始化数据库
        self._init_database()

        # 加载现有数据到图形
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(self._load_existing_lineage())
        else:
            try:
                asyncio.run(self._load_existing_lineage())
            except RuntimeError:
                # asyncio.run 不能在已有事件循环中调用，降级为同步执行
                asyncio.get_event_loop().run_until_complete(self._load_existing_lineage())

    def _init_database(self):
        """初始化血缘数据库"""
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 节点表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS lineage_nodes (
                        node_id TEXT PRIMARY KEY,
                        node_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        schema TEXT,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        version TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')

                # 边关系表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS lineage_edges (
                        edge_id TEXT PRIMARY KEY,
                        source_node_id TEXT NOT NULL,
                        target_node_id TEXT NOT NULL,
                        relationship_type TEXT NOT NULL,
                        transformation_logic TEXT,
                        confidence REAL DEFAULT 1.0,
                        created_at TEXT NOT NULL,
                        metadata TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (source_node_id) REFERENCES lineage_nodes (node_id),
                        FOREIGN KEY (target_node_id) REFERENCES lineage_nodes (node_id)
                    )
                ''')

                # 变更记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS data_changes (
                        change_id TEXT PRIMARY KEY,
                        node_id TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        old_value TEXT,
                        new_value TEXT,
                        change_reason TEXT,
                        changed_by TEXT,
                        changed_at TEXT NOT NULL,
                        impact_scope TEXT,
                        FOREIGN KEY (node_id) REFERENCES lineage_nodes (node_id)
                    )
                ''')

                # 索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_type ON lineage_nodes (node_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_name ON lineage_nodes (name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_source ON lineage_edges (source_node_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_target ON lineage_edges (target_node_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_changes_node ON data_changes (node_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_changes_time ON data_changes (changed_at)')

                conn.commit()

            self.logger.info("血缘数据库初始化完成")

        except Exception as e:
            self.logger.error(f"血缘数据库初始化失败: {e}")
            raise

    async def _load_existing_lineage(self):
        """加载现有血缘关系到图形"""
        if not self.lineage_graph:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 加载节点
                cursor.execute('''
                    SELECT node_id, node_type, name, metadata
                    FROM lineage_nodes
                    WHERE is_active = 1
                ''')

                for row in cursor.fetchall():
                    node_id, node_type, name, metadata = row
                    try:
                        metadata_dict = json.loads(metadata) if metadata else {}
                    except:
                        metadata_dict = {}

                    self.lineage_graph.add_node(
                        node_id,
                        node_type=node_type,
                        name=name,
                        **metadata_dict
                    )

                # 加载边
                cursor.execute('''
                    SELECT source_node_id, target_node_id, relationship_type, confidence, metadata
                    FROM lineage_edges
                    WHERE is_active = 1
                ''')

                for row in cursor.fetchall():
                    source_id, target_id, rel_type, confidence, metadata = row
                    try:
                        metadata_dict = json.loads(metadata) if metadata else {}
                    except:
                        metadata_dict = {}

                    self.lineage_graph.add_edge(
                        source_id,
                        target_id,
                        relationship_type=rel_type,
                        confidence=confidence,
                        **metadata_dict
                    )

            self.logger.info(f"加载血缘关系: {self.lineage_graph.number_of_nodes()} 节点, {self.lineage_graph.number_of_edges()} 边")

        except Exception as e:
            self.logger.error(f"加载血缘关系失败: {e}")

    async def track_lineage(self, lineage_data: Dict[str, Any]) -> Dict[str, Any]:
        """追踪数据血缘关系"""
        try:
            result = {
                'lineage_id': f"lineage_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'tracked_at': datetime.now().isoformat(),
                'nodes_created': 0,
                'edges_created': 0,
                'changes_recorded': 0,
                'status': 'success'
            }

            # 创建节点
            if 'nodes' in lineage_data:
                for node_data in lineage_data['nodes']:
                    await self._create_or_update_node(node_data)
                    result['nodes_created'] += 1

            # 创建边关系
            if 'edges' in lineage_data:
                for edge_data in lineage_data['edges']:
                    await self._create_or_update_edge(edge_data)
                    result['edges_created'] += 1

            # 记录变更
            if 'changes' in lineage_data:
                for change_data in lineage_data['changes']:
                    await self._record_change(change_data)
                    result['changes_recorded'] += 1

            # 自动推理关系
            if self.config.get('auto_infer_relationships', True):
                await self._infer_relationships(lineage_data)

            # 验证血缘完整性
            validation_result = await self._validate_lineage()
            result['validation'] = validation_result

            self.logger.info(f"血缘追踪完成: {result}")
            return result

        except Exception as e:
            self.logger.error(f"血缘追踪失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'tracked_at': datetime.now().isoformat()
            }

    async def _create_or_update_node(self, node_data: Dict[str, Any]) -> str:
        """创建或更新血缘节点"""
        try:
            node_id = node_data.get('node_id') or self._generate_node_id(node_data)

            node = LineageNode(
                node_id=node_id,
                node_type=node_data.get('node_type', 'unknown'),
                name=node_data.get('name', ''),
                schema=node_data.get('schema', {}),
                metadata=node_data.get('metadata', {}),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                version=node_data.get('version', '1.0')
            )

            # 存储到数据库
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO lineage_nodes
                    (node_id, node_type, name, schema, metadata, created_at, updated_at, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    node.node_id,
                    node.node_type,
                    node.name,
                    json.dumps(node.schema),
                    json.dumps(node.metadata),
                    node.created_at.isoformat(),
                    node.updated_at.isoformat(),
                    node.version
                ))
                conn.commit()

            # 更新内存缓存
            with self._lock:
                self._node_cache[node_id] = node

            # 更新图形
            if self.lineage_graph:
                self.lineage_graph.add_node(
                    node_id,
                    node_type=node.node_type,
                    name=node.name,
                    **node.metadata
                )

            # 更新Redis缓存
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        f"lineage_node:{node_id}",
                        self.cache_ttl,
                        json.dumps(asdict(node), default=str)
                    )
                except:
                    pass

            return node_id

        except Exception as e:
            self.logger.error(f"创建节点失败: {e}")
            raise

    def _generate_node_id(self, node_data: Dict[str, Any]) -> str:
        """生成节点ID"""
        content = f"{node_data.get('name', '')}{node_data.get('node_type', '')}{datetime.now().isoformat()}"
        return f"node_{hashlib.md5(content.encode()).hexdigest()[:8]}"

    async def _create_or_update_edge(self, edge_data: Dict[str, Any]) -> str:
        """创建或更新血缘边关系"""
        try:
            edge_id = edge_data.get('edge_id') or self._generate_edge_id(edge_data)

            edge = LineageEdge(
                edge_id=edge_id,
                source_node_id=edge_data['source_node_id'],
                target_node_id=edge_data['target_node_id'],
                relationship_type=edge_data.get('relationship_type', 'derived_from'),
                transformation_logic=edge_data.get('transformation_logic', ''),
                confidence=edge_data.get('confidence', 1.0),
                created_at=datetime.now(),
                metadata=edge_data.get('metadata', {})
            )

            # 存储到数据库
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO lineage_edges
                    (edge_id, source_node_id, target_node_id, relationship_type,
                     transformation_logic, confidence, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    edge.edge_id,
                    edge.source_node_id,
                    edge.target_node_id,
                    edge.relationship_type,
                    edge.transformation_logic,
                    edge.confidence,
                    edge.created_at.isoformat(),
                    json.dumps(edge.metadata)
                ))
                conn.commit()

            # 更新内存缓存
            with self._lock:
                self._edge_cache[edge_id] = edge

            # 更新图形
            if self.lineage_graph:
                self.lineage_graph.add_edge(
                    edge.source_node_id,
                    edge.target_node_id,
                    edge_id=edge_id,
                    relationship_type=edge.relationship_type,
                    confidence=edge.confidence,
                    **edge.metadata
                )

            return edge_id

        except Exception as e:
            self.logger.error(f"创建边关系失败: {e}")
            raise

    def _generate_edge_id(self, edge_data: Dict[str, Any]) -> str:
        """生成边ID"""
        content = f"{edge_data['source_node_id']}{edge_data['target_node_id']}{edge_data.get('relationship_type', '')}"
        return f"edge_{hashlib.md5(content.encode()).hexdigest()[:8]}"

    async def _record_change(self, change_data: Dict[str, Any]) -> str:
        """记录数据变更"""
        try:
            change_id = change_data.get('change_id') or self._generate_change_id()

            change = DataChange(
                change_id=change_id,
                node_id=change_data['node_id'],
                change_type=change_data.get('change_type', 'update'),
                old_value=change_data.get('old_value'),
                new_value=change_data.get('new_value'),
                change_reason=change_data.get('change_reason', ''),
                changed_by=change_data.get('changed_by', 'system'),
                changed_at=datetime.now(),
                impact_scope=change_data.get('impact_scope', [])
            )

            # 存储到数据库
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO data_changes
                    (change_id, node_id, change_type, old_value, new_value,
                     change_reason, changed_by, changed_at, impact_scope)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    change.change_id,
                    change.node_id,
                    change.change_type,
                    json.dumps(change.old_value) if change.old_value else None,
                    json.dumps(change.new_value) if change.new_value else None,
                    change.change_reason,
                    change.changed_by,
                    change.changed_at.isoformat(),
                    json.dumps(change.impact_scope)
                ))
                conn.commit()

            # 更新内存缓存
            with self._lock:
                self._change_cache[change_id] = change

            # 分析影响范围
            if self.config.get('auto_analyze_impact', True):
                await self._analyze_change_impact(change)

            return change_id

        except Exception as e:
            self.logger.error(f"记录变更失败: {e}")
            raise

    def _generate_change_id(self) -> str:
        """生成变更ID"""
        return f"change_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

    async def _infer_relationships(self, lineage_data: Dict[str, Any]):
        """自动推理血缘关系"""
        try:
            if not self.lineage_graph:
                return

            # 基于名称相似性推理
            await self._infer_by_name_similarity()

            # 基于模式相似性推理
            await self._infer_by_schema_similarity()

            # 基于时间序列推理
            await self._infer_by_temporal_sequence()

        except Exception as e:
            self.logger.error(f"关系推理失败: {e}")

    async def _infer_by_name_similarity(self):
        """基于名称相似性推理关系"""
        try:
            nodes = list(self.lineage_graph.nodes(data=True))

            for i, (node1_id, node1_data) in enumerate(nodes):
                for j, (node2_id, node2_data) in enumerate(nodes[i+1:], i+1):
                    similarity = self._calculate_name_similarity(
                        node1_data.get('name', ''),
                        node2_data.get('name', '')
                    )

                    if similarity > self.config.get('name_similarity_threshold', 0.8):
                        # 创建推理的边关系
                        if not self.lineage_graph.has_edge(node1_id, node2_id):
                            edge_data = {
                                'source_node_id': node1_id,
                                'target_node_id': node2_id,
                                'relationship_type': 'inferred_similar',
                                'confidence': similarity,
                                'metadata': {
                                    'inference_method': 'name_similarity',
                                    'similarity_score': similarity
                                }
                            }
                            await self._create_or_update_edge(edge_data)

        except Exception as e:
            self.logger.error(f"名称相似性推理失败: {e}")

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """计算名称相似性"""
        if not name1 or not name2:
            return 0.0

        # 简单的编辑距离相似性
        name1 = name1.lower().strip()
        name2 = name2.lower().strip()

        if name1 == name2:
            return 1.0

        # 计算编辑距离
        m, n = len(name1), len(name2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if name1[i-1] == name2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

        max_len = max(m, n)
        if max_len == 0:
            return 1.0

        return 1.0 - dp[m][n] / max_len

    async def _infer_by_schema_similarity(self):
        """基于模式相似性推理关系"""
        # 模式相似性推理逻辑
        pass

    async def _infer_by_temporal_sequence(self):
        """基于时间序列推理关系"""
        # 时间序列推理逻辑
        pass

    async def _analyze_change_impact(self, change: DataChange):
        """分析变更影响范围"""
        try:
            if not self.lineage_graph:
                return

            # 获取下游节点
            downstream_nodes = self._get_downstream_nodes(change.node_id)

            # 计算影响程度
            impact_analysis = {
                'direct_impact': len(downstream_nodes),
                'indirect_impact': 0,
                'affected_nodes': downstream_nodes,
                'analysis_time': datetime.now().isoformat()
            }

            # 更新变更记录
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE data_changes
                    SET impact_scope = ?
                    WHERE change_id = ?
                ''', (json.dumps(impact_analysis), change.change_id))
                conn.commit()

        except Exception as e:
            self.logger.error(f"影响分析失败: {e}")

    def _get_downstream_nodes(self, node_id: str) -> List[str]:
        """获取下游节点"""
        if not self.lineage_graph or node_id not in self.lineage_graph:
            return []

        try:
            return list(nx.descendants(self.lineage_graph, node_id))
        except:
            return []

    async def _validate_lineage(self) -> Dict[str, Any]:
        """验证血缘完整性"""
        try:
            validation_result = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'statistics': {}
            }

            if not self.lineage_graph:
                validation_result['warnings'].append("图形数据库不可用，跳过图形验证")
                return validation_result

            # 检查孤立节点
            isolated_nodes = list(nx.isolates(self.lineage_graph))
            if isolated_nodes:
                validation_result['warnings'].append(f"发现 {len(isolated_nodes)} 个孤立节点")

            # 检查循环依赖
            if not nx.is_directed_acyclic_graph(self.lineage_graph):
                cycles = list(nx.simple_cycles(self.lineage_graph))
                validation_result['errors'].append(f"发现 {len(cycles)} 个循环依赖")
                validation_result['is_valid'] = False

            # 统计信息
            validation_result['statistics'] = {
                'total_nodes': self.lineage_graph.number_of_nodes(),
                'total_edges': self.lineage_graph.number_of_edges(),
                'isolated_nodes': len(isolated_nodes),
                'weakly_connected_components': nx.number_weakly_connected_components(self.lineage_graph)
            }

            return validation_result

        except Exception as e:
            self.logger.error(f"血缘验证失败: {e}")
            return {
                'is_valid': False,
                'errors': [str(e)],
                'warnings': [],
                'statistics': {}
            }

    async def query_lineage(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """查询血缘关系"""
        try:
            query_type = query.get('type', 'node')

            if query_type == 'node':
                return await self._query_node_lineage(query)
            elif query_type == 'path':
                return await self._query_lineage_path(query)
            elif query_type == 'impact':
                return await self._query_impact_analysis(query)
            elif query_type == 'changes':
                return await self._query_change_history(query)
            else:
                raise ValueError(f"不支持的查询类型: {query_type}")

        except Exception as e:
            self.logger.error(f"血缘查询失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'query_time': datetime.now().isoformat()
            }

    async def _query_node_lineage(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """查询节点血缘"""
        node_id = query['node_id']
        depth = query.get('depth', 3)
        direction = query.get('direction', 'both')  # upstream, downstream, both

        result = {
            'node_id': node_id,
            'lineage': {
                'upstream': [],
                'downstream': []
            },
            'query_time': datetime.now().isoformat()
        }

        if not self.lineage_graph or node_id not in self.lineage_graph:
            return result

        try:
            if direction in ['upstream', 'both']:
                # 上游血缘
                upstream_nodes = []
                current_level = [node_id]

                for d in range(depth):
                    next_level = []
                    for node in current_level:
                        predecessors = list(self.lineage_graph.predecessors(node))
                        upstream_nodes.extend(predecessors)
                        next_level.extend(predecessors)
                    current_level = list(set(next_level))

                result['lineage']['upstream'] = list(set(upstream_nodes))

            if direction in ['downstream', 'both']:
                # 下游血缘
                downstream_nodes = []
                current_level = [node_id]

                for d in range(depth):
                    next_level = []
                    for node in current_level:
                        successors = list(self.lineage_graph.successors(node))
                        downstream_nodes.extend(successors)
                        next_level.extend(successors)
                    current_level = list(set(next_level))

                result['lineage']['downstream'] = list(set(downstream_nodes))

            return result

        except Exception as e:
            self.logger.error(f"节点血缘查询失败: {e}")
            result['error'] = str(e)
            return result

    async def generate_lineage_report(self, report_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成血缘报告"""
        try:
            config = report_config or {}

            report = {
                'report_id': f"lineage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'generated_at': datetime.now().isoformat(),
                'summary': {},
                'detailed_analysis': {},
                'visualizations': {},
                'recommendations': []
            }

            # 汇总统计
            report['summary'] = await self._generate_summary_statistics()

            # 详细分析
            if config.get('include_detailed_analysis', True):
                report['detailed_analysis'] = await self._generate_detailed_analysis()

            # 可视化
            if config.get('include_visualizations', True) and PLOTLY_AVAILABLE:
                report['visualizations'] = await self._generate_visualizations()

            # 推荐建议
            if config.get('include_recommendations', True):
                report['recommendations'] = await self._generate_recommendations()

            return report

        except Exception as e:
            self.logger.error(f"生成血缘报告失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }

    async def _generate_summary_statistics(self) -> Dict[str, Any]:
        """生成汇总统计"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 节点统计
                cursor.execute('SELECT COUNT(*) FROM lineage_nodes WHERE is_active = 1')
                total_nodes = cursor.fetchone()[0]

                cursor.execute('SELECT node_type, COUNT(*) FROM lineage_nodes WHERE is_active = 1 GROUP BY node_type')
                node_types = dict(cursor.fetchall())

                # 边统计
                cursor.execute('SELECT COUNT(*) FROM lineage_edges WHERE is_active = 1')
                total_edges = cursor.fetchone()[0]

                cursor.execute('SELECT relationship_type, COUNT(*) FROM lineage_edges WHERE is_active = 1 GROUP BY relationship_type')
                edge_types = dict(cursor.fetchall())

                # 变更统计
                cursor.execute('SELECT COUNT(*) FROM data_changes')
                total_changes = cursor.fetchone()[0]

                cursor.execute('SELECT change_type, COUNT(*) FROM data_changes GROUP BY change_type')
                change_types = dict(cursor.fetchall())

                return {
                    'nodes': {
                        'total': total_nodes,
                        'by_type': node_types
                    },
                    'edges': {
                        'total': total_edges,
                        'by_type': edge_types
                    },
                    'changes': {
                        'total': total_changes,
                        'by_type': change_types
                    }
                }

        except Exception as e:
            self.logger.error(f"生成汇总统计失败: {e}")
            return {}

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)

            if self.redis_client:
                try:
                    self.redis_client.close()
                except:
                    pass

            self.logger.info("数据血缘追踪器资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")


async def main():
    """测试主函数"""
    config = {
        'lineage_db_path': 'data/test_lineage.db',
        'max_workers': 2,
        'auto_infer_relationships': True,
        'auto_analyze_impact': True
    }

    async with DataLineageTracker(config) as tracker:
        # 测试血缘追踪
        test_lineage = {
            'nodes': [
                {
                    'node_id': 'source_table_1',
                    'node_type': 'source',
                    'name': '原始财务数据表',
                    'schema': {'columns': ['账户', '金额', '日期']},
                    'metadata': {'system': '金蝶K3'}
                },
                {
                    'node_id': 'cleaned_table_1',
                    'node_type': 'transformation',
                    'name': '清洗后财务数据表',
                    'schema': {'columns': ['account_code', 'amount', 'date']},
                    'metadata': {'transformation': 'data_cleaning'}
                }
            ],
            'edges': [
                {
                    'source_node_id': 'source_table_1',
                    'target_node_id': 'cleaned_table_1',
                    'relationship_type': 'transformed_to',
                    'transformation_logic': 'clean_and_standardize',
                    'confidence': 1.0
                }
            ],
            'changes': [
                {
                    'node_id': 'source_table_1',
                    'change_type': 'update',
                    'new_value': {'rows_added': 100},
                    'change_reason': '新数据导入',
                    'changed_by': 'data_import_job'
                }
            ]
        }

        result = await tracker.track_lineage(test_lineage)
        print(f"血缘追踪结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

        # 查询血缘关系
        query_result = await tracker.query_lineage({
            'type': 'node',
            'node_id': 'source_table_1',
            'direction': 'downstream',
            'depth': 2
        })
        print(f"血缘查询结果: {json.dumps(query_result, indent=2, ensure_ascii=False)}")

        # 生成血缘报告
        report = await tracker.generate_lineage_report()
        print(f"血缘报告: {json.dumps(report, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
