"""
MCN OpenAPI/Swagger Documentation Generator
Auto-generates OpenAPI 3.0 specifications for MCN APIs
"""

import json
import time
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class SwaggerEndpoint:
    path: str
    method: str
    summary: str
    description: str
    parameters: List[Dict] = None
    request_body: Dict = None
    responses: Dict = None
    tags: List[str] = None


class MCNSwaggerGenerator:
    """Generate OpenAPI 3.0 documentation for MCN APIs"""
    
    def __init__(self):
        self.endpoints = []
        self.info = {
            "title": "MCN API Documentation",
            "description": "Auto-generated API documentation for MCN services",
            "version": "3.0.0"
        }
    
    def auto_discover_endpoints(self):
        """Auto-discover MCN API endpoints"""
        # ML endpoints
        self.endpoints.extend([
            SwaggerEndpoint(
                path="/api/ml/train",
                method="post",
                summary="Train ML Model",
                description="Train a machine learning model with specified parameters",
                tags=["Machine Learning"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "model_type": {"type": "string", "enum": ["linear_regression", "random_forest", "xgboost"]},
                                    "dataset_name": {"type": "string"},
                                    "target_column": {"type": "string"},
                                    "n_estimators": {"type": "integer", "default": 100}
                                },
                                "required": ["model_type", "dataset_name", "target_column"]
                            }
                        }
                    }
                },
                responses={
                    "200": {
                        "description": "Model trained successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "model_id": {"type": "string"},
                                        "metrics": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            ),
            SwaggerEndpoint(
                path="/api/ml/predict",
                method="post",
                summary="Make Prediction",
                description="Make prediction using trained model",
                tags=["Machine Learning"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "model_id": {"type": "string"},
                                    "input_data": {"type": "object"}
                                },
                                "required": ["model_id", "input_data"]
                            }
                        }
                    }
                }
            )
        ])
        
        # AI endpoints
        self.endpoints.append(
            SwaggerEndpoint(
                path="/api/ai/chat",
                method="post",
                summary="AI Chat",
                description="Chat with AI models",
                tags=["Artificial Intelligence"],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "prompt": {"type": "string"},
                                    "model": {"type": "string", "default": "gpt-3.5-turbo"},
                                    "max_tokens": {"type": "integer", "default": 150}
                                },
                                "required": ["prompt"]
                            }
                        }
                    }
                }
            )
        )
    
    def generate_openapi_spec(self) -> Dict:
        """Generate OpenAPI 3.0 specification"""
        spec = {
            "openapi": "3.0.0",
            "info": self.info,
            "servers": [
                {"url": "http://localhost:8080", "description": "Development server"}
            ],
            "paths": {},
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer"
                    }
                }
            },
            "security": [{"bearerAuth": []}]
        }
        
        for endpoint in self.endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}
            
            operation = {
                "summary": endpoint.summary,
                "description": endpoint.description,
                "tags": endpoint.tags or ["General"]
            }
            
            if endpoint.parameters:
                operation["parameters"] = endpoint.parameters
            
            if endpoint.request_body:
                operation["requestBody"] = endpoint.request_body
            
            if endpoint.responses:
                operation["responses"] = endpoint.responses
            else:
                operation["responses"] = {
                    "200": {"description": "Success"},
                    "400": {"description": "Bad Request"},
                    "500": {"description": "Internal Server Error"}
                }
            
            spec["paths"][endpoint.path][endpoint.method] = operation
        
        return spec
    
    def generate_html_docs(self, output_file: str = "api_docs.html"):
        """Generate HTML documentation using Swagger UI"""
        spec = self.generate_openapi_spec()
        
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>MCN API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@3.25.0/swagger-ui.css" />
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@3.25.0/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({{
            url: 'data:application/json;base64,' + btoa(JSON.stringify({json.dumps(spec)})),
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.presets.standalone
            ]
        }});
    </script>
</body>
</html>"""
        
        with open(output_file, 'w') as f:
            f.write(html_template)
        
        return output_file


def generate_swagger_docs(output_dir: str = "api_docs") -> Dict:
    """Generate OpenAPI documentation"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    generator = MCNSwaggerGenerator()
    generator.auto_discover_endpoints()
    
    # Generate OpenAPI spec
    spec = generator.generate_openapi_spec()
    spec_file = os.path.join(output_dir, "openapi.json")
    with open(spec_file, 'w') as f:
        json.dump(spec, f, indent=2)
    
    # Generate HTML docs
    html_file = os.path.join(output_dir, "index.html")
    generator.generate_html_docs(html_file)
    
    return {
        "success": True,
        "spec_file": spec_file,
        "html_file": html_file,
        "endpoints_count": len(generator.endpoints)
    }