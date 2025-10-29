"""
MCN Code Generation System
Generate client SDKs, API wrappers, and integration code
"""

import os
import json
from typing import Dict, List


class MCNCodeGenerator:
    """Generate code for various languages and frameworks"""
    
    def __init__(self):
        self.templates = {}
        self._init_templates()
    
    def _init_templates(self):
        """Initialize code templates"""
        self.templates = {
            "python": {
                "client": '''"""
MCN Python Client SDK
Auto-generated client for MCN APIs
"""

import requests
import json
from typing import Dict, Any, Optional


class MCNClient:
    def __init__(self, base_url: str = "http://localhost:8080", api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
    
    def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, json=data)
        response.raise_for_status()
        return response.json()
    
    # ML Methods
    def train_model(self, model_type: str, dataset_name: str, target_column: str, **kwargs) -> Dict:
        return self._request("POST", "/api/ml/train", {
            "model_type": model_type,
            "dataset_name": dataset_name,
            "target_column": target_column,
            **kwargs
        })
    
    def predict(self, model_id: str, input_data: Dict) -> Dict:
        return self._request("POST", "/api/ml/predict", {
            "model_id": model_id,
            "input_data": input_data
        })
    
    # AI Methods
    def ai_chat(self, prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 150) -> Dict:
        return self._request("POST", "/api/ai/chat", {
            "prompt": prompt,
            "model": model,
            "max_tokens": max_tokens
        })
    
    # Database Methods
    def query(self, sql: str, params: List = None) -> Dict:
        return self._request("POST", "/api/db/query", {
            "sql": sql,
            "params": params or []
        })
''',
                "requirements": "requests>=2.28.0\\n"
            },
            "javascript": {
                "client": '''/**
 * MCN JavaScript Client SDK
 * Auto-generated client for MCN APIs
 */

class MCNClient {
    constructor(baseUrl = 'http://localhost:8080', apiKey = null) {
        this.baseUrl = baseUrl.replace(/\\/$/, '');
        this.apiKey = apiKey;
    }

    async _request(method, endpoint, data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (this.apiKey) {
            options.headers['Authorization'] = `Bearer ${this.apiKey}`;
        }

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    // ML Methods
    async trainModel(modelType, datasetName, targetColumn, options = {}) {
        return this._request('POST', '/api/ml/train', {
            model_type: modelType,
            dataset_name: datasetName,
            target_column: targetColumn,
            ...options
        });
    }

    async predict(modelId, inputData) {
        return this._request('POST', '/api/ml/predict', {
            model_id: modelId,
            input_data: inputData
        });
    }

    // AI Methods
    async aiChat(prompt, model = 'gpt-3.5-turbo', maxTokens = 150) {
        return this._request('POST', '/api/ai/chat', {
            prompt,
            model,
            max_tokens: maxTokens
        });
    }

    // Database Methods
    async query(sql, params = []) {
        return this._request('POST', '/api/db/query', {
            sql,
            params
        });
    }
}

module.exports = MCNClient;
''',
                "package": '''{
  "name": "mcn-client",
  "version": "1.0.0",
  "description": "MCN JavaScript Client SDK",
  "main": "mcn-client.js",
  "dependencies": {
    "node-fetch": "^3.0.0"
  }
}'''
            }
        }
    
    def generate_python_client(self, output_dir: str = "python_client") -> Dict:
        """Generate Python client SDK"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate client code
        client_file = os.path.join(output_dir, "mcn_client.py")
        with open(client_file, 'w') as f:
            f.write(self.templates["python"]["client"])
        
        # Generate requirements
        req_file = os.path.join(output_dir, "requirements.txt")
        with open(req_file, 'w') as f:
            f.write(self.templates["python"]["requirements"])
        
        # Generate setup.py
        setup_file = os.path.join(output_dir, "setup.py")
        with open(setup_file, 'w') as f:
            f.write('''from setuptools import setup

setup(
    name="mcn-client",
    version="1.0.0",
    description="MCN Python Client SDK",
    py_modules=["mcn_client"],
    install_requires=["requests>=2.28.0"],
    python_requires=">=3.7"
)''')
        
        return {
            "success": True,
            "client_file": client_file,
            "requirements_file": req_file,
            "setup_file": setup_file
        }
    
    def generate_javascript_client(self, output_dir: str = "javascript_client") -> Dict:
        """Generate JavaScript client SDK"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate client code
        client_file = os.path.join(output_dir, "mcn-client.js")
        with open(client_file, 'w') as f:
            f.write(self.templates["javascript"]["client"])
        
        # Generate package.json
        package_file = os.path.join(output_dir, "package.json")
        with open(package_file, 'w') as f:
            f.write(self.templates["javascript"]["package"])
        
        return {
            "success": True,
            "client_file": client_file,
            "package_file": package_file
        }
    
    def generate_docker_compose(self, output_dir: str = "docker") -> Dict:
        """Generate Docker Compose for MCN stack"""
        os.makedirs(output_dir, exist_ok=True)
        
        compose_content = '''version: '3.8'

services:
  mcn-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - MCN_ENV=production
      - DATABASE_URL=postgresql://mcn:password@postgres:5432/mcn_db
    depends_on:
      - postgres
      - redis
    volumes:
      - ./mcn_data:/app/data

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: mcn_db
      POSTGRES_USER: mcn
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  swagger-ui:
    image: swaggerapi/swagger-ui
    ports:
      - "8081:8080"
    environment:
      SWAGGER_JSON: /api_docs/openapi.json
    volumes:
      - ./api_docs:/api_docs

volumes:
  postgres_data:
  redis_data:
'''
        
        compose_file = os.path.join(output_dir, "docker-compose.yml")
        with open(compose_file, 'w') as f:
            f.write(compose_content)
        
        # Generate Dockerfile
        dockerfile_content = '''FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "run_mcn.py", "serve", "--host", "0.0.0.0", "--port", "8080"]
'''
        
        dockerfile = os.path.join(output_dir, "Dockerfile")
        with open(dockerfile, 'w') as f:
            f.write(dockerfile_content)
        
        return {
            "success": True,
            "compose_file": compose_file,
            "dockerfile": dockerfile
        }


def generate_all_clients(output_dir: str = "generated_clients") -> Dict:
    """Generate all client SDKs and deployment files"""
    generator = MCNCodeGenerator()
    
    results = {}
    
    # Generate Python client
    python_dir = os.path.join(output_dir, "python")
    results["python"] = generator.generate_python_client(python_dir)
    
    # Generate JavaScript client
    js_dir = os.path.join(output_dir, "javascript")
    results["javascript"] = generator.generate_javascript_client(js_dir)
    
    # Generate Docker setup
    docker_dir = os.path.join(output_dir, "docker")
    results["docker"] = generator.generate_docker_compose(docker_dir)
    
    return {
        "success": True,
        "results": results,
        "output_dir": output_dir
    }