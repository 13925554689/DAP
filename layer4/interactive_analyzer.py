"""
交互式分析器 - Layer 4
拖拽式交互分析界面

核心功能：
1. 拖拽式数据分析界面
2. 实时数据可视化
3. 动态筛选和钻取
4. 自定义仪表板
5. 交互式图表生成
"""

import asyncio
import logging
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, Counter
import pickle
import hashlib
import uuid
from enum import Enum

# 可视化库
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.io as pio

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import seaborn as sns

    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# 数据处理
try:
    from scipy import stats
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans

    SCIPY_SKLEARN_AVAILABLE = True
except ImportError:
    SCIPY_SKLEARN_AVAILABLE = False

# Web框架（可选）
try:
    from flask import Flask, request, jsonify, render_template_string, send_file
    from flask_cors import CORS

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


class AnalysisType(Enum):
    """分析类型"""

    DESCRIPTIVE = "descriptive"  # 描述性分析
    TREND = "trend"  # 趋势分析
    COMPARISON = "comparison"  # 对比分析
    CORRELATION = "correlation"  # 相关性分析
    DISTRIBUTION = "distribution"  # 分布分析
    CLUSTERING = "clustering"  # 聚类分析
    OUTLIER = "outlier"  # 异常值分析


class ChartType(Enum):
    """图表类型"""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOX = "box"
    HEATMAP = "heatmap"
    SUNBURST = "sunburst"
    TREEMAP = "treemap"
    GAUGE = "gauge"


class FilterType(Enum):
    """筛选器类型"""

    RANGE = "range"  # 范围筛选
    CATEGORICAL = "categorical"  # 分类筛选
    DATE_RANGE = "date_range"  # 日期范围
    TEXT_SEARCH = "text_search"  # 文本搜索
    MULTI_SELECT = "multi_select"  # 多选


@dataclass
class AnalysisWidget:
    """分析组件"""

    widget_id: str
    widget_type: str
    title: str
    data_source: str
    configuration: Dict[str, Any]
    position: Dict[str, Any]  # x, y, width, height
    created_at: datetime
    updated_at: datetime


@dataclass
class Dashboard:
    """仪表板"""

    dashboard_id: str
    dashboard_name: str
    description: str
    widgets: List[AnalysisWidget]
    layout: Dict[str, Any]
    filters: List[Dict[str, Any]]
    created_by: str
    created_at: datetime
    updated_at: datetime
    is_public: bool


@dataclass
class AnalysisSession:
    """分析会话"""

    session_id: str
    user_id: str
    dashboard_id: Optional[str]
    data_context: Dict[str, Any]
    interaction_history: List[Dict[str, Any]]
    created_at: datetime
    last_activity: datetime


