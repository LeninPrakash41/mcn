"""
MCN Project Manager
Handles project structure, scaffolding, and organization
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from .mcn_logger import log_step, log_error
from .mcn_frontend import mcn_frontend


class MCNProjectManager:
    """Manages MCN project structure and scaffolding"""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)

    def create_project_structure(
        self,
        project_name: str,
        include_frontend: bool = True,
        frontend_framework: str = None,
    ) -> Dict[str, Any]:
        """Create complete MCN project structure"""

        log_step(f"Creating MCN project: {project_name}")

        project_dir = self.project_path / project_name
        project_dir.mkdir(exist_ok=True)

        # Core MCN structure
        structure = {
            "mcn": ["scripts/", "config/", "data/", "logs/"],
            "tests": ["unit/", "integration/", "e2e/"],
            "docs": ["api/", "guides/", "examples/"],
            "deployment": ["docker/", "kubernetes/", "terraform/"],
        }

        if include_frontend:
            structure["frontend"] = ["src/", "public/", "assets/"]

        # Create directories
        for main_dir, subdirs in structure.items():
            main_path = project_dir / main_dir
            main_path.mkdir(exist_ok=True)

            for subdir in subdirs:
                (main_path / subdir).mkdir(exist_ok=True)

        # Create essential files
        self._create_essential_files(
            project_dir, project_name, include_frontend, frontend_framework
        )

        log_step(f"Project {project_name} created successfully")

        return {
            "project_path": str(project_dir),
            "structure": structure,
            "frontend_included": include_frontend,
            "frontend_framework": frontend_framework,
        }

    def _create_essential_files(
        self,
        project_dir: Path,
        project_name: str,
        include_frontend: bool,
        frontend_framework: str,
    ):
        """Create essential project files"""

        # MCN main script
        main_mcn = f"""// {project_name} - Main MCN Application
use "db"
use "ai"
use "http"

// Configuration
var config = {{
    "app_name": "{project_name}",
    "version": "1.0.0",
    "database": {{
        "host": "localhost",
        "port": 5432,
        "name": "{project_name}_db"
    }},
    "api": {{
        "port": 8080,
        "cors": true
    }}
}}

// Initialize database
task "init_db" "query" "CREATE TABLE IF NOT EXISTS app_data (id SERIAL PRIMARY KEY, data JSONB)"

// Main application logic
function main() {{
    log("Starting {project_name}...")

    // Your MCN code here
    var result = ai("Welcome to {project_name}! How can I help you today?")

    return {{
        "status": "success",
        "message": result,
        "timestamp": now()
    }}
}}

// Export for API access
export main
"""

        with open(project_dir / "mcn" / "main.mcn", "w") as f:
            f.write(main_mcn)

        # Configuration file
        config = {
            "project": {
                "name": project_name,
                "version": "1.0.0",
                "description": f"MCN application: {project_name}",
            },
            "database": {
                "type": "postgresql",
                "host": "localhost",
                "port": 5432,
                "name": f"{project_name}_db",
            },
            "api": {"port": 8080, "cors": True, "rate_limit": 100},
            "ai": {"provider": "openai", "model": "gpt-4", "max_tokens": 1000},
            "logging": {"level": "INFO", "file": "logs/app.log"},
        }

        with open(project_dir / "mcn" / "config" / "app.json", "w") as f:
            json.dump(config, f, indent=2)

        # Docker configuration
        dockerfile = f"""FROM python:3.9-slim

WORKDIR /app

# Install MCN dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy MCN application
COPY mcn/ ./mcn/
COPY tests/ ./tests/

# Expose API port
EXPOSE 8080

# Run MCN application
CMD ["python", "-m", "mcn.mcn_cli", "mcn/main.mcn", "--serve", "--port", "8080"]
"""

        with open(project_dir / "deployment" / "docker" / "Dockerfile", "w") as f:
            f.write(dockerfile)

        # Requirements file
        requirements = """mcn-lang>=1.0.0
fastapi>=0.68.0
uvicorn>=0.15.0
sqlalchemy>=1.4.0
psycopg2-binary>=2.9.0
openai>=0.27.0
requests>=2.25.0
python-dotenv>=0.19.0
"""

        with open(project_dir / "requirements.txt", "w") as f:
            f.write(requirements)

        # README
        readme = f"""# {project_name}

MCN-powered application with AI, database, and API capabilities.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your application:
   ```bash
   cp mcn/config/app.json.example mcn/config/app.json
   # Edit configuration as needed
   ```

