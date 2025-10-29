"""
MCN Performance Monitoring & Analytics System
Real-time monitoring, metrics collection, and performance analytics
"""

import time
import json
import sqlite3
import threading
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque


@dataclass
class MetricPoint:
    timestamp: float
    metric_name: str
    value: float
    tags: Dict[str, str] = None


@dataclass
class PerformanceEvent:
    event_id: str
    event_type: str
    duration: float
    timestamp: float
    metadata: Dict = None


class MCNMonitor:
    """Real-time performance monitoring system"""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: deque(maxlen=1000))
        self.events = deque(maxlen=5000)
        self.active_timers = {}
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self._init_db()
    
    def _init_db(self):
        """Initialize monitoring database"""
        self.conn = sqlite3.connect("mcn_monitoring.db", check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY,
                timestamp REAL,
                metric_name TEXT,
                value REAL,
                tags TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                event_id TEXT,
                event_type TEXT,
                duration REAL,
                timestamp REAL,
                metadata TEXT
            )
        """)
        self.conn.commit()
    
    def start_timer(self, event_id: str, event_type: str = "operation") -> str:
        """Start performance timer"""
        timer_key = f"{event_type}_{event_id}_{time.time()}"
        self.active_timers[timer_key] = {
            "event_id": event_id,
            "event_type": event_type,
            "start_time": time.time()
        }
        return timer_key
    
    def end_timer(self, timer_key: str, metadata: Dict = None) -> float:
        """End performance timer and record event"""
        if timer_key not in self.active_timers:
            return 0.0
        
        timer_info = self.active_timers.pop(timer_key)
        duration = time.time() - timer_info["start_time"]
        
        event = PerformanceEvent(
            event_id=timer_info["event_id"],
            event_type=timer_info["event_type"],
            duration=duration,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self.events.append(event)
        self._store_event(event)
        
        return duration
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a metric point"""
        metric = MetricPoint(
            timestamp=time.time(),
            metric_name=name,
            value=value,
            tags=tags or {}
        )
        
        self.metrics[name].append(metric)
        self._store_metric(metric)
    
    def increment_counter(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment counter metric"""
        self.counters[name] += value
        self.record_metric(f"counter.{name}", self.counters[name], tags)
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set gauge metric"""
        self.gauges[name] = value
        self.record_metric(f"gauge.{name}", value, tags)
    
    def get_metrics_summary(self, time_window: int = 300) -> Dict:
        """Get metrics summary for time window (seconds)"""
        cutoff_time = time.time() - time_window
        summary = {}
        
        for metric_name, points in self.metrics.items():
            recent_points = [p for p in points if p.timestamp > cutoff_time]
            if recent_points:
                values = [p.value for p in recent_points]
                summary[metric_name] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[-1]
                }
        
        return summary
    
    def get_performance_report(self, time_window: int = 300) -> Dict:
        """Get performance report"""
        cutoff_time = time.time() - time_window
        recent_events = [e for e in self.events if e.timestamp > cutoff_time]
        
        # Group by event type
        by_type = defaultdict(list)
        for event in recent_events:
            by_type[event.event_type].append(event.duration)
        
        report = {}
        for event_type, durations in by_type.items():
            report[event_type] = {
                "count": len(durations),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "total_duration": sum(durations)
            }
        
        return report
    
    def _store_metric(self, metric: MetricPoint):
        """Store metric in database"""
        try:
            self.conn.execute(
                "INSERT INTO metrics (timestamp, metric_name, value, tags) VALUES (?, ?, ?, ?)",
                (metric.timestamp, metric.metric_name, metric.value, json.dumps(metric.tags))
            )
            self.conn.commit()
        except Exception:
            pass  # Fail silently to not impact performance
    
    def _store_event(self, event: PerformanceEvent):
        """Store event in database"""
        try:
            self.conn.execute(
                "INSERT INTO events (event_id, event_type, duration, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                (event.event_id, event.event_type, event.duration, event.timestamp, json.dumps(event.metadata))
            )
            self.conn.commit()
        except Exception:
            pass


