"""
DAP - 性能监控模块
提供系统性能监控和调试功能
"""

import time
import psutil
import threading
import logging
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """性能指标数据类"""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    memory_before: int
    memory_after: int
    memory_delta: int
    cpu_percent: float
    thread_id: int
    success: bool = True
    error_message: str = ""
    custom_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'operation_name': self.operation_name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'memory_before': self.memory_before,
            'memory_after': self.memory_after,
            'memory_delta': self.memory_delta,
            'cpu_percent': self.cpu_percent,
            'thread_id': self.thread_id,
            'success': self.success,
            'error_message': self.error_message,
            'custom_data': self.custom_data,
            'timestamp': datetime.fromtimestamp(self.start_time).isoformat()
        }

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_metrics: int = 1000):
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.operation_stats = defaultdict(list)
        self._lock = threading.Lock()
        self.monitoring_enabled = True
        
    def is_enabled(self) -> bool:
        """检查监控是否启用"""
        return self.monitoring_enabled
    
    def enable(self):
        """启用监控"""
        self.monitoring_enabled = True
        logger.info("性能监控已启用")
    
    def disable(self):
        """禁用监控"""
        self.monitoring_enabled = False
        logger.info("性能监控已禁用")
    
    def record_metric(self, metric: PerformanceMetric):
        """记录性能指标"""
        if not self.monitoring_enabled:
            return
            
        with self._lock:
            self.metrics.append(metric)
            self.operation_stats[metric.operation_name].append(metric)
            
            # 限制每个操作的历史记录数量
            if len(self.operation_stats[metric.operation_name]) > 100:
                self.operation_stats[metric.operation_name] = \
                    self.operation_stats[metric.operation_name][-100:]
    
    def get_metrics(self, operation_name: str = None, limit: int = None) -> List[PerformanceMetric]:
        """获取性能指标"""
        with self._lock:
            if operation_name:
                metrics = self.operation_stats.get(operation_name, [])
            else:
                metrics = list(self.metrics)
            
            if limit:
                metrics = metrics[-limit:]
                
            return metrics
    
    def get_summary(self, operation_name: str = None) -> Dict[str, Any]:
        """获取性能摘要"""
        metrics = self.get_metrics(operation_name)
        
        if not metrics:
            return {"error": "没有找到性能数据"}
        
        durations = [m.duration for m in metrics]
        memory_deltas = [m.memory_delta for m in metrics]
        success_count = sum(1 for m in metrics if m.success)
        
        return {
            "operation_name": operation_name or "所有操作",
            "total_calls": len(metrics),
            "success_count": success_count,
            "failure_count": len(metrics) - success_count,
            "success_rate": success_count / len(metrics) * 100,
            "duration": {
                "min": min(durations),
                "max": max(durations),
                "avg": sum(durations) / len(durations),
                "total": sum(durations)
            },
            "memory": {
                "min_delta": min(memory_deltas),
                "max_delta": max(memory_deltas),
                "avg_delta": sum(memory_deltas) / len(memory_deltas),
                "total_delta": sum(memory_deltas)
            },
            "time_range": {
                "start": datetime.fromtimestamp(metrics[0].start_time).isoformat(),
                "end": datetime.fromtimestamp(metrics[-1].start_time).isoformat()
            }
        }
    
    def get_slow_operations(self, threshold_seconds: float = 1.0) -> List[PerformanceMetric]:
        """获取慢操作"""
        with self._lock:
            return [m for m in self.metrics if m.duration > threshold_seconds]
    
    def get_memory_intensive_operations(self, threshold_mb: float = 100.0) -> List[PerformanceMetric]:
        """获取内存密集型操作"""
        threshold_bytes = threshold_mb * 1024 * 1024
        with self._lock:
            return [m for m in self.metrics if abs(m.memory_delta) > threshold_bytes]
    
    def clear_metrics(self, operation_name: str = None):
        """清理性能指标"""
        with self._lock:
            if operation_name:
                self.operation_stats[operation_name].clear()
            else:
                self.metrics.clear()
                self.operation_stats.clear()
    
    def export_metrics(self, filepath: str, operation_name: str = None):
        """导出性能指标到文件"""
        metrics = self.get_metrics(operation_name)
        data = [m.to_dict() for m in metrics]
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"性能指标已导出到: {filepath}")
        except Exception as e:
            logger.error(f"导出性能指标失败: {e}")

