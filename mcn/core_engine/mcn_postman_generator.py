"""
MCN Postman Collection Generator
Auto-generates Postman collections for MCN API endpoints
"""

import json
import time
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class MCNEndpoint:
    """MCN API endpoint definition"""
    path: str
    method: str
    name: str
    description: str
    parameters: List[Dict] = None
    body_schema: Dict = None
    response_example: Dict = None


class MCNPostmanGenerator:
    """Generate Postman collections for MCN APIs"""
    
    def __init__(self):
        self.endpoints = []
        self.collection_info = {
            "name": "MCN API Collection",
            "description": "Auto-generated Postman collection for MCN APIs",
            "version": "1.0.0"
        }
    
    def add_endpoint(self, endpoint: MCNEndpoint):
        """Add endpoint to collection"""
        self.endpoints.append(endpoint)
    
    def auto_discover_endpoints(self, mcn_server_instance=None):
        """Auto-discover endpoints from MCN server"""
        # ML System endpoints
        self.add_endpoint(MCNEndpoint(
            path="/api/ml/train",
            method="POST",
            name="Train ML Model",
            description="Train a machine learning model",
            body_schema={
                "model_type": "random_forest",
                "dataset_name": "customers",
                "target_column": "churn",
                "n_estimators": 100
            },
            response_example={
                "success": True,
                "model_id": "rf_customers_123456",
                "metrics": {"accuracy": 0.85}
            }
        ))
        
        self.add_endpoint(MCNEndpoint(
            path="/api/ml/predict",
            method="POST",
            name="Make Prediction",
            description="Make prediction with trained model",
            body_schema={
                "model_id": "rf_customers_123456",
                "input_data": {"age": 30, "income": 50000}
            },
            response_example={
                "success": True,
                "prediction": 0.23,
                "probability": 0.77
            }
        ))
        
        # Database endpoints
        self.add_endpoint(MCNEndpoint(
            path="/api/db/query",
            method="POST",
            name="Execute Database Query",
            description="Execute SQL query on database",
            body_schema={
                "sql": "SELECT * FROM users LIMIT 10",
                "params": []
            },
            response_example={
                "success": True,
                "data": [{"id": 1, "name": "John"}],
                "rows_affected": 1
            }
        ))
        
        # AI endpoints
        self.add_endpoint(MCNEndpoint(
            path="/api/ai/chat",
            method="POST",
            name="AI Chat",
            description="Chat with AI model",
            body_schema={
                "prompt": "Analyze this data",
                "model": "gpt-3.5-turbo",
                "max_tokens": 150
            },
            response_example={
                "response": "Based on the data analysis...",
                "model": "gpt-3.5-turbo",
                "tokens_used": 45
            }
        ))
        
        # IoT endpoints
        self.add_endpoint(MCNEndpoint(
            path="/api/iot/devices",
            method="GET",
            name="List IoT Devices",
            description="Get list of registered IoT devices",
            response_example={
                "devices": [
                    {"id": "temp_01", "type": "temperature_sensor", "status": "active"}
                ]
            }
        ))
        
        self.add_endpoint(MCNEndpoint(
            path="/api/iot/device/{device_id}/read",
            method="GET",
            name="Read IoT Device",
            description="Read data from IoT device",
            parameters=[{"name": "device_id", "in": "path", "required": True}],
            response_example={
                "success": True,
                "value": 23.5,
                "unit": "°C",
                "timestamp": 1640995200
            }
        ))
        
        # Event endpoints
        self.add_endpoint(MCNEndpoint(
            path="/api/events/trigger",
            method="POST",
            name="Trigger Event",
            description="Trigger an event in the system",
            body_schema={
                "event_name": "user_login",
                "data": {"user_id": 123, "timestamp": 1640995200}
            },
            response_example={
                "success": True,
                "message": "Event triggered successfully"
            }
        ))
        
        # Agent endpoints
        self.add_endpoint(MCNEndpoint(
            path="/api/agents/create",
            method="POST",
            name="Create Agent",
            description="Create autonomous agent",
            body_schema={
                "name": "data_analyst",
                "prompt": "You are a data analysis expert",
                "model": "gpt-4",
                "tools": ["query", "ai"]
            },
            response_example={
                "success": True,
                "agent_id": "agent_123",
                "status": "created"
            }
        ))
        
        # Pipeline endpoints
        self.add_endpoint(MCNEndpoint(
            path="/api/pipelines/run",
            method="POST",
            name="Run Data Pipeline",
            description="Execute data processing pipeline",
            body_schema={
                "pipeline_name": "customer_analysis",
                "input_data": "customer_data.csv"
            },
            response_example={
                "success": True,
                "pipeline_id": "pipe_123",
                "status": "running"
            }
        ))
    
    def generate_collection(self, output_file: str = None) -> Dict:
        """Generate Postman collection JSON"""
        collection = {
            "info": {
                "name": self.collection_info["name"],
                "description": self.collection_info["description"],
                "version": self.collection_info["version"],
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": [],
            "variable": [
                {
                    "key": "base_url",
                    "value": "http://localhost:8080",
                    "type": "string"
                },
                {
                    "key": "api_key",
                    "value": "your_api_key_here",
                    "type": "string"
                }
            ]
        }
        
        # Group endpoints by category
        categories = {}
        for endpoint in self.endpoints:
            category = endpoint.path.split('/')[2] if len(endpoint.path.split('/')) > 2 else 'general'
            if category not in categories:
                categories[category] = []
            categories[category].append(endpoint)
        
        # Create folders for each category
        for category, endpoints in categories.items():
            folder = {
                "name": category.upper(),
                "item": []
            }
            
            for endpoint in endpoints:
                request_item = self._create_request_item(endpoint)
                folder["item"].append(request_item)
            
            collection["item"].append(folder)
        
        # Save to file if specified
        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(collection, f, indent=2)
        
        return collection
    
    def _create_request_item(self, endpoint: MCNEndpoint) -> Dict:
        """Create Postman request item from endpoint"""
        # Build URL with path parameters
        url_path = endpoint.path
        if endpoint.parameters:
            for param in endpoint.parameters:
                if param.get('in') == 'path':
                    url_path = url_path.replace(f"{{{param['name']}}}", f"{{{{param['name']}}}}")
        
        request_item = {
            "name": endpoint.name,
            "request": {
                "method": endpoint.method,
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                        "type": "text"
                    },
                    {
                        "key": "Authorization",
                        "value": "Bearer {{api_key}}",
                        "type": "text"
                    }
                ],
                "url": {
                    "raw": "{{base_url}}" + url_path,
                    "host": ["{{base_url}}"],
                    "path": url_path.strip('/').split('/')
                },
                "description": endpoint.description
            },
            "response": []
        }
        
        # Add body for POST/PUT requests
        if endpoint.method in ['POST', 'PUT'] and endpoint.body_schema:
            request_item["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(endpoint.body_schema, indent=2),
                "options": {
                    "raw": {
                        "language": "json"
                    }
                }
            }
        
        # Add query parameters
        if endpoint.parameters:
            query_params = [p for p in endpoint.parameters if p.get('in') == 'query']
            if query_params:
                request_item["request"]["url"]["query"] = [
                    {
                        "key": param["name"],
                        "value": param.get("example", ""),
                        "description": param.get("description", "")
                    }
                    for param in query_params
                ]
        
        # Add example response
        if endpoint.response_example:
            request_item["response"].append({
                "name": "Success Response",
                "originalRequest": request_item["request"],
                "status": "OK",
                "code": 200,
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json"
                    }
                ],
                "body": json.dumps(endpoint.response_example, indent=2)
            })
        
        return request_item
    
    def generate_environment(self, env_name: str = "MCN Development") -> Dict:
        """Generate Postman environment file"""
        environment = {
            "name": env_name,
            "values": [
                {
                    "key": "base_url",
                    "value": "http://localhost:8080",
                    "enabled": True
                },
                {
                    "key": "api_key",
                    "value": "",
                    "enabled": True
                },
                {
                    "key": "model_id",
                    "value": "",
                    "enabled": True
                },
                {
                    "key": "dataset_name",
                    "value": "sample_data",
                    "enabled": True
                }
            ]
        }
        return environment
    
    def export_postman_files(self, output_dir: str = "postman_exports"):
        """Export both collection and environment files"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Auto-discover endpoints
        self.auto_discover_endpoints()
        
        # Generate collection
        collection_file = os.path.join(output_dir, "MCN_API_Collection.json")
        collection = self.generate_collection(collection_file)
        
        # Generate environment
        environment = self.generate_environment()
        env_file = os.path.join(output_dir, "MCN_Development_Environment.json")
        with open(env_file, 'w') as f:
            json.dump(environment, f, indent=2)
        
        # Generate README
        readme_content = self._generate_readme()
        readme_file = os.path.join(output_dir, "README.md")
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        return {
            "collection_file": collection_file,
            "environment_file": env_file,
            "readme_file": readme_file,
            "endpoints_count": len(self.endpoints)
        }
    
    def _generate_readme(self) -> str:
        """Generate README for Postman exports"""
        return f"""# MCN API Postman Collection

