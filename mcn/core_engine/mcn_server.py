"""
MCN Server Runtime - Phase 3 Feature
Allows MCN scripts to act as backend microservices
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import os
import json
from typing import Dict, Any
from .mcn_interpreter import MCNInterpreter


class MCNServer:
    def __init__(self):
        self.app = FastAPI(title="MCN Server Runtime", version="2.0")
        self.interpreters = {}
        self.routes = {}

    def load_script(self, script_path: str, endpoint: str = None):
        """Load MCN script as API endpoint"""
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")

        script_name = os.path.basename(script_path).replace(".mcn", "")
        endpoint = endpoint or f"/{script_name}"

        # Create interpreter for this script
        interpreter = MCNInterpreter()

        # Read and parse script
        with open(script_path, "r") as f:
            script_content = f.read()

        self.interpreters[endpoint] = {
            "interpreter": interpreter,
            "script": script_content,
            "path": script_path,
        }

        # Create FastAPI route
        @self.app.post(endpoint)
        async def execute_script(data: Dict[str, Any] = None):
            try:
                # Set request data as variables
                if data:
                    for key, value in data.items():
                        interpreter.variables[key] = value

                # Execute script
                result = interpreter.execute(script_content)

                return JSONResponse(
                    {
                        "success": True,
                        "result": result,
                        "variables": interpreter.variables,
                    }
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        self.routes[endpoint] = script_path
        return endpoint

    def serve(self, host: str = "127.0.0.1", port: int = 8000):
        """Start the MCN server"""
        print(f"MCN Server starting on http://{host}:{port}")
        print("Loaded endpoints:")
        for endpoint, script_path in self.routes.items():
            print(f"  POST {endpoint} -> {script_path}")

        uvicorn.run(self.app, host=host, port=port)


def serve_script(script_path: str, host: str = "127.0.0.1", port: int = 8000):
    """Serve a single MCN script as API"""
    server = MCNServer()
    server.load_script(script_path)
    server.serve(host, port)


def serve_directory(directory: str, host: str = "127.0.0.1", port: int = 8000):
    """Serve all MCN scripts in directory as APIs"""
    server = MCNServer()

    for filename in os.listdir(directory):
        if filename.endswith(".mcn"):
            script_path = os.path.join(directory, filename)
            server.load_script(script_path)

    server.serve(host, port)