class MCNAnalytics:
    """Analytics and insights system"""
    
    def __init__(self, monitor: MCNMonitor):
        self.monitor = monitor
    
    def analyze_performance_trends(self, days: int = 7) -> Dict:
        """Analyze performance trends over time"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        cursor = self.monitor.conn.cursor()
        cursor.execute(
            "SELECT event_type, AVG(duration), COUNT(*) FROM events WHERE timestamp > ? GROUP BY event_type",
            (cutoff_time,)
        )
        
        trends = {}
        for event_type, avg_duration, count in cursor.fetchall():
            trends[event_type] = {
                "avg_duration": avg_duration,
                "total_calls": count,
                "calls_per_day": count / days
            }
        
        return trends
    
    def detect_anomalies(self, threshold_multiplier: float = 2.0) -> List[Dict]:
        """Detect performance anomalies"""
        anomalies = []
        
        # Get baseline performance
        baseline_window = 24 * 3600  # 24 hours
        recent_window = 3600  # 1 hour
        
        baseline_time = time.time() - baseline_window
        recent_time = time.time() - recent_window
        
        cursor = self.monitor.conn.cursor()
        
        # Get baseline averages
        cursor.execute(
            "SELECT event_type, AVG(duration) FROM events WHERE timestamp BETWEEN ? AND ? GROUP BY event_type",
            (baseline_time, recent_time)
        )
        baselines = dict(cursor.fetchall())
        
        # Get recent averages
        cursor.execute(
            "SELECT event_type, AVG(duration) FROM events WHERE timestamp > ? GROUP BY event_type",
            (recent_time,)
        )
        
        for event_type, recent_avg in cursor.fetchall():
            if event_type in baselines:
                baseline_avg = baselines[event_type]
                if recent_avg > baseline_avg * threshold_multiplier:
                    anomalies.append({
                        "event_type": event_type,
                        "baseline_avg": baseline_avg,
                        "recent_avg": recent_avg,
                        "severity": recent_avg / baseline_avg,
                        "detected_at": time.time()
                    })
        
        return anomalies
    
    def generate_dashboard_data(self) -> Dict:
        """Generate data for monitoring dashboard"""
        return {
            "metrics_summary": self.monitor.get_metrics_summary(),
            "performance_report": self.monitor.get_performance_report(),
            "trends": self.analyze_performance_trends(1),  # Last day
            "anomalies": self.detect_anomalies(),
            "system_health": self._get_system_health()
        }
    
    def _get_system_health(self) -> Dict:
        """Get overall system health status"""
        recent_events = [e for e in self.monitor.events if e.timestamp > time.time() - 300]
        
        if not recent_events:
            return {"status": "unknown", "score": 0}
        
        # Calculate health score based on recent performance
        avg_duration = sum(e.duration for e in recent_events) / len(recent_events)
        error_rate = len([e for e in recent_events if e.metadata and e.metadata.get("error")]) / len(recent_events)
        
        health_score = max(0, min(100, 100 - (avg_duration * 10) - (error_rate * 50)))
        
        if health_score > 80:
            status = "healthy"
        elif health_score > 60:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "score": round(health_score, 1),
            "avg_response_time": round(avg_duration, 3),
            "error_rate": round(error_rate * 100, 1)
        }


# Global monitor instance
_monitor = None

def get_monitor() -> MCNMonitor:
    """Get global monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = MCNMonitor()
    return _monitor

def monitor_function(func_name: str = None):
    """Decorator to monitor function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_monitor()
            name = func_name or func.__name__
            timer_key = monitor.start_timer(name, "function")
            
            try:
                result = func(*args, **kwargs)
                monitor.end_timer(timer_key, {"success": True})
                return result
            except Exception as e:
                monitor.end_timer(timer_key, {"success": False, "error": str(e)})
                raise
        
        return wrapper
    return decorator