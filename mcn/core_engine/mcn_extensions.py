"""
MCN Version 2.0 Extensions
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
class MCNTask:
    name: str
    coroutine: Any
    result: Any = None
    completed: bool = False


class MCNAIContext:
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


class MCNPackageManager:
    """Simple package management system"""

    def __init__(self):
        self.packages_dir = "mcn_packages"
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
        with open(package_file, "w") as f:
            json.dump(
                {
                    "name": package_name,
                    "functions": list(functions.keys()),
                    "installed": True,
                },
                f,
                indent=2,
            )

    def get_package_functions(self, package_name: str) -> Dict[str, Any]:
        """Get functions from a package"""
        return self.installed_packages.get(package_name, {})

    def list_packages(self) -> List[str]:
        """List installed packages"""
        return list(self.installed_packages.keys())


class MCNAsyncRuntime:
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

        task = MCNTask(name=name, coroutine=task_wrapper())
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


class MCNTypeChecker:
    """Optional type checking for MCN variables"""

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
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])

        return True


# Built-in packages
def create_db_package():
    """Real database utilities package"""
    import sqlite3
    import json
    import time

    def batch_insert(table: str, records: List[Dict]):
        """Real batch insert into database"""
        if not records:
            return "No records to insert"
        
        try:
            conn = sqlite3.connect("mcn_data.db")
            cursor = conn.cursor()
            
            columns = list(records[0].keys())
            placeholders = ", ".join(["?" for _ in columns])
            column_names = ", ".join(columns)
            
            sql = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"
            
            for record in records:
                values = [record.get(col) for col in columns]
                cursor.execute(sql, values)
            
            conn.commit()
            conn.close()
            
            return f"Successfully inserted {len(records)} records into {table}"
            
        except Exception as e:
            return f"Batch insert failed: {str(e)}"

    def backup_table(table: str, backup_path: str = None):
        """Real table backup to JSON file"""
        try:
            conn = sqlite3.connect("mcn_data.db")
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT * FROM {table}")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            data = [dict(zip(columns, row)) for row in rows]
            
            if not backup_path:
                backup_path = f"{table}_backup_{int(time.time())}.json"
            
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            conn.close()
            
            return f"Table {table} backed up to {backup_path} ({len(data)} records)"
            
        except Exception as e:
            return f"Backup failed: {str(e)}"

    return {"batch_insert": batch_insert, "backup_table": backup_table}


def create_http_package():
    """Real HTTP utilities package"""
    import requests
    import json

    def get_json(url: str, headers: Dict = None, timeout: int = 30):
        try:
            response = requests.get(url, headers=headers or {}, timeout=timeout)
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json(),
                "status_code": response.status_code
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": 0
            }

    def post_form(url: str, data: Dict, headers: Dict = None, timeout: int = 30):
        try:
            response = requests.post(url, data=data, headers=headers or {}, timeout=timeout)
            response.raise_for_status()
            
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            return {
                "success": True,
                "data": response_data,
                "status_code": response.status_code
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": 0
            }

    return {"get_json": get_json, "post_form": post_form}


def create_ai_package():
    """Real AI utilities package with API integrations"""
    import requests
    import os
    import re

    def summarize(text: str, max_length: int = 100):
        api_key = os.getenv("OPENAI_API_KEY")
        
        if api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": f"Summarize this text in {max_length} characters or less: {text}"}
                    ],
                    "max_tokens": 150
                }
                
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                    
            except Exception:
                pass
        
        # Simple extractive summarization
        sentences = re.split(r'[.!?]+', text)
        if len(sentences) <= 2:
            return text[:max_length]
        
        summary = f"{sentences[0].strip()}. {sentences[-2].strip()}."
        return summary[:max_length] + "..." if len(summary) > max_length else summary

    def analyze_sentiment(text: str):
        api_key = os.getenv("OPENAI_API_KEY")
        
        if api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": f"Analyze sentiment (positive/negative/neutral): {text}"}
                    ],
                    "max_tokens": 10
                }
                
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    sentiment = data["choices"][0]["message"]["content"].strip().lower()
                    return {"sentiment": sentiment, "confidence": 0.85}
                    
            except Exception:
                pass
        
        # Simple keyword-based sentiment analysis
        positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'like', 'happy']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'dislike', 'sad', 'angry']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return {"sentiment": "positive", "confidence": 0.7}
        elif negative_count > positive_count:
            return {"sentiment": "negative", "confidence": 0.7}
        else:
            return {"sentiment": "neutral", "confidence": 0.6}

    def predict_trend(data: List):
        if not data or len(data) < 2:
            return {"trend": "insufficient_data", "confidence": 0.0}
        
        try:
            numeric_data = []
            for item in data:
                if isinstance(item, (int, float)):
                    numeric_data.append(float(item))
                elif isinstance(item, dict) and 'value' in item:
                    numeric_data.append(float(item['value']))
                else:
                    numeric_data.append(float(item))
            
            if len(numeric_data) < 2:
                return {"trend": "insufficient_data", "confidence": 0.0}
            
            # Simple trend calculation
            first_half = sum(numeric_data[:len(numeric_data)//2]) / (len(numeric_data)//2)
            second_half = sum(numeric_data[len(numeric_data)//2:]) / (len(numeric_data) - len(numeric_data)//2)
            
            if second_half > first_half * 1.1:
                return {"trend": "upward", "confidence": 0.8}
            elif second_half < first_half * 0.9:
                return {"trend": "downward", "confidence": 0.8}
            else:
                return {"trend": "stable", "confidence": 0.7}
                
        except Exception as e:
            return {"trend": "error", "confidence": 0.0, "error": str(e)}

    return {
        "summarize": summarize,
        "analyze_sentiment": analyze_sentiment,
        "predict_trend": predict_trend,
    }
