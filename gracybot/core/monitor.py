



import time
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Any
from collections import deque

from gracybot.core.utils import logger

class MonitorManager:

    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MonitorManager, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):


        self.cpu_history = deque(maxlen=60)
        self.memory_history = deque(maxlen=60)
        self.message_stats = {
            "total_received": 0,
            "total_processed": 0,
            "total_errors": 0,
            "response_times": deque(maxlen=100),
            "per_minute": deque(maxlen=60)
        }
        

        self.plugin_stats = {}
        

        self.start_time = time.time()
        

        self.monitoring_enabled = True
        self.monitor_thread = threading.Thread(target=self._background_monitor, daemon=True)
        self.monitor_thread.start()

        import os as _os
        if _os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            logger.info("监控管理器已初始化并启动")
            logger.info("结构化日志监控管理器已初始化并启动✅加载✅ 核心模块加载完成，版本")
    
    def _background_monitor(self):

        while self.monitoring_enabled:
            try:

                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()
                
                current_time = datetime.now()
                
                self.cpu_history.append({
                    "timestamp": current_time,
                    "value": cpu_percent
                })
                
                self.memory_history.append({
                    "timestamp": current_time,
                    "value": memory_info.percent,
                    "used_mb": memory_info.used / (1024 * 1024),
                    "total_mb": memory_info.total / (1024 * 1024)
                })
                

                self.message_stats["per_minute"].append({
                    "timestamp": current_time,
                    "received": 0,
                    "processed": 0,
                    "errors": 0
                })
                

                time.sleep(60)
                
            except Exception as e:
                logger.error(f"后台监控线程发生异常: {str(e)}", exc_info=True)
                time.sleep(10)
    
    def record_message_received(self):

        self.message_stats["total_received"] += 1

        if self.message_stats["per_minute"]:
            self.message_stats["per_minute"][-1]["received"] += 1
    
    def record_message_processed(self, processing_time: float):

        self.message_stats["total_processed"] += 1
        self.message_stats["response_times"].append(processing_time * 1000)

        if self.message_stats["per_minute"]:
            self.message_stats["per_minute"][-1]["processed"] += 1
    
    def record_message_error(self):

        self.message_stats["total_errors"] += 1

        if self.message_stats["per_minute"]:
            self.message_stats["per_minute"][-1]["errors"] += 1
    
    def record_plugin_execution(self, plugin_name: str, execution_time: float, success: bool):

        if plugin_name not in self.plugin_stats:
            self.plugin_stats[plugin_name] = {
                "total_executions": 0,
                "successful_executions": 0,
                "total_time": 0,
                "avg_execution_time": 0
            }
        
        stats = self.plugin_stats[plugin_name]
        stats["total_executions"] += 1
        if success:
            stats["successful_executions"] += 1
        stats["total_time"] += execution_time
        stats["avg_execution_time"] = stats["total_time"] / stats["total_executions"]
    
    def get_system_status(self) -> Dict[str, Any]:

        uptime = time.time() - self.start_time
        

        avg_response_time = sum(self.message_stats["response_times"]) / len(self.message_stats["response_times"]) \
            if self.message_stats["response_times"] else 0
        

        latest_cpu = self.cpu_history[-1]["value"] if self.cpu_history else 0
        latest_memory = self.memory_history[-1] if self.memory_history else {"value": 0, "used_mb": 0, "total_mb": 0}
        

        error_rate = (self.message_stats["total_errors"] / max(self.message_stats["total_received"], 1)) * 100
        
        return {
            "status": "healthy" if error_rate < 5 else "degraded" if error_rate < 20 else "unhealthy",
            "uptime_seconds": uptime,
            "uptime_formatted": self._format_uptime(uptime),
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_usage_percent": latest_cpu,
                "memory": {
                    "usage_percent": latest_memory["value"],
                    "used_mb": latest_memory["used_mb"],
                    "total_mb": latest_memory["total_mb"]
                }
            },
            "message_stats": {
                "total_received": self.message_stats["total_received"],
                "total_processed": self.message_stats["total_processed"],
                "total_errors": self.message_stats["total_errors"],
                "error_rate_percent": round(error_rate, 2),
                "avg_response_time_ms": round(avg_response_time, 2)
            }
        }
    
    def get_health_check(self) -> Dict[str, Any]:

        system_status = self.get_system_status()
        return {
            "status": system_status["status"],
            "timestamp": system_status["timestamp"],
            "uptime": system_status["uptime_formatted"],
            "service": "GracyBot",
            "version": "1.0.0",
            "checks": {
                "cpu_healthy": system_status["system"]["cpu_usage_percent"] < 90,
                "memory_healthy": system_status["system"]["memory"]["usage_percent"] < 90,
                "error_rate_healthy": system_status["message_stats"]["error_rate_percent"] < 10
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:

        return {
            "cpu_history": list(self.cpu_history),
            "memory_history": list(self.memory_history),
            "message_stats": {
                "minute_history": list(self.message_stats["per_minute"]),
                "response_times": list(self.message_stats["response_times"])
            },
            "plugin_stats": self.plugin_stats
        }
    
    def _format_uptime(self, seconds: float) -> str:

        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0 or parts:
            parts.append(f"{hours}小时")
        if minutes > 0 or parts:
            parts.append(f"{minutes}分钟")
        parts.append(f"{seconds}秒")
        
        return " ".join(parts)
    
    def shutdown(self):

        self.monitoring_enabled = False
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("监控管理器已关闭")


monitor_manager = MonitorManager()
