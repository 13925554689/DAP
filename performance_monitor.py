"""
Performance Monitor for DAP System
Real-time system performance monitoring and optimization

Provides comprehensive monitoring of system resources, performance metrics,
and automated optimization recommendations for the DAP audit system.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
import logging
from contextlib import asynccontextmanager
import os
import sys
import threading
from collections import deque
import statistics

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False

try:
    import sqlite3
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.animation import FuncAnimation
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

class PerformanceMonitor:
    """
    Comprehensive performance monitoring system for DAP

    Features:
    - Real-time system resource monitoring
    - Database performance tracking
    - Application-level metrics
    - Automated alerts and optimization suggestions
    - Historical data analysis
    - Dashboard visualization
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.setup_logging()

        # Monitoring configuration
        self.monitoring_interval = self.config.get('monitoring_interval', 5)  # seconds
        self.data_retention_days = self.config.get('data_retention_days', 30)
        self.alert_thresholds = self.config.get('alert_thresholds', {
            'cpu_percent': 80,
            'memory_percent': 85,
            'disk_percent': 90,
            'response_time': 2.0,
            'error_rate': 5.0
        })

        # Metrics storage
        self.metrics_history = {
            'system': deque(maxlen=1000),
            'application': deque(maxlen=1000),
            'database': deque(maxlen=1000),
            'alerts': deque(maxlen=100)
        }

        # Performance tracking
        self.start_time = time.time()
        self.monitoring_active = False
        self.monitoring_task = None

        # Database for persistent storage
        self.db_path = self.config.get('db_path', 'performance_metrics.db')

        # Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            self.registry = CollectorRegistry()
            self.setup_prometheus_metrics()

        # Alert management
        self.alert_callbacks = []
        self.alert_history = []

        self.initialize_monitor()

    def setup_logging(self):
        """Setup enhanced logging for performance monitor"""
        self.logger = logging.getLogger(f"{__name__}.PerformanceMonitor")

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def initialize_monitor(self):
        """Initialize performance monitor"""
        try:
            if SQLITE_AVAILABLE:
                self.setup_database()

            self.logger.info("Performance Monitor initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing Performance Monitor: {e}")

    def setup_database(self):
        """Setup SQLite database for metrics storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    memory_used_gb REAL,
                    memory_total_gb REAL,
                    disk_percent REAL,
                    disk_used_gb REAL,
                    disk_total_gb REAL,
                    network_sent_mb REAL,
                    network_recv_mb REAL,
                    load_average REAL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS application_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    component TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    unit TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS database_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    connection_count INTEGER,
                    active_queries INTEGER,
                    avg_query_time REAL,
                    cache_hit_rate REAL,
                    transactions_per_second REAL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    threshold REAL,
                    resolved TEXT,
                    resolved_at TEXT
                )
            ''')

            conn.commit()
            conn.close()

            self.logger.info("Performance metrics database initialized")

        except Exception as e:
            self.logger.error(f"Error setting up database: {e}")

    def setup_prometheus_metrics(self):
        """Setup Prometheus metrics"""
        try:
            self.prometheus_metrics = {
                # System metrics
                'cpu_usage': Gauge('dap_cpu_usage_percent', 'CPU usage percentage', registry=self.registry),
                'memory_usage': Gauge('dap_memory_usage_percent', 'Memory usage percentage', registry=self.registry),
                'disk_usage': Gauge('dap_disk_usage_percent', 'Disk usage percentage', registry=self.registry),
                'network_sent': Counter('dap_network_sent_bytes_total', 'Network bytes sent', registry=self.registry),
                'network_recv': Counter('dap_network_recv_bytes_total', 'Network bytes received', registry=self.registry),

                # Application metrics
                'request_count': Counter('dap_requests_total', 'Total requests', ['method', 'endpoint'], registry=self.registry),
                'request_duration': Histogram('dap_request_duration_seconds', 'Request duration', ['method', 'endpoint'], registry=self.registry),
                'active_sessions': Gauge('dap_active_sessions', 'Active user sessions', registry=self.registry),
                'error_count': Counter('dap_errors_total', 'Total errors', ['component', 'error_type'], registry=self.registry),

                # Database metrics
                'db_connections': Gauge('dap_db_connections', 'Database connections', registry=self.registry),
                'db_query_duration': Histogram('dap_db_query_duration_seconds', 'Database query duration', registry=self.registry),
                'db_cache_hits': Counter('dap_db_cache_hits_total', 'Database cache hits', registry=self.registry),
                'db_cache_misses': Counter('dap_db_cache_misses_total', 'Database cache misses', registry=self.registry)
            }

            self.logger.info("Prometheus metrics initialized")

        except Exception as e:
            self.logger.error(f"Error setting up Prometheus metrics: {e}")

    async def start_monitoring(self):
        """Start performance monitoring"""
        if self.monitoring_active:
            self.logger.warning("Monitoring is already active")
            return

        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self.monitoring_loop())

        self.logger.info("Performance monitoring started")

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        if not self.monitoring_active:
            return

        self.monitoring_active = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Performance monitoring stopped")

    async def monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Collect system metrics
                system_metrics = await self.collect_system_metrics()
                if system_metrics:
                    self.metrics_history['system'].append(system_metrics)
                    await self.store_system_metrics(system_metrics)
                    await self.check_system_alerts(system_metrics)

                # Collect application metrics
                app_metrics = await self.collect_application_metrics()
                if app_metrics:
                    self.metrics_history['application'].append(app_metrics)

                # Collect database metrics
                db_metrics = await self.collect_database_metrics()
                if db_metrics:
                    self.metrics_history['database'].append(db_metrics)
                    await self.store_database_metrics(db_metrics)

                # Update Prometheus metrics
                if PROMETHEUS_AVAILABLE:
                    await self.update_prometheus_metrics(system_metrics, app_metrics, db_metrics)

                # Cleanup old data
                await self.cleanup_old_data()

                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)

    async def collect_system_metrics(self) -> Optional[Dict[str, Any]]:
        """Collect system-level performance metrics"""
        if not PSUTIL_AVAILABLE:
            return None

        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else cpu_percent / 100

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)

            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)

            # Network metrics
            network = psutil.net_io_counters()
            network_sent_mb = network.bytes_sent / (1024**2)
            network_recv_mb = network.bytes_recv / (1024**2)

            # GPU metrics if available
            gpu_metrics = {}
            if GPUTIL_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]  # First GPU
                        gpu_metrics = {
                            'gpu_percent': gpu.load * 100,
                            'gpu_memory_percent': gpu.memoryUtil * 100,
                            'gpu_temperature': gpu.temperature
                        }
                except Exception:
                    pass

            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'load_average': load_avg,
                'memory_percent': memory_percent,
                'memory_used_gb': memory_used_gb,
                'memory_total_gb': memory_total_gb,
                'disk_percent': disk_percent,
                'disk_used_gb': disk_used_gb,
                'disk_total_gb': disk_total_gb,
                'network_sent_mb': network_sent_mb,
                'network_recv_mb': network_recv_mb,
                **gpu_metrics
            }

            return metrics

        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return None

    async def collect_application_metrics(self) -> Optional[Dict[str, Any]]:
        """Collect application-level performance metrics"""
        try:
            # This would integrate with actual DAP components
            # For now, we'll provide mock data

            metrics = {
                'timestamp': datetime.now().isoformat(),
                'active_sessions': len(getattr(self, 'active_sessions', {})),
                'total_requests': getattr(self, 'total_requests', 0),
                'avg_response_time': getattr(self, 'avg_response_time', 0.1),
                'error_rate': getattr(self, 'error_rate', 0.0),
                'memory_usage_app': self.get_process_memory_usage(),
                'threads_count': threading.active_count(),
                'components_status': {
                    'data_ingestor': 'healthy',
                    'audit_engine': 'healthy',
                    'api_server': 'healthy',
                    'database': 'healthy'
                }
            }

            return metrics

        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {e}")
            return None

    async def collect_database_metrics(self) -> Optional[Dict[str, Any]]:
        """Collect database performance metrics"""
        try:
            # Mock database metrics - in real implementation,
            # this would connect to actual database and collect metrics

            metrics = {
                'timestamp': datetime.now().isoformat(),
                'connection_count': 10,
                'active_queries': 2,
                'avg_query_time': 0.15,
                'cache_hit_rate': 85.5,
                'transactions_per_second': 25.3,
                'slow_queries': 0,
                'deadlocks': 0,
                'table_locks': 1
            }

            return metrics

        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {e}")
            return None

    def get_process_memory_usage(self) -> float:
        """Get current process memory usage in MB"""
        try:
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                return process.memory_info().rss / (1024**2)
            return 0.0
        except Exception:
            return 0.0

    async def store_system_metrics(self, metrics: Dict[str, Any]):
        """Store system metrics in database"""
        if not SQLITE_AVAILABLE:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO system_metrics (
                    timestamp, cpu_percent, memory_percent, memory_used_gb, memory_total_gb,
                    disk_percent, disk_used_gb, disk_total_gb, network_sent_mb, network_recv_mb, load_average
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics['timestamp'],
                metrics['cpu_percent'],
                metrics['memory_percent'],
                metrics['memory_used_gb'],
                metrics['memory_total_gb'],
                metrics['disk_percent'],
                metrics['disk_used_gb'],
                metrics['disk_total_gb'],
                metrics['network_sent_mb'],
                metrics['network_recv_mb'],
                metrics['load_average']
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.error(f"Error storing system metrics: {e}")

    async def store_database_metrics(self, metrics: Dict[str, Any]):
        """Store database metrics in database"""
        if not SQLITE_AVAILABLE:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO database_metrics (
                    timestamp, connection_count, active_queries, avg_query_time,
                    cache_hit_rate, transactions_per_second
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                metrics['timestamp'],
                metrics['connection_count'],
                metrics['active_queries'],
                metrics['avg_query_time'],
                metrics['cache_hit_rate'],
                metrics['transactions_per_second']
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.error(f"Error storing database metrics: {e}")

    async def check_system_alerts(self, metrics: Dict[str, Any]):
        """Check for system alerts based on thresholds"""
        try:
            alerts = []

            # CPU alert
            if metrics['cpu_percent'] > self.alert_thresholds['cpu_percent']:
                alert = {
                    'type': 'system',
                    'severity': 'warning' if metrics['cpu_percent'] < 95 else 'critical',
                    'message': f"High CPU usage: {metrics['cpu_percent']:.1f}%",
                    'metric_name': 'cpu_percent',
                    'metric_value': metrics['cpu_percent'],
                    'threshold': self.alert_thresholds['cpu_percent'],
                    'timestamp': datetime.now().isoformat()
                }
                alerts.append(alert)

            # Memory alert
            if metrics['memory_percent'] > self.alert_thresholds['memory_percent']:
                alert = {
                    'type': 'system',
                    'severity': 'warning' if metrics['memory_percent'] < 95 else 'critical',
                    'message': f"High memory usage: {metrics['memory_percent']:.1f}%",
                    'metric_name': 'memory_percent',
                    'metric_value': metrics['memory_percent'],
                    'threshold': self.alert_thresholds['memory_percent'],
                    'timestamp': datetime.now().isoformat()
                }
                alerts.append(alert)

            # Disk alert
            if metrics['disk_percent'] > self.alert_thresholds['disk_percent']:
                alert = {
                    'type': 'system',
                    'severity': 'warning' if metrics['disk_percent'] < 95 else 'critical',
                    'message': f"High disk usage: {metrics['disk_percent']:.1f}%",
                    'metric_name': 'disk_percent',
                    'metric_value': metrics['disk_percent'],
                    'threshold': self.alert_thresholds['disk_percent'],
                    'timestamp': datetime.now().isoformat()
                }
                alerts.append(alert)

            # Process alerts
            for alert in alerts:
                await self.process_alert(alert)

        except Exception as e:
            self.logger.error(f"Error checking system alerts: {e}")

    async def process_alert(self, alert: Dict[str, Any]):
        """Process and store alert"""
        try:
            # Add to alert history
            self.alert_history.append(alert)
            self.metrics_history['alerts'].append(alert)

            # Store in database
            if SQLITE_AVAILABLE:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO alerts (
                        timestamp, alert_type, severity, message,
                        metric_name, metric_value, threshold, resolved
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert['timestamp'],
                    alert['type'],
                    alert['severity'],
                    alert['message'],
                    alert['metric_name'],
                    alert['metric_value'],
                    alert['threshold'],
                    'false'
                ))

                conn.commit()
                conn.close()

            # Log alert
            if alert['severity'] == 'critical':
                self.logger.error(f"CRITICAL ALERT: {alert['message']}")
            else:
                self.logger.warning(f"WARNING ALERT: {alert['message']}")

            # Call alert callbacks
            for callback in self.alert_callbacks:
                try:
                    await callback(alert)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}")

        except Exception as e:
            self.logger.error(f"Error processing alert: {e}")

    async def update_prometheus_metrics(self, system_metrics: Dict[str, Any], app_metrics: Dict[str, Any], db_metrics: Dict[str, Any]):
        """Update Prometheus metrics"""
        if not PROMETHEUS_AVAILABLE:
            return

        try:
            if system_metrics:
                self.prometheus_metrics['cpu_usage'].set(system_metrics['cpu_percent'])
                self.prometheus_metrics['memory_usage'].set(system_metrics['memory_percent'])
                self.prometheus_metrics['disk_usage'].set(system_metrics['disk_percent'])

            if db_metrics:
                self.prometheus_metrics['db_connections'].set(db_metrics['connection_count'])

        except Exception as e:
            self.logger.error(f"Error updating Prometheus metrics: {e}")

    async def cleanup_old_data(self):
        """Cleanup old metrics data based on retention policy"""
        if not SQLITE_AVAILABLE:
            return

        try:
            cutoff_date = datetime.now() - timedelta(days=self.data_retention_days)
            cutoff_str = cutoff_date.isoformat()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Clean up old system metrics
            cursor.execute('DELETE FROM system_metrics WHERE timestamp < ?', (cutoff_str,))

            # Clean up old application metrics
            cursor.execute('DELETE FROM application_metrics WHERE timestamp < ?', (cutoff_str,))

            # Clean up old database metrics
            cursor.execute('DELETE FROM database_metrics WHERE timestamp < ?', (cutoff_str,))

            # Clean up old resolved alerts
            alert_cutoff = datetime.now() - timedelta(days=7)  # Keep alerts for 7 days
            cursor.execute('DELETE FROM alerts WHERE timestamp < ? AND resolved = "true"', (alert_cutoff.isoformat(),))

            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        try:
            current_time = datetime.now().isoformat()

            # Get latest metrics from each category
            latest_system = self.metrics_history['system'][-1] if self.metrics_history['system'] else {}
            latest_app = self.metrics_history['application'][-1] if self.metrics_history['application'] else {}
            latest_db = self.metrics_history['database'][-1] if self.metrics_history['database'] else {}

            # Recent alerts (last 10)
            recent_alerts = list(self.metrics_history['alerts'])[-10:]

            return {
                'timestamp': current_time,
                'system': latest_system,
                'application': latest_app,
                'database': latest_db,
                'alerts': recent_alerts,
                'monitoring_status': {
                    'active': self.monitoring_active,
                    'uptime': time.time() - self.start_time,
                    'data_points': {
                        'system': len(self.metrics_history['system']),
                        'application': len(self.metrics_history['application']),
                        'database': len(self.metrics_history['database'])
                    }
                }
            }

        except Exception as e:
            self.logger.error(f"Error getting current metrics: {e}")
            return {'error': str(e)}

    def get_historical_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get historical performance metrics"""
        try:
            if not SQLITE_AVAILABLE:
                return {'error': 'Database not available'}

            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_str = cutoff_time.isoformat()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get system metrics
            cursor.execute('''
                SELECT * FROM system_metrics
                WHERE timestamp > ?
                ORDER BY timestamp
            ''', (cutoff_str,))

            system_data = []
            for row in cursor.fetchall():
                system_data.append({
                    'timestamp': row[1],
                    'cpu_percent': row[2],
                    'memory_percent': row[3],
                    'disk_percent': row[5]
                })

            # Get database metrics
            cursor.execute('''
                SELECT * FROM database_metrics
                WHERE timestamp > ?
                ORDER BY timestamp
            ''', (cutoff_str,))

            db_data = []
            for row in cursor.fetchall():
                db_data.append({
                    'timestamp': row[1],
                    'connection_count': row[2],
                    'avg_query_time': row[4],
                    'cache_hit_rate': row[5]
                })

            conn.close()

            return {
                'system_metrics': system_data,
                'database_metrics': db_data,
                'period_hours': hours
            }

        except Exception as e:
            self.logger.error(f"Error getting historical metrics: {e}")
            return {'error': str(e)}

    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            current_metrics = self.get_current_metrics()
            historical_metrics = self.get_historical_metrics(24)

            # Calculate averages and trends
            report = {
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'monitoring_status': 'active' if self.monitoring_active else 'inactive',
                    'uptime_hours': (time.time() - self.start_time) / 3600,
                    'total_alerts': len(self.alert_history),
                    'critical_alerts': len([a for a in self.alert_history if a.get('severity') == 'critical'])
                },
                'current_status': current_metrics,
                'recommendations': self.generate_recommendations(current_metrics, historical_metrics)
            }

            # Add performance analysis
            if historical_metrics.get('system_metrics'):
                system_data = historical_metrics['system_metrics']
                if system_data:
                    cpu_values = [m['cpu_percent'] for m in system_data if m.get('cpu_percent')]
                    memory_values = [m['memory_percent'] for m in system_data if m.get('memory_percent')]

                    if cpu_values and memory_values:
                        report['analysis'] = {
                            'cpu': {
                                'average': statistics.mean(cpu_values),
                                'peak': max(cpu_values),
                                'trend': 'stable'  # Simplified trend analysis
                            },
                            'memory': {
                                'average': statistics.mean(memory_values),
                                'peak': max(memory_values),
                                'trend': 'stable'
                            }
                        }

            return report

        except Exception as e:
            self.logger.error(f"Error generating performance report: {e}")
            return {'error': str(e)}

    def generate_recommendations(self, current_metrics: Dict[str, Any], historical_metrics: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []

        try:
            system = current_metrics.get('system', {})

            # CPU recommendations
            if system.get('cpu_percent', 0) > 80:
                recommendations.append("CPU使用率偏高，建议检查并优化高CPU消耗的进程")

            # Memory recommendations
            if system.get('memory_percent', 0) > 85:
                recommendations.append("内存使用率偏高，建议增加内存或优化内存使用")

            # Disk recommendations
            if system.get('disk_percent', 0) > 90:
                recommendations.append("磁盘空间不足，建议清理或扩容磁盘")

            # Database recommendations
            db = current_metrics.get('database', {})
            if db.get('avg_query_time', 0) > 1.0:
                recommendations.append("数据库查询时间较长，建议优化SQL查询或添加索引")

            if db.get('cache_hit_rate', 100) < 80:
                recommendations.append("数据库缓存命中率较低，建议调整缓存配置")

            # General recommendations
            if not recommendations:
                recommendations.append("系统运行状态良好，继续保持当前配置")

        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
            recommendations.append("无法生成建议，请检查系统状态")

        return recommendations

    def add_alert_callback(self, callback: Callable):
        """Add alert callback function"""
        self.alert_callbacks.append(callback)

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus not available\n"

        try:
            return generate_latest(self.registry).decode('utf-8')
        except Exception as e:
            return f"# Error generating metrics: {e}\n"

    async def start_dashboard_server(self, port: int = 8080):
        """Start simple HTTP dashboard server"""
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import json

            class DashboardHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/':
                        self.send_dashboard_html()
                    elif self.path == '/metrics':
                        self.send_json_response(self.server.monitor.get_current_metrics())
                    elif self.path == '/historical':
                        self.send_json_response(self.server.monitor.get_historical_metrics())
                    elif self.path == '/report':
                        self.send_json_response(self.server.monitor.generate_performance_report())
                    elif self.path == '/prometheus':
                        self.send_prometheus_metrics()
                    else:
                        self.send_error(404)

                def send_dashboard_html(self):
                    html = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>DAP Performance Monitor</title>
                        <meta charset="UTF-8">
                        <style>
                            body { font-family: Arial, sans-serif; margin: 20px; }
                            .metric { margin: 10px 0; padding: 10px; border: 1px solid #ccc; }
                            .alert { background-color: #ffcccc; }
                            .good { background-color: #ccffcc; }
                        </style>
                    </head>
                    <body>
                        <h1>DAP Performance Monitor Dashboard</h1>
                        <div id="metrics"></div>
                        <script>
                            function updateMetrics() {
                                fetch('/metrics')
                                    .then(response => response.json())
                                    .then(data => {
                                        document.getElementById('metrics').innerHTML =
                                            '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                                    });
                            }
                            updateMetrics();
                            setInterval(updateMetrics, 5000);
                        </script>
                    </body>
                    </html>
                    """
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html.encode())

                def send_json_response(self, data):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(data, indent=2).encode())

                def send_prometheus_metrics(self):
                    metrics = self.server.monitor.get_prometheus_metrics()
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(metrics.encode())

            server = HTTPServer(('localhost', port), DashboardHandler)
            server.monitor = self

            self.logger.info(f"Performance dashboard started on http://localhost:{port}")

            # Run server in background thread
            import threading
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()

            return server

        except Exception as e:
            self.logger.error(f"Error starting dashboard server: {e}")
            return None

# Test and main execution
async def test_performance_monitor():
    """Test performance monitor functionality"""
    print("Testing Performance Monitor...")

    monitor = PerformanceMonitor()
    print(f"✓ Monitor initialized")

    # Start monitoring for a short period
    await monitor.start_monitoring()
    print("✓ Monitoring started")

    # Wait a bit to collect some data
    await asyncio.sleep(3)

    # Get current metrics
    metrics = monitor.get_current_metrics()
    print(f"✓ Current metrics collected: {bool(metrics.get('system'))}")

    # Generate report
    report = monitor.generate_performance_report()
    print(f"✓ Performance report generated: {bool(report.get('summary'))}")

    # Stop monitoring
    await monitor.stop_monitoring()
    print("✓ Monitoring stopped")

    print("✓ Performance Monitor test completed")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='DAP Performance Monitor')
    parser.add_argument('--start', '-s', action='store_true', help='Start monitoring')
    parser.add_argument('--dashboard', '-d', action='store_true', help='Start dashboard server')
    parser.add_argument('--port', '-p', type=int, default=8080, help='Dashboard port')
    parser.add_argument('--report', '-r', action='store_true', help='Generate performance report')
    parser.add_argument('--test', '-t', action='store_true', help='Run test mode')

    args = parser.parse_args()

    async def main():
        monitor = PerformanceMonitor()

        if args.test:
            await test_performance_monitor()

        elif args.report:
            report = monitor.generate_performance_report()
            print(json.dumps(report, indent=2, ensure_ascii=False))

        elif args.start or args.dashboard:
            await monitor.start_monitoring()

            if args.dashboard:
                server = await monitor.start_dashboard_server(args.port)
                print(f"Dashboard available at http://localhost:{args.port}")

            try:
                print("Performance monitoring running... Press Ctrl+C to stop")
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping performance monitor...")
                await monitor.stop_monitoring()

        else:
            print("DAP Performance Monitor")
            print("Use --start to start monitoring, --dashboard for web interface, or --test for testing")
            print("Example: python performance_monitor.py --start --dashboard")

    asyncio.run(main())