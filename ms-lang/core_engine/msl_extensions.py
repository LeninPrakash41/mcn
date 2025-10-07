"""
MSL Version 2.0 Extensions
- AI Context Engine
- Typed Variables (optional)
- Parallel Tasks
- Package System
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

@dataclass
class MSLTask:
    name: str
    coroutine: Any
    result: Any = None
    completed: bool = False

class MSLAIContext:
    """AI Context Engine for enhanced AI reasoning"""
    
    def __init__(self):
        self.context_history = []
        self.variables_context = {}
        
    def add_context(self, key: str, value: Any):
        """Add context for AI reasoning"""
        self.variables_context[key] = value
        
    def get_enhanced_prompt(self, prompt: str, include_vars: bool = True) -> str:
        """Enhance prompt with context"""
        if not include_vars:
            return prompt
            
        context_str = ""
        if self.variables_context:
            context_str = "\nContext variables:\n"
            for key, value in self.variables_context.items():
                context_str += f"- {key}: {value}\n"
                
        return f"{prompt}{context_str}"

class MSLPackageManager:
    """Simple package management system"""
    
    def __init__(self):
        self.packages_dir = "msl_packages"
        self.installed_packages = {}
        self._ensure_packages_dir()
        
    def _ensure_packages_dir(self):
        if not os.path.exists(self.packages_dir):
            os.makedirs(self.packages_dir)
            
    def add_package(self, package_name: str, functions: Dict[str, Any]):
        """Add a package with functions"""
        self.installed_packages[package_name] = functions
        
        # Save package info
        package_file = os.path.join(self.packages_dir, f"{package_name}.json")
        with open(package_file, 'w') as f:
            json.dump({
                "name": package_name,
                "functions": list(functions.keys()),
                "installed": True
            }, f, indent=2)
            
    def get_package_functions(self, package_name: str) -> Dict[str, Any]:
        """Get functions from a package"""
        return self.installed_packages.get(package_name, {})
        
    def list_packages(self) -> List[str]:
        """List installed packages"""
        return list(self.installed_packages.keys())

class MSLAsyncRuntime:
    """Async runtime for parallel task execution"""
    
    def __init__(self):
        self.tasks = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def create_task(self, name: str, func, *args, **kwargs):
        """Create a named task"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def task_wrapper():
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
                
        task = MSLTask(name=name, coroutine=task_wrapper())
        self.tasks[name] = task
        return task
        
    async def await_tasks(self, *task_names):
        """Wait for multiple tasks to complete"""
        tasks_to_wait = []
        for name in task_names:
            if name in self.tasks:
                tasks_to_wait.append(self.tasks[name].coroutine)
                
        if tasks_to_wait:
            results = await asyncio.gather(*tasks_to_wait, return_exceptions=True)
            
            # Update task results
            for i, name in enumerate(task_names):
                if name in self.tasks:
                    self.tasks[name].result = results[i]
                    self.tasks[name].completed = True
                    
            return results
        return []

class MSLTypeChecker:
    """Optional type checking for MSL variables"""
    
    def __init__(self):
        self.type_hints = {}
        
    def add_type_hint(self, var_name: str, var_type: str):
        """Add type hint for variable"""
        self.type_hints[var_name] = var_type
        
    def check_type(self, var_name: str, value: Any) -> bool:
        """Check if value matches expected type"""
        if var_name not in self.type_hints:
            return True  # No type hint, allow any type
            
        expected_type = self.type_hints[var_name]
        
        type_map = {
            'string': str,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict
        }
        
        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])
            
        return True

# Built-in packages
def create_db_package():
    """Database utilities package"""
    def batch_insert(table: str, records: List[Dict]):
        # Mock implementation
        return f"Inserted {len(records)} records into {table}"
        
    def backup_table(table: str):
        return f"Backed up table {table}"
        
    return {
        'batch_insert': batch_insert,
        'backup_table': backup_table
    }

def create_http_package():
    """HTTP utilities package"""
    import requests
    
    def get_json(url: str):
        response = requests.get(url)
        return response.json()
        
    def post_form(url: str, data: Dict):
        response = requests.post(url, data=data)
        return response.text
        
    return {
        'get_json': get_json,
        'post_form': post_form
    }

def create_ai_package():
    """Enhanced AI utilities package"""
    def summarize(text: str):
        return f"Summary: {text[:50]}..."
        
    def analyze_sentiment(text: str):
        # Mock sentiment analysis
        return {"sentiment": "positive", "confidence": 0.85}
        
    def predict_trend(data: List):
        return {"trend": "upward", "confidence": 0.75}
        
    return {
        'summarize': summarize,
        'analyze_sentiment': analyze_sentiment,
        'predict_trend': predict_trend
    }