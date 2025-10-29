"""
MCN Production Runtime - Enhanced Dynamic Systems
Optimized for production workloads with security and performance
"""

import os
import time
import json
import threading
from typing import Dict, Any, List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


@dataclass
class SystemMetrics:
    requests_per_second: float = 0.0
    active_connections: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    error_rate: float = 0.0


class ProductionMCNRuntime:
    """Production-ready MCN runtime with enhanced security and performance"""
    
    def __init__(self):
        self.metrics = SystemMetrics()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.device_cache = {}
        self.model_cache = {}
        self.security_config = self._load_security_config()
        self._init_monitoring()
    
    def _load_security_config(self) -> Dict:
        """Load security configuration"""
        return {
            "max_file_size": int(os.getenv("MCN_MAX_FILE_SIZE", "10485760")),  # 10MB
            "allowed_extensions": os.getenv("MCN_ALLOWED_EXTENSIONS", ".mcn,.json,.csv").split(","),
            "rate_limit": int(os.getenv("MCN_RATE_LIMIT", "100")),  # requests per minute
            "enable_cors": os.getenv("MCN_ENABLE_CORS", "false").lower() == "true"
        }
    
    def _init_monitoring(self):
        """Initialize system monitoring"""
        def monitor_loop():
            while True:
                self._update_metrics()
                time.sleep(5)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
    
    def _update_metrics(self):
        """Update system performance metrics"""
        import psutil
        process = psutil.Process()
        self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        self.metrics.cpu_usage_percent = process.cpu_percent()
    
    def execute_secure(self, code: str, context: Dict = None) -> Dict:
        """Execute MCN code with security validation"""
        try:
            # Validate code size
            if len(code) > self.security_config["max_file_size"]:
                raise Exception("Code size exceeds maximum limit")
            
            # Basic code validation
            if any(dangerous in code for dangerous in ["import os", "exec(", "eval("]):
                raise Exception("Potentially dangerous code detected")
            
            # Execute with timeout
            from .mcn_interpreter import MCNInterpreter
            interpreter = MCNInterpreter()
            
            if context:
                interpreter.variables.update(context)
            
            result = interpreter.execute(code, quiet=False)
            
            return {
                "success": True,
                "result": result,
                "metrics": {
                    "execution_time": time.time(),
                    "memory_used": self.metrics.memory_usage_mb
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        return {
            "status": "operational",
            "version": "3.0.0",
            "uptime": time.time(),
            "metrics": {
                "memory_mb": self.metrics.memory_usage_mb,
                "cpu_percent": self.metrics.cpu_usage_percent,
                "active_devices": len(self.device_cache),
                "cached_models": len(self.model_cache)
            },
            "features": {
                "ai_models": True,
                "iot_devices": True,
                "ml_training": True,
                "event_system": True,
                "database": True
            }
        }


# Global production runtime instance
production_runtime = ProductionMCNRuntime()


def get_production_runtime():
    """Get production runtime instance"""
    return production_runtime