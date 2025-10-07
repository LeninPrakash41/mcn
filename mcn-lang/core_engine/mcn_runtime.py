import requests
import sqlite3
import psycopg2
import pymongo
import json
import os
import smtplib
import hashlib
import base64
from typing import Any, Dict, List, Optional
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

class MCNRuntime:
    def __init__(self):
        self.db_connection = None
        self.db_type = 'sqlite'
        self.ai_providers = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'anthropic': os.getenv('ANTHROPIC_API_KEY'),
            'google': os.getenv('GOOGLE_AI_KEY')
        }
        self.workflows = {}
        self.email_config = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'email': os.getenv('EMAIL_USER'),
            'password': os.getenv('EMAIL_PASSWORD')
        }
        self._setup_logging()

    def log(self, message: Any) -> None:
        """Print message to console with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def trigger(self, endpoint: str, payload: Dict = None, method: str = "POST") -> Dict:
        """Trigger API/webhook call"""
        try:
            headers = {'Content-Type': 'application/json'}

            if method.upper() == "GET":
                response = requests.get(endpoint, params=payload, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(endpoint, json=payload, headers=headers, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(endpoint, headers=headers, timeout=30)
            else:
                raise Exception(f"Unsupported HTTP method: {method}")

            return {
                "status_code": response.status_code,
                "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                "success": 200 <= response.status_code < 300
            }
        except requests.exceptions.RequestException as e:
            return {
                "status_code": 0,
                "data": str(e),
                "success": False
            }

    def query(self, sql: str, params: tuple = None) -> List[Dict]:
        """Enhanced database query with multi-DB support"""
        if not self.db_connection:
            self._init_database()

        try:
            if self.db_type == 'sqlite':
                return self._query_sqlite(sql, params)
            elif self.db_type == 'postgresql':
                return self._query_postgresql(sql, params)
            elif self.db_type == 'mongodb':
                return self._query_mongodb(sql, params)
            else:
                raise Exception(f"Unsupported database type: {self.db_type}")
        except Exception as e:
            raise Exception(f"Database error: {str(e)}")

    def _query_sqlite(self, sql: str, params: tuple = None) -> List[Dict]:
        """SQLite query execution"""
        cursor = self.db_connection.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        if sql.strip().upper().startswith('SELECT'):
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        else:
            self.db_connection.commit()
            return [{"affected_rows": cursor.rowcount}]

    def _query_postgresql(self, sql: str, params: tuple = None) -> List[Dict]:
        """PostgreSQL query execution"""
        cursor = self.db_connection.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        if sql.strip().upper().startswith('SELECT'):
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        else:
            self.db_connection.commit()
            return [{"affected_rows": cursor.rowcount}]

    def _query_mongodb(self, query_str: str, params: tuple = None) -> List[Dict]:
        """MongoDB query execution (simplified)"""
        # Basic MongoDB operations
        try:
            query_data = json.loads(query_str)
            collection_name = query_data.get('collection')
            operation = query_data.get('operation', 'find')
            filter_data = query_data.get('filter', {})

            collection = self.db_connection[collection_name]

            if operation == 'find':
                results = list(collection.find(filter_data))
                return [{**doc, '_id': str(doc['_id'])} for doc in results]
            elif operation == 'insert':
                result = collection.insert_one(query_data.get('document', {}))
                return [{"inserted_id": str(result.inserted_id)}]
            elif operation == 'update':
                result = collection.update_many(filter_data, query_data.get('update', {}))
                return [{"modified_count": result.modified_count}]
            elif operation == 'delete':
                result = collection.delete_many(filter_data)
                return [{"deleted_count": result.deleted_count}]
        except Exception as e:
            raise Exception(f"MongoDB error: {str(e)}")

    def workflow(self, name: str, params: Dict = None) -> Any:
        """Execute registered workflow"""
        if name not in self.workflows:
            raise Exception(f"Workflow '{name}' not found")

        workflow_func = self.workflows[name]
        return workflow_func(params or {})

    def ai(self, prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 150, provider: str = "openai") -> str:
        """Enhanced AI with multiple provider support"""
        if provider == "openai":
            return self._call_openai(prompt, model, max_tokens)
        elif provider == "anthropic":
            return self._call_anthropic(prompt, model, max_tokens)
        elif provider == "google":
            return self._call_google(prompt, model, max_tokens)
        else:
            return f"AI Mock Response for {provider}: {prompt[:50]}..."

    def _call_openai(self, prompt: str, model: str, max_tokens: int) -> str:
        """OpenAI API integration"""
        api_key = self.ai_providers.get('openai')
        if not api_key:
            return f"OpenAI Mock: {prompt[:50]}..."

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7
            }

            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                return f"OpenAI Error: {response.status_code}"

        except Exception as e:
            return f"OpenAI Error: {str(e)}"

    def _call_anthropic(self, prompt: str, model: str, max_tokens: int) -> str:
        """Anthropic Claude API integration"""
        api_key = self.ai_providers.get('anthropic')
        if not api_key:
            return f"Anthropic Mock: {prompt[:50]}..."

        try:
            headers = {
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }

            payload = {
                "model": model or "claude-3-sonnet-20240229",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }

            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data['content'][0]['text']
            else:
                return f"Anthropic Error: {response.status_code}"

        except Exception as e:
            return f"Anthropic Error: {str(e)}"

    def _call_google(self, prompt: str, model: str, max_tokens: int) -> str:
        """Google AI API integration"""
        api_key = self.ai_providers.get('google')
        if not api_key:
            return f"Google AI Mock: {prompt[:50]}..."

        try:
            headers = {
                'Content-Type': 'application/json'
            }

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.7
                }
            }

            model_name = model or "gemini-pro"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                return f"Google AI Error: {response.status_code}"

        except Exception as e:
            return f"Google AI Error: {str(e)}"

    def _init_database(self, db_path: str = "mcn_data.db"):
        """Initialize SQLite database connection"""
        self.db_connection = sqlite3.connect(db_path)

        # Create sample tables for demo
        cursor = self.db_connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                age INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                prompt TEXT,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT,
                temperature REAL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.db_connection.commit()

    def register_workflow(self, name: str, func):
        """Register a custom workflow function"""
        self.workflows[name] = func

    def connect_database(self, db_path: str):
        """Connect to a specific database"""
        if self.db_connection:
            self.db_connection.close()
        self.db_connection = sqlite3.connect(db_path)

    def close_database(self):
        """Close database connection"""
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None

    def send_email(self, to: str, subject: str, body: str, html: bool = False) -> Dict:
        """Send email via SMTP"""
        if not self.email_config['email'] or not self.email_config['password']:
            return {"success": False, "error": "Email credentials not configured"}

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['email']
            msg['To'] = to
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html' if html else 'plain'))

            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email'], self.email_config['password'])
            server.send_message(msg)
            server.quit()

            return {"success": True, "message": f"Email sent to {to}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def hash_data(self, data: str, algorithm: str = "sha256") -> str:
        """Hash data using specified algorithm"""
        if algorithm == "md5":
            return hashlib.md5(data.encode()).hexdigest()
        elif algorithm == "sha1":
            return hashlib.sha1(data.encode()).hexdigest()
        elif algorithm == "sha256":
            return hashlib.sha256(data.encode()).hexdigest()
        else:
            raise Exception(f"Unsupported hash algorithm: {algorithm}")

    def encode_base64(self, data: str) -> str:
        """Encode string to base64"""
        return base64.b64encode(data.encode()).decode()

    def decode_base64(self, data: str) -> str:
        """Decode base64 string"""
        return base64.b64decode(data.encode()).decode()

    def read_file(self, file_path: str) -> str:
        """Read file content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"File read error: {str(e)}")

    def write_file(self, file_path: str, content: str, append: bool = False) -> Dict:
        """Write content to file"""
        try:
            mode = 'a' if append else 'w'
            with open(file_path, mode, encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "message": f"File {'appended' if append else 'written'}: {file_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def now(self) -> str:
        """Get current timestamp"""
        return datetime.now().isoformat()

    def format_date(self, date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format date string"""
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime(format_str)
        except Exception as e:
            return f"Date format error: {str(e)}"

    def connect_postgresql(self, host: str, database: str, user: str, password: str, port: int = 5432):
        """Connect to PostgreSQL database"""
        try:
            self.db_connection = psycopg2.connect(
                host=host,
                database=database,
                user=user,
                password=password,
                port=port
            )
            self.db_type = 'postgresql'
            return {"success": True, "message": "Connected to PostgreSQL"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def connect_mongodb(self, connection_string: str, database_name: str):
        """Connect to MongoDB database"""
        try:
            client = pymongo.MongoClient(connection_string)
            self.db_connection = client[database_name]
            self.db_type = 'mongodb'
            return {"success": True, "message": "Connected to MongoDB"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _setup_logging(self):
        """Setup enhanced logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('mcn_runtime.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