class InteractiveAnalyzer:
    """交互式分析器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 数据库配置
        self.analyzer_db_path = self.config.get(
            "analyzer_db_path", "data/interactive_analyzer.db"
        )
        self.dashboard_cache_path = self.config.get(
            "dashboard_cache_path", "data/dashboards/"
        )

        # 会话管理
        self.active_sessions = {}
        self.dashboard_cache = {}
        self.widget_cache = {}

        # 数据缓存
        self.data_cache = {}
        self.chart_cache = {}

        # Web服务配置
        self.web_enabled = self.config.get("web_enabled", True)
        self.web_host = self.config.get("web_host", "127.0.0.1")
        self.web_port = self.config.get("web_port", 8080)

        # 并发控制
        self.max_workers = self.config.get("max_workers", 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._lock = threading.RLock()

        # 确保目录存在
        Path(self.dashboard_cache_path).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 初始化Web服务
        if self.web_enabled and FLASK_AVAILABLE:
            self._init_web_service()

        # 加载仪表板
        asyncio.create_task(self._load_dashboards())

    def _init_database(self):
        """初始化分析器数据库"""
        try:
            Path(self.analyzer_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.analyzer_db_path) as conn:
                cursor = conn.cursor()

                # 仪表板表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dashboards (
                        dashboard_id TEXT PRIMARY KEY,
                        dashboard_name TEXT NOT NULL,
                        description TEXT,
                        layout TEXT,
                        filters TEXT,
                        created_by TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        is_public BOOLEAN DEFAULT 0
                    )
                """
                )

                # 分析组件表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_widgets (
                        widget_id TEXT PRIMARY KEY,
                        dashboard_id TEXT,
                        widget_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        data_source TEXT,
                        configuration TEXT,
                        position TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (dashboard_id) REFERENCES dashboards (dashboard_id)
                    )
                """
                )

                # 分析会话表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        dashboard_id TEXT,
                        data_context TEXT,
                        interaction_history TEXT,
                        created_at TEXT NOT NULL,
                        last_activity TEXT NOT NULL,
                        FOREIGN KEY (dashboard_id) REFERENCES dashboards (dashboard_id)
                    )
                """
                )

                # 用户偏好表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        user_id TEXT PRIMARY KEY,
                        default_dashboard_id TEXT,
                        chart_preferences TEXT,
                        color_scheme TEXT,
                        layout_preferences TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 数据源配置表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS data_sources (
                        source_id TEXT PRIMARY KEY,
                        source_name TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        connection_config TEXT,
                        schema_info TEXT,
                        refresh_frequency INTEGER DEFAULT 3600,
                        last_refresh TEXT,
                        is_active BOOLEAN DEFAULT 1
                    )
                """
                )

                # 索引
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_dashboards_user ON dashboards (created_by)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_widgets_dashboard ON analysis_widgets (dashboard_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON analysis_sessions (user_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_activity ON analysis_sessions (last_activity)"
                )

                conn.commit()

            self.logger.info("交互式分析器数据库初始化完成")

        except Exception as e:
            self.logger.error(f"交互式分析器数据库初始化失败: {e}")
            raise

    def _init_web_service(self):
        """初始化Web服务"""
        try:
            self.app = Flask(__name__)
            CORS(self.app)

            # 注册路由
            self._register_routes()

            self.logger.info("Web服务初始化完成")

        except Exception as e:
            self.logger.error(f"Web服务初始化失败: {e}")

    def _register_routes(self):
        """注册Web路由"""
        try:

            @self.app.route("/")
            def index():
                return self._render_main_interface()

            @self.app.route("/api/dashboards", methods=["GET"])
            def get_dashboards():
                user_id = request.args.get("user_id", "default")
                dashboards = self._get_user_dashboards(user_id)
                return jsonify(dashboards)

            @self.app.route("/api/dashboards", methods=["POST"])
            def create_dashboard():
                data = request.json
                result = asyncio.run(self.create_dashboard(data))
                return jsonify(result)

            @self.app.route("/api/dashboards/<dashboard_id>", methods=["GET"])
            def get_dashboard(dashboard_id):
                dashboard = self._get_dashboard_by_id(dashboard_id)
                return jsonify(dashboard)

            @self.app.route("/api/analysis/execute", methods=["POST"])
            def execute_analysis():
                data = request.json
                result = asyncio.run(self.execute_analysis(data))
                return jsonify(result)

            @self.app.route("/api/charts/generate", methods=["POST"])
            def generate_chart():
                data = request.json
                result = asyncio.run(self.generate_chart(data))
                return jsonify(result)

            @self.app.route("/api/data/filter", methods=["POST"])
            def filter_data():
                data = request.json
                result = asyncio.run(self.filter_data(data))
                return jsonify(result)

            @self.app.route("/api/widgets", methods=["POST"])
            def create_widget():
                data = request.json
                result = asyncio.run(self.create_widget(data))
                return jsonify(result)

        except Exception as e:
            self.logger.error(f"注册Web路由失败: {e}")

    def _render_main_interface(self):
        """渲染主界面"""
        html_template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>DAP 交互式分析器</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <style>
                body {
                    font-family: 'Microsoft YaHei', sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f5f5f5;
                }
                .header {
                    background-color: #2c3e50;
                    color: white;
                    padding: 15px 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .sidebar {
                    width: 250px;
                    background-color: white;
                    height: calc(100vh - 60px);
                    float: left;
                    box-shadow: 2px 0 5px rgba(0,0,0,0.1);
                    overflow-y: auto;
                }
                .main-content {
                    margin-left: 250px;
                    padding: 20px;
                    height: calc(100vh - 100px);
                    overflow-y: auto;
                }
                .widget-palette {
                    padding: 15px;
                }
                .widget-item {
                    padding: 10px;
                    margin: 5px 0;
                    background-color: #ecf0f1;
                    border-radius: 5px;
                    cursor: pointer;
                    border: 1px solid #bdc3c7;
                }
                .widget-item:hover {
                    background-color: #d5dbdb;
                }
                .dashboard-area {
                    background-color: white;
                    border-radius: 8px;
                    padding: 20px;
                    min-height: 500px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .chart-container {
                    margin: 10px 0;
                    background-color: white;
                    border-radius: 5px;
                    padding: 15px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                .controls {
                    margin-bottom: 20px;
                }
                .btn {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    margin-right: 10px;
                }
                .btn:hover {
                    background-color: #2980b9;
                }
                .filter-panel {
                    background-color: #ecf0f1;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>DAP 交互式分析器</h1>
                <div>
                    <button class="btn" onclick="createNewDashboard()">新建仪表板</button>
                    <button class="btn" onclick="saveDashboard()">保存</button>
                </div>
            </div>

            <div class="sidebar">
                <div class="widget-palette">
                    <h3>分析组件</h3>
                    <div class="widget-item" onclick="addWidget('chart')">📊 图表分析</div>
                    <div class="widget-item" onclick="addWidget('table')">📋 数据表格</div>
                    <div class="widget-item" onclick="addWidget('metric')">📈 关键指标</div>
                    <div class="widget-item" onclick="addWidget('filter')">🔍 数据筛选</div>
                    <div class="widget-item" onclick="addWidget('summary')">📄 数据汇总</div>
                </div>

                <div class="widget-palette">
                    <h3>图表类型</h3>
                    <div class="widget-item" onclick="setChartType('bar')">📊 柱状图</div>
                    <div class="widget-item" onclick="setChartType('line')">📈 折线图</div>
                    <div class="widget-item" onclick="setChartType('pie')">🥧 饼图</div>
                    <div class="widget-item" onclick="setChartType('scatter')">⚫ 散点图</div>
                    <div class="widget-item" onclick="setChartType('heatmap')">🔥 热力图</div>
                </div>
            </div>

            <div class="main-content">
                <div class="filter-panel">
                    <h4>数据筛选</h4>
                    <div id="filters-container">
                        <!-- 动态筛选器 -->
                    </div>
                    <button class="btn" onclick="applyFilters()">应用筛选</button>
                </div>

                <div class="dashboard-area" id="dashboard">
                    <h3>拖拽组件到此处开始分析</h3>
                    <div id="widgets-container">
                        <!-- 动态组件 -->
                    </div>
                </div>
            </div>

            <script>
                let currentDashboard = null;
                let widgetCounter = 0;

                function addWidget(type) {
                    widgetCounter++;
                    const widgetId = 'widget_' + widgetCounter;

                    const widgetHtml = `
                        <div class="chart-container" id="${widgetId}">
                            <h4>${type} 组件 ${widgetCounter}</h4>
                            <div id="${widgetId}_content">正在加载...</div>
                            <button onclick="configureWidget('${widgetId}')">配置</button>
                            <button onclick="removeWidget('${widgetId}')">删除</button>
                        </div>
                    `;

                    $('#widgets-container').append(widgetHtml);

                    // 生成示例数据
                    generateSampleChart(widgetId + '_content', type);
                }

                function generateSampleChart(containerId, type) {
                    const data = {
                        chart_type: type,
                        data_source: 'sample_data'
                    };

                    $.ajax({
                        url: '/api/charts/generate',
                        method: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify(data),
                        success: function(response) {
                            if (response.status === 'success') {
                                document.getElementById(containerId).innerHTML = response.chart_html;
                            }
                        }
                    });
                }

                function setChartType(chartType) {
                    console.log('设置图表类型:', chartType);
                }

                function configureWidget(widgetId) {
                    alert('配置组件: ' + widgetId);
                }

                function removeWidget(widgetId) {
                    $('#' + widgetId).remove();
                }

                function createNewDashboard() {
                    const name = prompt('请输入仪表板名称:');
                    if (name) {
                        const data = {
                            dashboard_name: name,
                            description: '新建仪表板',
                            created_by: 'user'
                        };

                        $.ajax({
                            url: '/api/dashboards',
                            method: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify(data),
                            success: function(response) {
                                if (response.status === 'success') {
                                    currentDashboard = response.dashboard_id;
                                    alert('仪表板创建成功！');
                                }
                            }
                        });
                    }
                }

                function saveDashboard() {
                    if (currentDashboard) {
                        alert('仪表板已保存！');
                    } else {
                        alert('请先创建仪表板！');
                    }
                }

                function applyFilters() {
                    console.log('应用筛选器');
                }

                // 初始化
                $(document).ready(function() {
                    console.log('DAP 交互式分析器已加载');
                });
            </script>
        </body>
        </html>
        """
        return html_template

    async def _load_dashboards(self):
        """加载仪表板"""
        try:
            with sqlite3.connect(self.analyzer_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT dashboard_id, dashboard_name, description, layout, filters
                    FROM dashboards
                """
                )

                dashboards_loaded = 0
                for row in cursor.fetchall():
                    dashboard_id = row[0]
                    try:
                        layout = json.loads(row[3]) if row[3] else {}
                        filters = json.loads(row[4]) if row[4] else []

                        dashboard = Dashboard(
                            dashboard_id=dashboard_id,
                            dashboard_name=row[1],
                            description=row[2] or "",
                            widgets=[],
                            layout=layout,
                            filters=filters,
                            created_by="",
                            created_at=datetime.now(),
                            updated_at=datetime.now(),
                            is_public=False,
                        )

                        # 加载仪表板的组件
                        dashboard.widgets = await self._load_dashboard_widgets(
                            dashboard_id
                        )

                        with self._lock:
                            self.dashboard_cache[dashboard_id] = dashboard

                        dashboards_loaded += 1

                    except Exception as e:
                        self.logger.error(f"加载仪表板 {dashboard_id} 失败: {e}")

            self.logger.info(f"仪表板加载完成: {dashboards_loaded} 个仪表板")

        except Exception as e:
            self.logger.error(f"加载仪表板失败: {e}")

    async def _load_dashboard_widgets(self, dashboard_id: str) -> List[AnalysisWidget]:
        """加载仪表板组件"""
        try:
            widgets = []

            with sqlite3.connect(self.analyzer_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT widget_id, widget_type, title, data_source,
                           configuration, position, created_at, updated_at
                    FROM analysis_widgets
                    WHERE dashboard_id = ?
                    ORDER BY created_at
                """,
                    (dashboard_id,),
                )

                for row in cursor.fetchall():
                    try:
                        configuration = json.loads(row[4]) if row[4] else {}
                        position = json.loads(row[5]) if row[5] else {}

                        widget = AnalysisWidget(
                            widget_id=row[0],
                            widget_type=row[1],
                            title=row[2],
                            data_source=row[3] or "",
                            configuration=configuration,
                            position=position,
                            created_at=datetime.fromisoformat(row[6]),
                            updated_at=datetime.fromisoformat(row[7]),
                        )

                        widgets.append(widget)

                    except Exception as e:
                        self.logger.error(f"加载组件失败: {e}")

            return widgets

        except Exception as e:
            self.logger.error(f"加载仪表板组件失败: {e}")
            return []

    async def create_dashboard(
        self, dashboard_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建仪表板"""
        try:
            dashboard_id = f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            dashboard = Dashboard(
                dashboard_id=dashboard_id,
                dashboard_name=dashboard_config["dashboard_name"],
                description=dashboard_config.get("description", ""),
                widgets=[],
                layout=dashboard_config.get("layout", {}),
                filters=dashboard_config.get("filters", []),
                created_by=dashboard_config.get("created_by", "system"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_public=dashboard_config.get("is_public", False),
            )

            # 保存到数据库
            await self._save_dashboard_to_db(dashboard)

            # 更新缓存
            with self._lock:
                self.dashboard_cache[dashboard_id] = dashboard

            result = {
                "status": "success",
                "dashboard_id": dashboard_id,
                "message": f"仪表板 '{dashboard.dashboard_name}' 创建成功",
            }

            self.logger.info(f"仪表板创建成功: {dashboard_id}")
            return result

        except Exception as e:
            self.logger.error(f"创建仪表板失败: {e}")
            return {"status": "error", "error": str(e)}

    async def _save_dashboard_to_db(self, dashboard: Dashboard):
        """保存仪表板到数据库"""
        try:
            with sqlite3.connect(self.analyzer_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO dashboards
                    (dashboard_id, dashboard_name, description, layout, filters,
                     created_by, created_at, updated_at, is_public)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        dashboard.dashboard_id,
                        dashboard.dashboard_name,
                        dashboard.description,
                        json.dumps(dashboard.layout),
                        json.dumps(dashboard.filters),
                        dashboard.created_by,
                        dashboard.created_at.isoformat(),
                        dashboard.updated_at.isoformat(),
                        dashboard.is_public,
                    ),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"保存仪表板到数据库失败: {e}")
            raise

    async def create_widget(self, widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """创建分析组件"""
        try:
            widget_id = f"widget_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            widget = AnalysisWidget(
                widget_id=widget_id,
                widget_type=widget_config["widget_type"],
                title=widget_config.get("title", "新组件"),
                data_source=widget_config.get("data_source", ""),
                configuration=widget_config.get("configuration", {}),
                position=widget_config.get(
                    "position", {"x": 0, "y": 0, "width": 400, "height": 300}
                ),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # 保存到数据库
            await self._save_widget_to_db(widget, widget_config.get("dashboard_id"))

            # 更新仪表板缓存
            dashboard_id = widget_config.get("dashboard_id")
            if dashboard_id and dashboard_id in self.dashboard_cache:
                with self._lock:
                    self.dashboard_cache[dashboard_id].widgets.append(widget)

            result = {
                "status": "success",
                "widget_id": widget_id,
                "message": f"组件 '{widget.title}' 创建成功",
            }

            self.logger.info(f"分析组件创建成功: {widget_id}")
            return result

        except Exception as e:
            self.logger.error(f"创建分析组件失败: {e}")
            return {"status": "error", "error": str(e)}

    async def _save_widget_to_db(
        self, widget: AnalysisWidget, dashboard_id: str = None
    ):
        """保存组件到数据库"""
        try:
            with sqlite3.connect(self.analyzer_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO analysis_widgets
                    (widget_id, dashboard_id, widget_type, title, data_source,
                     configuration, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        widget.widget_id,
                        dashboard_id,
                        widget.widget_type,
                        widget.title,
                        widget.data_source,
                        json.dumps(widget.configuration),
                        json.dumps(widget.position),
                        widget.created_at.isoformat(),
                        widget.updated_at.isoformat(),
                    ),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"保存组件到数据库失败: {e}")
            raise

    async def execute_analysis(self, analysis_config: Dict[str, Any]) -> Dict[str, Any]:
        """执行分析"""
        try:
            analysis_type = AnalysisType(
                analysis_config.get("analysis_type", "descriptive")
            )
            data_source = analysis_config["data_source"]
            parameters = analysis_config.get("parameters", {})

            analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            result = {
                "analysis_id": analysis_id,
                "analysis_type": analysis_type.value,
                "started_at": datetime.now().isoformat(),
                "results": {},
                "visualizations": [],
                "insights": [],
                "status": "success",
            }

            # 获取数据
            data = await self._get_analysis_data(data_source)
            if data is None or len(data) == 0:
                return {
                    "status": "error",
                    "error": f"数据源 {data_source} 无数据",
                    "started_at": datetime.now().isoformat(),
                }

            # 根据分析类型执行分析
            if analysis_type == AnalysisType.DESCRIPTIVE:
                analysis_results = await self._descriptive_analysis(data, parameters)
            elif analysis_type == AnalysisType.TREND:
                analysis_results = await self._trend_analysis(data, parameters)
            elif analysis_type == AnalysisType.COMPARISON:
                analysis_results = await self._comparison_analysis(data, parameters)
            elif analysis_type == AnalysisType.CORRELATION:
                analysis_results = await self._correlation_analysis(data, parameters)
            elif analysis_type == AnalysisType.DISTRIBUTION:
                analysis_results = await self._distribution_analysis(data, parameters)
            elif analysis_type == AnalysisType.CLUSTERING:
                analysis_results = await self._clustering_analysis(data, parameters)
            elif analysis_type == AnalysisType.OUTLIER:
                analysis_results = await self._outlier_analysis(data, parameters)
            else:
                return {
                    "status": "error",
                    "error": f"不支持的分析类型: {analysis_type.value}",
                    "started_at": datetime.now().isoformat(),
                }

            result["results"] = analysis_results
            result["completed_at"] = datetime.now().isoformat()

            # 生成洞察
            insights = await self._generate_insights(analysis_results, analysis_type)
            result["insights"] = insights

            self.logger.info(f"分析执行完成: {analysis_id}")
            return result

        except Exception as e:
            self.logger.error(f"执行分析失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "started_at": datetime.now().isoformat(),
            }

    async def _get_analysis_data(self, data_source: str) -> Optional[pd.DataFrame]:
        """获取分析数据"""
        try:
            # 检查缓存
            with self._lock:
                if data_source in self.data_cache:
                    cache_entry = self.data_cache[data_source]
                    if datetime.now() - cache_entry["cached_at"] < timedelta(
                        minutes=30
                    ):
                        return cache_entry["data"]

            # 生成示例数据（实际应该从数据源获取）
            data = await self._generate_sample_data(data_source)

            # 缓存数据
            with self._lock:
                self.data_cache[data_source] = {
                    "data": data,
                    "cached_at": datetime.now(),
                }

            return data

        except Exception as e:
            self.logger.error(f"获取分析数据失败: {e}")
            return None

    async def _generate_sample_data(self, data_source: str) -> pd.DataFrame:
        """生成示例数据"""
        try:
            np.random.seed(42)

            if data_source == "financial_data":
                # 财务数据示例
                dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
                data = pd.DataFrame(
                    {
                        "date": dates,
                        "revenue": np.random.normal(100000, 20000, len(dates)),
                        "cost": np.random.normal(60000, 15000, len(dates)),
                        "profit": np.random.normal(40000, 10000, len(dates)),
                        "category": np.random.choice(["A", "B", "C"], len(dates)),
                        "region": np.random.choice(
                            ["北京", "上海", "广州", "深圳"], len(dates)
                        ),
                    }
                )
                data["profit"] = data["revenue"] - data["cost"]

            elif data_source == "audit_data":
                # 审计数据示例
                n_records = 1000
                data = pd.DataFrame(
                    {
                        "account_code": [f"账户{i:04d}" for i in range(n_records)],
                        "amount": np.random.lognormal(10, 1, n_records),
                        "transaction_type": np.random.choice(
                            ["收入", "支出", "转账"], n_records
                        ),
                        "risk_score": np.random.uniform(0, 1, n_records),
                        "department": np.random.choice(
                            ["销售", "采购", "财务", "人事"], n_records
                        ),
                        "quarter": np.random.choice(
                            ["Q1", "Q2", "Q3", "Q4"], n_records
                        ),
                    }
                )

            else:
                # 默认数据示例
                data = pd.DataFrame(
                    {
                        "x": np.random.normal(0, 1, 100),
                        "y": np.random.normal(0, 1, 100),
                        "category": np.random.choice(["类别1", "类别2", "类别3"], 100),
                    }
                )

            return data

        except Exception as e:
            self.logger.error(f"生成示例数据失败: {e}")
            return pd.DataFrame()

    async def _descriptive_analysis(
        self, data: pd.DataFrame, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """描述性分析"""
        try:
            results = {
                "summary_statistics": {},
                "data_types": {},
                "missing_values": {},
                "data_quality": {},
            }

            # 基本统计信息
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) > 0:
                results["summary_statistics"] = (
                    data[numeric_columns].describe().to_dict()
                )

            # 数据类型
            results["data_types"] = data.dtypes.astype(str).to_dict()

            # 缺失值统计
            results["missing_values"] = data.isnull().sum().to_dict()

            # 数据质量评估
            results["data_quality"] = {
                "total_rows": len(data),
                "total_columns": len(data.columns),
                "missing_rate": data.isnull().sum().sum()
                / (len(data) * len(data.columns)),
                "duplicate_rows": data.duplicated().sum(),
            }

            return results

        except Exception as e:
            self.logger.error(f"描述性分析失败: {e}")
            return {}

    async def _trend_analysis(
        self, data: pd.DataFrame, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """趋势分析"""
        try:
            results = {"trends": {}, "seasonal_patterns": {}, "growth_rates": {}}

            date_column = parameters.get("date_column", "date")
            value_columns = parameters.get("value_columns", [])

            if date_column in data.columns:
                data[date_column] = pd.to_datetime(data[date_column])
                data = data.sort_values(date_column)

                for column in value_columns:
                    if column in data.columns and pd.api.types.is_numeric_dtype(
                        data[column]
                    ):
                        # 计算趋势
                        values = data[column].dropna()
                        if len(values) > 1:
                            # 简单线性趋势
                            x = np.arange(len(values))
                            slope, intercept = np.polyfit(x, values, 1)

                            results["trends"][column] = {
                                "slope": float(slope),
                                "direction": "increasing"
                                if slope > 0
                                else "decreasing",
                                "strength": abs(slope),
                            }

                            # 增长率
                            if len(values) > 0:
                                growth_rate = (
                                    (values.iloc[-1] - values.iloc[0])
                                    / values.iloc[0]
                                    * 100
                                )
                                results["growth_rates"][column] = float(growth_rate)

            return results

        except Exception as e:
            self.logger.error(f"趋势分析失败: {e}")
            return {}

    async def _correlation_analysis(
        self, data: pd.DataFrame, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """相关性分析"""
        try:
            results = {"correlation_matrix": {}, "strong_correlations": []}

            numeric_data = data.select_dtypes(include=[np.number])

            if len(numeric_data.columns) > 1:
                corr_matrix = numeric_data.corr()
                results["correlation_matrix"] = corr_matrix.to_dict()

                # 强相关性（绝对值大于0.7）
                strong_corr_threshold = parameters.get("correlation_threshold", 0.7)
                for i in range(len(corr_matrix.columns)):
                    for j in range(i + 1, len(corr_matrix.columns)):
                        corr_value = corr_matrix.iloc[i, j]
                        if abs(corr_value) > strong_corr_threshold:
                            results["strong_correlations"].append(
                                {
                                    "variable1": corr_matrix.columns[i],
                                    "variable2": corr_matrix.columns[j],
                                    "correlation": float(corr_value),
                                    "strength": "strong"
                                    if abs(corr_value) > 0.8
                                    else "moderate",
                                }
                            )

            return results

        except Exception as e:
            self.logger.error(f"相关性分析失败: {e}")
            return {}

    async def generate_chart(self, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """生成图表"""
        try:
            if not PLOTLY_AVAILABLE:
                return {"status": "error", "error": "Plotly 不可用，无法生成图表"}

            chart_type = ChartType(chart_config.get("chart_type", "bar"))
            data_source = chart_config.get("data_source", "sample_data")

            # 获取数据
            data = await self._get_analysis_data(data_source)
            if data is None or len(data) == 0:
                return {"status": "error", "error": "无法获取数据"}

            # 生成图表
            fig = await self._create_plotly_chart(chart_type, data, chart_config)

            if fig is None:
                return {"status": "error", "error": "图表生成失败"}

            # 转换为HTML
            chart_html = fig.to_html(
                include_plotlyjs="cdn", div_id=f"chart_{uuid.uuid4().hex[:8]}"
            )

            result = {
                "status": "success",
                "chart_type": chart_type.value,
                "chart_html": chart_html,
                "data_points": len(data),
            }

            return result

        except Exception as e:
            self.logger.error(f"生成图表失败: {e}")
            return {"status": "error", "error": str(e)}

    async def _create_plotly_chart(
        self, chart_type: ChartType, data: pd.DataFrame, config: Dict[str, Any]
    ):
        """创建Plotly图表"""
        try:
            if chart_type == ChartType.BAR:
                if (
                    "category" in data.columns
                    and len(data.select_dtypes(include=[np.number]).columns) > 0
                ):
                    numeric_col = data.select_dtypes(include=[np.number]).columns[0]
                    grouped = data.groupby("category")[numeric_col].sum().reset_index()
                    fig = px.bar(grouped, x="category", y=numeric_col, title="柱状图分析")
                else:
                    # 默认柱状图
                    fig = px.bar(x=["A", "B", "C"], y=[1, 3, 2], title="示例柱状图")

            elif chart_type == ChartType.LINE:
                if (
                    "date" in data.columns
                    and len(data.select_dtypes(include=[np.number]).columns) > 0
                ):
                    numeric_col = data.select_dtypes(include=[np.number]).columns[0]
                    fig = px.line(data, x="date", y=numeric_col, title="趋势分析")
                else:
                    # 默认折线图
                    fig = px.line(
                        x=range(10), y=np.random.randn(10).cumsum(), title="示例折线图"
                    )

            elif chart_type == ChartType.PIE:
                if "category" in data.columns:
                    category_counts = data["category"].value_counts()
                    fig = px.pie(
                        values=category_counts.values,
                        names=category_counts.index,
                        title="分布分析",
                    )
                else:
                    # 默认饼图
                    fig = px.pie(
                        values=[30, 20, 50], names=["类别1", "类别2", "类别3"], title="示例饼图"
                    )

            elif chart_type == ChartType.SCATTER:
                numeric_cols = data.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) >= 2:
                    fig = px.scatter(
                        data, x=numeric_cols[0], y=numeric_cols[1], title="散点图分析"
                    )
                else:
                    # 默认散点图
                    fig = px.scatter(
                        x=np.random.randn(50), y=np.random.randn(50), title="示例散点图"
                    )

            elif chart_type == ChartType.HEATMAP:
                numeric_data = data.select_dtypes(include=[np.number])
                if len(numeric_data.columns) > 1:
                    corr_matrix = numeric_data.corr()
                    fig = px.imshow(
                        corr_matrix, text_auto=True, aspect="auto", title="相关性热力图"
                    )
                else:
                    # 默认热力图
                    z = np.random.randn(10, 10)
                    fig = px.imshow(z, title="示例热力图")

            else:
                # 默认图表
                fig = px.bar(x=["A", "B", "C"], y=[1, 3, 2], title="默认图表")

            # 设置中文字体和样式
            fig.update_layout(
                font=dict(family="Microsoft YaHei", size=12),
                title_font=dict(size=16),
                showlegend=True,
            )

            return fig

        except Exception as e:
            self.logger.error(f"创建Plotly图表失败: {e}")
            return None

    async def filter_data(self, filter_config: Dict[str, Any]) -> Dict[str, Any]:
        """筛选数据"""
        try:
            data_source = filter_config["data_source"]
            filters = filter_config.get("filters", [])

            # 获取原始数据
            data = await self._get_analysis_data(data_source)
            if data is None:
                return {"status": "error", "error": "无法获取数据"}

            # 应用筛选器
            filtered_data = data.copy()
            applied_filters = []

            for filter_item in filters:
                filter_type = FilterType(filter_item["type"])
                column = filter_item["column"]

                if column not in filtered_data.columns:
                    continue

                if filter_type == FilterType.RANGE:
                    min_val = filter_item.get("min_value")
                    max_val = filter_item.get("max_value")
                    if min_val is not None:
                        filtered_data = filtered_data[filtered_data[column] >= min_val]
                    if max_val is not None:
                        filtered_data = filtered_data[filtered_data[column] <= max_val]
                    applied_filters.append(f"{column}: {min_val} - {max_val}")

                elif filter_type == FilterType.CATEGORICAL:
                    values = filter_item.get("values", [])
                    if values:
                        filtered_data = filtered_data[
                            filtered_data[column].isin(values)
                        ]
                        applied_filters.append(f"{column}: {', '.join(values)}")

                elif filter_type == FilterType.TEXT_SEARCH:
                    search_text = filter_item.get("search_text", "")
                    if search_text:
                        filtered_data = filtered_data[
                            filtered_data[column].str.contains(search_text, na=False)
                        ]
                        applied_filters.append(f"{column}: 包含 '{search_text}'")

            result = {
                "status": "success",
                "original_count": len(data),
                "filtered_count": len(filtered_data),
                "applied_filters": applied_filters,
                "filter_ratio": len(filtered_data) / len(data) if len(data) > 0 else 0,
            }

            # 更新数据缓存
            filtered_source = f"{data_source}_filtered_{hashlib.md5(str(filters).encode()).hexdigest()[:8]}"
            with self._lock:
                self.data_cache[filtered_source] = {
                    "data": filtered_data,
                    "cached_at": datetime.now(),
                }

            result["filtered_data_source"] = filtered_source

            return result

        except Exception as e:
            self.logger.error(f"数据筛选失败: {e}")
            return {"status": "error", "error": str(e)}

    def _get_user_dashboards(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户仪表板"""
        try:
            dashboards = []
            for dashboard_id, dashboard in self.dashboard_cache.items():
                if dashboard.created_by == user_id or dashboard.is_public:
                    dashboards.append(
                        {
                            "dashboard_id": dashboard_id,
                            "dashboard_name": dashboard.dashboard_name,
                            "description": dashboard.description,
                            "widgets_count": len(dashboard.widgets),
                            "created_at": dashboard.created_at.isoformat(),
                            "updated_at": dashboard.updated_at.isoformat(),
                        }
                    )

            return dashboards

        except Exception as e:
            self.logger.error(f"获取用户仪表板失败: {e}")
            return []

    def _get_dashboard_by_id(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取仪表板"""
        try:
            dashboard = self.dashboard_cache.get(dashboard_id)
            if dashboard:
                return {
                    "dashboard_id": dashboard_id,
                    "dashboard_name": dashboard.dashboard_name,
                    "description": dashboard.description,
                    "widgets": [asdict(widget) for widget in dashboard.widgets],
                    "layout": dashboard.layout,
                    "filters": dashboard.filters,
                }
            return None

        except Exception as e:
            self.logger.error(f"获取仪表板失败: {e}")
            return None

    async def start_web_service(self):
        """启动Web服务"""
        try:
            if self.web_enabled and FLASK_AVAILABLE and hasattr(self, "app"):
                self.logger.info(f"启动Web服务: http://{self.web_host}:{self.web_port}")
                self.app.run(
                    host=self.web_host, port=self.web_port, debug=False, threaded=True
                )
            else:
                self.logger.warning("Web服务未启用或Flask不可用")

        except Exception as e:
            self.logger.error(f"启动Web服务失败: {e}")

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

            self.logger.info("交互式分析器资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理失败: {e}")


async def main():
    """测试主函数"""
    config = {
        "analyzer_db_path": "data/test_interactive_analyzer.db",
        "dashboard_cache_path": "data/test_dashboards/",
        "web_enabled": True,
        "web_host": "127.0.0.1",
        "web_port": 8080,
    }

    async with InteractiveAnalyzer(config) as analyzer:
        # 创建测试仪表板
        dashboard_config = {
            "dashboard_name": "财务分析仪表板",
            "description": "财务数据的交互式分析",
            "created_by": "test_user",
        }

        dashboard_result = await analyzer.create_dashboard(dashboard_config)
        print(f"仪表板创建结果: {json.dumps(dashboard_result, indent=2, ensure_ascii=False)}")

        if dashboard_result["status"] == "success":
            dashboard_id = dashboard_result["dashboard_id"]

            # 创建分析组件
            widget_config = {
                "dashboard_id": dashboard_id,
                "widget_type": "chart",
                "title": "收入趋势分析",
                "data_source": "financial_data",
                "configuration": {
                    "chart_type": "line",
                    "x_axis": "date",
                    "y_axis": "revenue",
                },
            }

            widget_result = await analyzer.create_widget(widget_config)
            print(f"组件创建结果: {json.dumps(widget_result, indent=2, ensure_ascii=False)}")

            # 执行分析
            analysis_config = {
                "analysis_type": "descriptive",
                "data_source": "financial_data",
                "parameters": {},
            }

            analysis_result = await analyzer.execute_analysis(analysis_config)
            print(f"分析结果: {json.dumps(analysis_result, indent=2, ensure_ascii=False)}")

        # 启动Web服务（注释掉以避免阻塞）
        # await analyzer.start_web_service()


if __name__ == "__main__":
    asyncio.run(main())