## Overview
This collection contains {len(self.endpoints)} API endpoints for the MCN system, automatically generated for easy testing and development.

## Setup Instructions

1. **Import Collection**
   - Open Postman
   - Click "Import" button
   - Select `MCN_API_Collection.json`

2. **Import Environment**
   - Click "Import" button
   - Select `MCN_Development_Environment.json`
   - Set as active environment

3. **Configure Variables**
   - Update `base_url` if your MCN server runs on different port
   - Set `api_key` if authentication is required

## Available Endpoints

### ML (Machine Learning)
- Train ML Model
- Make Prediction

### Database
- Execute Database Query

### AI
- AI Chat

### IoT
- List IoT Devices
- Read IoT Device

### Events
- Trigger Event

### Agents
- Create Agent

### Pipelines
- Run Data Pipeline

## Usage Tips

1. **Variables**: Use {{{{variable_name}}}} syntax for dynamic values
2. **Authentication**: API key is automatically included in headers
3. **Examples**: Each request includes example request/response data
4. **Testing**: Use Postman's test scripts for automated testing

## Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""


def generate_postman_collection(output_dir: str = "postman_exports") -> Dict:
    """Convenience function to generate Postman collection"""
    generator = MCNPostmanGenerator()
    return generator.export_postman_files(output_dir)


# Integration with MCN server
def auto_generate_on_server_start(server_instance=None):
    """Auto-generate Postman collection when MCN server starts"""
    try:
        result = generate_postman_collection()
        print(f"✅ Postman collection generated: {result['endpoints_count']} endpoints")
        print(f"📁 Files saved to: postman_exports/")
        return result
    except Exception as e:
        print(f"❌ Failed to generate Postman collection: {e}")
        return None