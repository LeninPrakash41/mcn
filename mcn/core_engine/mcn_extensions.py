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


def create_analytics_package():
    """Real database reporting and analytics package for MCN."""
    import sqlite3
    import json
    import os
    import re
    from typing import List, Dict, Any, Optional

    def _connect(db_path: str = "mcn_data.db"):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def report(
        table: str,
        metrics: Any = None,
        group_by: Any = None,
        filter: Optional[str] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        db_path: str = "mcn_data.db"
    ) -> Dict[str, Any]:
        """
        Build and execute an analytical aggregation report against a database table.
        Example:
            report("deals", metrics="sum(value) as revenue, count(id) as deals", group_by="stage")
        """
        try:
            conn = _connect(db_path)
            cursor = conn.cursor()

            # 1. Resolve select metrics
            if not metrics:
                select_clause = "*"
            elif isinstance(metrics, list):
                parsed_metrics = []
                for m in metrics:
                    m_str = str(m).strip()
                    if ":" in m_str:
                        agg_op, col_name = m_str.split(":", 1)
                        agg_op = agg_op.strip().upper()
                        col_name = col_name.strip()
                        alias = f"{agg_op.lower()}_{col_name.replace('*', 'total')}"
                        parsed_metrics.append(f"{agg_op}({col_name}) AS {alias}")
                    else:
                        parsed_metrics.append(m_str)
                select_clause = ", ".join(parsed_metrics)
            elif isinstance(metrics, dict):
                select_clause = ", ".join(f"{expr} AS {alias}" for alias, expr in metrics.items())
            else:
                select_clause = str(metrics)

            # 2. Resolve group by
            group_clause = ""
            if group_by:
                if isinstance(group_by, list):
                    group_fields = ", ".join(group_by)
                else:
                    group_fields = str(group_by)
                group_clause = f" GROUP BY {group_fields}"
                # Ensure grouped fields are included in SELECT if not wildcard
                if select_clause != "*" and not any(f in select_clause for f in group_fields.split(",")):
                    select_clause = f"{group_fields}, {select_clause}"

            # 3. Resolve filters
            where_clause = f" WHERE {filter}" if filter else ""

            # 4. Resolve order by
            order_clause = f" ORDER BY {order_by}" if order_by else ""

            # 5. Resolve limit
            limit_clause = f" LIMIT {int(limit)}" if limit else ""

            sql = f"SELECT {select_clause} FROM {table}{where_clause}{group_clause}{order_clause}{limit_clause}"
            cursor.execute(sql)
            rows_raw = cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = [dict(row) for row in rows_raw]

            # Compute summary aggregations
            summary = {}
            for col in columns:
                vals = [r[col] for r in rows if isinstance(r.get(col), (int, float))]
                if vals:
                    summary[col] = {
                        "sum": round(sum(vals), 2),
                        "avg": round(sum(vals) / len(vals), 2),
                        "min": min(vals),
                        "max": max(vals),
                        "count": len(vals)
                    }

            conn.close()
            return {
                "success": True,
                "table": table,
                "query": sql,
                "columns": columns,
                "rows": rows,
                "count": len(rows),
                "summary": summary
            }
        except Exception as e:
            return {"success": False, "table": table, "error": str(e), "rows": [], "columns": []}

    def kpi(
        table: str,
        columns: Any = None,
        metrics: Any = None,
        metric: Any = None,
        label: Optional[str] = None,
        filter: Optional[str] = None,
        db_path: str = "mcn_data.db"
    ) -> Dict[str, Any]:
        """
        Compute high-level statistical KPIs for all numeric metrics in a table.
        Supports metrics=["sum:amount", "avg:amount", "count:*"] or columns=["amount"].
        """
        try:
            conn = _connect(db_path)
            cursor = conn.cursor()

            # Get table schema
            cursor.execute(f"PRAGMA table_info({table})")
            table_info = cursor.fetchall()
            all_cols = [r["name"] for r in table_info]

            where_clause = f" WHERE {filter}" if filter else ""

            # Count total records
            cursor.execute(f"SELECT COUNT(*) AS total_count FROM {table}{where_clause}")
            total_count = cursor.fetchone()["total_count"]

            # Target columns / metrics
            raw_metrics = metrics or columns or (metric if isinstance(metric, list) else ([metric] if metric else None))
            target_cols = []
            if raw_metrics:
                items = raw_metrics if isinstance(raw_metrics, list) else [c.strip() for c in str(raw_metrics).split(",")]
                for item in items:
                    if ":" in item:
                        _, col_name = item.split(":", 1)
                        if col_name != "*" and col_name in all_cols:
                            target_cols.append(col_name)
                    elif item in all_cols:
                        target_cols.append(item)
            else:
                target_cols = [r["name"] for r in table_info if any(t in r["type"].lower() for t in ("int", "real", "float", "numeric", "double"))]

            kpi_metrics = {}
            for c in target_cols:
                if c not in all_cols:
                    continue
                cursor.execute(f"SELECT SUM({c}) as total, AVG({c}) as mean, MIN({c}) as minimum, MAX({c}) as maximum FROM {table}{where_clause}")
                res = cursor.fetchone()
                if res and res["total"] is not None:
                    kpi_metrics[c] = {
                        "sum": round(res["total"], 2),
                        "avg": round(res["mean"], 2),
                        "min": res["minimum"],
                        "max": res["maximum"],
                        "formatted_sum": f"${res['total']:,.2f}" if any(k in c.lower() for k in ("price", "value", "revenue", "budget", "amount", "cost")) else f"{res['total']:,}"
                    }

            conn.close()
            total_sum = sum(v["sum"] for v in kpi_metrics.values()) if kpi_metrics else 0
            res_dict = {
                "success": True,
                "table": table,
                "total_records": total_count,
                "total_sum": total_sum,
                "kpis": kpi_metrics
            }
            if kpi_metrics:
                first_k = next(iter(kpi_metrics.values()))
                res_dict["sum"] = first_k["sum"]
                res_dict["avg"] = first_k["avg"]
                res_dict["min"] = first_k["min"]
                res_dict["max"] = first_k["max"]
            return res_dict
        except Exception as e:
            return {"success": False, "table": table, "error": str(e), "total_records": 0, "total_sum": 0, "kpis": {}}

    def trend(
        table: str,
        date_col: Optional[str] = None,
        date_field: Optional[str] = None,
        val_col: Optional[str] = None,
        value_field: Optional[str] = None,
        interval: str = "monthly",
        agg: str = "sum",
        filter: Optional[str] = None,
        db_path: str = "mcn_data.db"
    ) -> Dict[str, Any]:
        """
        Compute time-series aggregation and period-over-period growth rates.
        Intervals: 'daily', 'weekly', 'monthly', 'yearly'
        """
        date_col = date_field or date_col or "created_at"
        val_col = value_field or val_col
        try:
            conn = _connect(db_path)
            cursor = conn.cursor()

            format_map = {
                "daily": "%Y-%m-%d",
                "weekly": "%Y-%W",
                "monthly": "%Y-%m",
                "yearly": "%Y"
            }
            dt_fmt = format_map.get(interval.lower(), "%Y-%m")

            agg_expr = f"{agg.upper()}({val_col})" if val_col else "COUNT(*)"
            where_clause = f" WHERE {filter}" if filter else ""
            where_clause += f" {'AND' if where_clause else 'WHERE'} {date_col} IS NOT NULL AND {date_col} != ''"

            sql = f"""
                SELECT 
                    strftime('{dt_fmt}', {date_col}) AS period,
                    {agg_expr} AS metric_value,
                    COUNT(*) AS record_count
                FROM {table}
                {where_clause}
                GROUP BY period
                ORDER BY period ASC
            """
            cursor.execute(sql)
            rows = [dict(r) for r in cursor.fetchall()]

            series = []
            prev_val = None
            for r in rows:
                v = r["metric_value"] or 0
                growth = None
                if prev_val is not None and prev_val > 0:
                    growth = round(((v - prev_val) / prev_val) * 100, 1)
                series.append({
                    "period": r["period"] or "Unknown",
                    "value": round(v, 2) if isinstance(v, float) else v,
                    "count": r["record_count"],
                    "growth_pct": growth
                })
                prev_val = v

            # Calculate overall trend direction
            overall_growth = None
            if len(series) >= 2 and series[0]["value"] > 0:
                overall_growth = round(((series[-1]["value"] - series[0]["value"]) / series[0]["value"]) * 100, 1)

            conn.close()
            return {
                "success": True,
                "table": table,
                "interval": interval,
                "series": series,
                "overall_growth_pct": overall_growth,
                "trend_direction": "upward" if (overall_growth or 0) > 0 else "downward" if (overall_growth or 0) < 0 else "stable"
            }
        except Exception as e:
            return {"success": False, "table": table, "error": str(e), "series": []}

    def distribution(
        table: str,
        col: Optional[str] = None,
        category_field: Optional[str] = None,
        metric: str = "count",
        agg: Optional[str] = None,
        val_col: Optional[str] = None,
        value_field: Optional[str] = None,
        limit: int = 10,
        pareto: bool = False,
        db_path: str = "mcn_data.db"
    ) -> Dict[str, Any]:
        """
        Calculate category share percentages and distribution for charts/dashboards.
        """
        col = category_field or col or "category"
        val_col = value_field or val_col
        agg_op = agg or metric or "count"
        try:
            conn = _connect(db_path)
            cursor = conn.cursor()

            agg_expr = f"{agg_op.upper()}({val_col})" if val_col and agg_op.lower() != "count" else "COUNT(*)"

            sql = f"""
                SELECT 
                    COALESCE({col}, 'Uncategorized') AS category,
                    {agg_expr} AS metric_val
                FROM {table}
                GROUP BY category
                ORDER BY metric_val DESC
                LIMIT {int(limit)}
            """
            cursor.execute(sql)
            rows = [dict(r) for r in cursor.fetchall()]

            total_sum = sum(r["metric_val"] or 0 for r in rows)
            breakdown = []
            cum_pct = 0.0
            for r in rows:
                val = r["metric_val"] or 0
                pct = round((val / total_sum) * 100, 1) if total_sum > 0 else 0
                cum_pct += pct
                breakdown.append({
                    "category": str(r["category"]),
                    "value": val,
                    "share_pct": pct,
                    "cumulative_pct": round(cum_pct, 1)
                })

            conn.close()
            return {
                "success": True,
                "table": table,
                "column": col,
                "total": total_sum,
                "items": breakdown,
                "breakdown": breakdown
            }
        except Exception as e:
            return {"success": False, "table": table, "error": str(e), "items": [], "breakdown": []}

    def pivot(
        table: str,
        row_field: Optional[str] = None,
        row_col: Optional[str] = None,
        col_field: Optional[str] = None,
        col_col: Optional[str] = None,
        val_field: Optional[str] = None,
        value_field: Optional[str] = None,
        val_col: Optional[str] = None,
        agg: str = "sum",
        metric: Optional[str] = None,
        db_path: str = "mcn_data.db"
    ) -> Dict[str, Any]:
        """
        Generate a 2D cross-tabulation matrix / pivot table from any database table.
        """
        row_field = row_field or row_col or "row"
        col_field = col_field or col_col or "column"
        val_field = value_field or val_field or val_col or "amount"
        agg_op = agg or metric or "sum"
        try:
            conn = _connect(db_path)
            cursor = conn.cursor()

            # 1. Distinct column values
            cursor.execute(f"SELECT DISTINCT {col_field} AS val FROM {table} WHERE {col_field} IS NOT NULL ORDER BY val ASC")
            col_vals = [str(r["val"]) for r in cursor.fetchall()]

            # 2. Distinct row values
            cursor.execute(f"SELECT DISTINCT {row_field} AS val FROM {table} WHERE {row_field} IS NOT NULL ORDER BY val ASC")
            row_vals = [str(r["val"]) for r in cursor.fetchall()]

            # 3. Aggregated values
            agg_fn = agg_op.upper()
            cursor.execute(f"SELECT {row_field} AS r, {col_field} AS c, {agg_fn}({val_field}) AS v FROM {table} GROUP BY {row_field}, {col_field}")
            data_map = {(str(r["r"]), str(r["c"])): r["v"] for r in cursor.fetchall()}

            matrix = []
            for rv in row_vals:
                row_dict = {row_field: rv}
                row_total = 0
                for cv in col_vals:
                    val = data_map.get((rv, cv), 0)
                    row_dict[cv] = val
                    if isinstance(val, (int, float)):
                        row_total += val
                row_dict["Total"] = round(row_total, 2)
                matrix.append(row_dict)

            conn.close()
            return {
                "success": True,
                "table": table,
                "row_field": row_field,
                "col_field": col_field,
                "columns": [row_field] + col_vals + ["Total"],
                "rows": matrix
            }
        except Exception as e:
            return {"success": False, "table": table, "error": str(e), "rows": [], "columns": []}

    def chart_data(
        table: str,
        x_col: str,
        y_cols: Any,
        chart_type: str = "bar",
        filter: Optional[str] = None,
        limit: int = 20,
        db_path: str = "mcn_data.db"
    ) -> Dict[str, Any]:
        """
        Prepare chart-ready JSON dataset for frontend UI components.
        """
        try:
            conn = _connect(db_path)
            cursor = conn.cursor()

            y_list = y_cols if isinstance(y_cols, list) else [c.strip() for c in str(y_cols).split(",")]
            where_clause = f" WHERE {filter}" if filter else ""
            limit_clause = f" LIMIT {int(limit)}"

            select_cols = f"{x_col}, " + ", ".join(y_list)
            cursor.execute(f"SELECT {select_cols} FROM {table}{where_clause}{limit_clause}")
            rows = cursor.fetchall()

            labels = [str(r[x_col]) for r in rows]
            datasets = []
            for y in y_list:
                datasets.append({
                    "label": y.replace("_", " ").title(),
                    "data": [r[y] for r in rows]
                })

            conn.close()
            return {
                "success": True,
                "type": chart_type,
                "labels": labels,
                "datasets": datasets
            }
        except Exception as e:
            return {"success": False, "type": chart_type, "error": str(e), "labels": [], "datasets": []}

    def export_report(
        report_data: Any,
        format: str = "markdown",
        file_path: Optional[str] = None
    ) -> str:
        """
        Export analytical report data to Markdown, CSV, JSON, or executive HTML.
        """
        rows = []
        columns = []

        if isinstance(report_data, dict):
            rows = report_data.get("rows", [])
            columns = report_data.get("columns", [])
            if not columns and rows:
                columns = list(rows[0].keys())
        elif isinstance(report_data, list):
            rows = report_data
            if rows and isinstance(rows[0], dict):
                columns = list(rows[0].keys())

        fmt = format.lower().strip()
        output_str = ""

        if fmt == "markdown" or fmt == "md":
            if not rows or not columns:
                output_str = "_No report records available._"
            else:
                header = "| " + " | ".join(str(c).replace("_", " ").title() for c in columns) + " |"
                sep = "| " + " | ".join("---" for _ in columns) + " |"
                body = "\n".join(
                    "| " + " | ".join(str(r.get(c, "-")) for c in columns) + " |"
                    for r in rows
                )
                output_str = f"{header}\n{sep}\n{body}"

        elif fmt == "csv":
            import io
            import csv
            buf = io.StringIO()
            if rows and columns:
                writer = csv.DictWriter(buf, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            output_str = buf.getvalue()

        elif fmt == "json":
            output_str = json.dumps(report_data, indent=2, default=str)

        elif fmt == "html":
            rows_html_list = []
            for r in rows:
                cells = "".join(f'<td style="padding:8px 12px;border-bottom:1px solid #1e293b;">{r.get(c, "-")}</td>' for c in columns)
                rows_html_list.append(f"<tr>{cells}</tr>")
            table_rows = "".join(rows_html_list)

            headers_list = []
            for c in columns:
                col_title = str(c).replace("_", " ").title()
                headers_list.append(f'<th style="padding:10px 12px;background:#0f172a;color:#38bdf8;text-align:left;border-bottom:2px solid #38bdf8;">{col_title}</th>')
            table_headers = "".join(headers_list)

            output_str = f"""<div style="font-family:system-ui,sans-serif;background:#0b1120;color:#f8fafc;padding:20px;border-radius:12px;border:1px solid #1e293b;">
  <h2 style="color:#38bdf8;margin-top:0;">MCN Analytics Report</h2>
  <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
    <thead><tr>{table_headers}</tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>"""
        else:
            output_str = str(report_data)

        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(output_str)

        return output_str

    return {
        "report": report,
        "generate_report": report,
        "kpi": kpi,
        "kpi_summary": kpi,
        "trend": trend,
        "trend_analysis": trend,
        "distribution": distribution,
        "distribution_analysis": distribution,
        "pivot": pivot,
        "pivot_table": pivot,
        "chart_data": chart_data,
        "export_report": export_report,
    }


def create_reports_package():
    """Alias for create_analytics_package."""
    return create_analytics_package()