# 全局性能监控器实例
global_monitor = PerformanceMonitor()

@contextmanager
def performance_monitor(operation_name: str, custom_data: Dict[str, Any] = None, 
                       monitor: PerformanceMonitor = None):
    """性能监控上下文管理器"""
    if monitor is None:
        monitor = global_monitor
    
    if not monitor.is_enabled():
        yield
        return
    
    # 获取初始状态
    process = psutil.Process()
    start_time = time.time()
    memory_before = process.memory_info().rss
    cpu_before = process.cpu_percent()
    thread_id = threading.get_ident()
    
    success = True
    error_message = ""
    
    try:
        yield
    except Exception as e:
        success = False
        error_message = str(e)
        raise
    finally:
        # 获取结束状态
        end_time = time.time()
        memory_after = process.memory_info().rss
        cpu_after = process.cpu_percent()
        
        # 创建性能指标
        metric = PerformanceMetric(
            operation_name=operation_name,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_delta=memory_after - memory_before,
            cpu_percent=(cpu_before + cpu_after) / 2,  # 平均CPU使用率
            thread_id=thread_id,
            success=success,
            error_message=error_message,
            custom_data=custom_data or {}
        )
        
        # 记录指标
        monitor.record_metric(metric)
        
        # 记录到日志
        if success:
            logger.info(
                f"性能监控 - {operation_name}: "
                f"耗时={metric.duration:.3f}s, "
                f"内存变化={metric.memory_delta/1024/1024:.1f}MB, "
                f"CPU={metric.cpu_percent:.1f}%"
            )
        else:
            logger.error(
                f"性能监控 - {operation_name} 失败: "
                f"耗时={metric.duration:.3f}s, "
                f"错误={error_message}"
            )

def monitor_performance(operation_name: str = None, custom_data: Dict[str, Any] = None):
    """性能监控装饰器"""
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        def wrapper(*args, **kwargs):
            with performance_monitor(operation_name, custom_data):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, check_interval: float = 60.0):
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.system_stats = deque(maxlen=1440)  # 保留24小时的数据（每分钟一个点）
        self._lock = threading.Lock()
    
    def start(self):
        """启动系统监控"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("系统监控已启动")
    
    def stop(self):
        """停止系统监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                stats = self._collect_system_stats()
                with self._lock:
                    self.system_stats.append(stats)
            except Exception as e:
                logger.error(f"系统监控数据收集失败: {e}")
            
            time.sleep(self.check_interval)
    
    def _collect_system_stats(self) -> Dict[str, Any]:
        """收集系统统计信息"""
        try:
            process = psutil.Process()
            
            return {
                'timestamp': time.time(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent,
                'process_memory_mb': process.memory_info().rss / 1024 / 1024,
                'process_cpu_percent': process.cpu_percent(),
                'thread_count': process.num_threads(),
                'open_files': len(process.open_files()) if hasattr(process, 'open_files') else 0
            }
        except Exception as e:
            logger.error(f"收集系统统计信息失败: {e}")
            return {'timestamp': time.time(), 'error': str(e)}
    
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前系统状态"""
        return self._collect_system_stats()
    
    def get_history_stats(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """获取历史系统状态"""
        cutoff_time = time.time() - (minutes * 60)
        with self._lock:
            return [
                stats for stats in self.system_stats
                if stats.get('timestamp', 0) > cutoff_time
            ]
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取系统健康报告"""
        current = self.get_current_stats()
        
        health_issues = []
        health_score = 100
        
        # 检查CPU使用率
        if current.get('cpu_percent', 0) > 80:
            health_issues.append("CPU使用率过高")
            health_score -= 20
        
        # 检查内存使用率
        if current.get('memory_percent', 0) > 85:
            health_issues.append("内存使用率过高")
            health_score -= 20
        
        # 检查磁盘使用率
        if current.get('disk_usage', 0) > 90:
            health_issues.append("磁盘空间不足")
            health_score -= 15
        
        # 检查进程内存
        if current.get('process_memory_mb', 0) > 1000:
            health_issues.append("进程内存使用过多")
            health_score -= 10
        
        return {
            'health_score': max(0, health_score),
            'status': 'healthy' if health_score >= 80 else 'warning' if health_score >= 60 else 'critical',
            'issues': health_issues,
            'current_stats': current,
            'timestamp': datetime.now().isoformat()
        }

# 全局系统监控器实例
global_system_monitor = SystemMonitor()