3. Run the application:
   ```bash
   python -m mcn.mcn_cli mcn/main.mcn
   ```

4. Serve as API:
   ```bash
   python -m mcn.mcn_cli mcn/main.mcn --serve --port 8080
   ```

## Project Structure

- `mcn/` - MCN scripts and configuration
- `tests/` - Test files
- `docs/` - Documentation
- `deployment/` - Docker and Kubernetes configs
{"- `frontend/` - Frontend application" if include_frontend else ""}

## Features

- 🤖 AI Integration
- 🗄️ Database Operations
- 🌐 REST API
- 📊 Real-time Processing
- 🔧 Easy Configuration

## API Endpoints

- `POST /main` - Main application endpoint

## Development

Run tests:
```bash
python -m pytest tests/
```

Build Docker image:
```bash
docker build -f deployment/docker/Dockerfile -t {project_name} .
```

## Documentation

See `docs/` directory for detailed guides and API documentation.
"""

        with open(project_dir / "README.md", "w") as f:
            f.write(readme)

        # Create frontend integration if requested
        if include_frontend and frontend_framework:
            self._setup_frontend_integration(
                project_dir, project_name, frontend_framework
            )

    def _setup_frontend_integration(
        self, project_dir: Path, project_name: str, framework: str
    ):
        """Setup frontend integration"""

        log_step(f"Setting up {framework} frontend integration")

        # Sample endpoints for frontend
        endpoints = [
            {"name": "main", "path": "/main", "method": "POST"},
            {"name": "health", "path": "/health", "method": "GET"},
        ]

        # Generate API client
        frontend_dir = project_dir / "frontend"
        mcn_frontend.project_path = frontend_dir

        config = mcn_frontend.create_frontend_config(framework, endpoints)
        examples = mcn_frontend.generate_frontend_examples(framework, endpoints)

        # Create example component
        if "component" in examples:
            ext = (
                "tsx" if framework == "react" else "vue" if framework == "vue" else "ts"
            )
            example_file = frontend_dir / f"MCNExample.{ext}"

            with open(example_file, "w") as f:
                f.write(examples["component"])

        # Frontend README
        frontend_readme = f"""# {project_name} Frontend

{framework.title()} frontend for {project_name} MCN application.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Configure MCN API:
   ```bash
   cp .env.mcn.example .env.local
   # Update MCN_API_URL if needed
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

## MCN Integration

The frontend includes:
- Auto-generated API client (`mcn-api-client.{ext}`)
- Example components (`MCNExample.{ext}`)
- Environment configuration (`.env.mcn`)

## Usage

```javascript
import {{ useMCNApi }} from './mcn-api-client';

const {{ callApi, loading, error }} = useMCNApi();

// Call MCN endpoint
const result = await callApi('main', {{ data: 'example' }});
```
"""

        with open(frontend_dir / "README.md", "w") as f:
            f.write(frontend_readme)

    def validate_project_structure(self, project_path: str = None) -> Dict[str, Any]:
        """Validate MCN project structure"""

        if not project_path:
            project_path = self.project_path
        else:
            project_path = Path(project_path)

        log_step("Validating project structure")

        required_files = [
            "mcn/main.mcn",
            "mcn/config/app.json",
            "requirements.txt",
            "README.md",
        ]

        required_dirs = ["mcn/", "tests/", "docs/", "logs/"]

        validation_result = {
            "valid": True,
            "missing_files": [],
            "missing_dirs": [],
            "recommendations": [],
        }

        # Check required files
        for file_path in required_files:
            if not (project_path / file_path).exists():
                validation_result["missing_files"].append(file_path)
                validation_result["valid"] = False

        # Check required directories
        for dir_path in required_dirs:
            if not (project_path / dir_path).exists():
                validation_result["missing_dirs"].append(dir_path)
                validation_result["valid"] = False

        # Generate recommendations
        if validation_result["missing_files"]:
            validation_result["recommendations"].append(
                "Create missing files using: mcn init --template=basic"
            )

        if validation_result["missing_dirs"]:
            validation_result["recommendations"].append(
                "Create missing directories for proper project organization"
            )

        # Check for frontend integration
        if not (project_path / "frontend").exists():
            validation_result["recommendations"].append(
                "Consider adding frontend integration with: mcn add-frontend --framework=react"
            )

        return validation_result


# Global project manager instance
mcn_project_manager = MCNProjectManager()
