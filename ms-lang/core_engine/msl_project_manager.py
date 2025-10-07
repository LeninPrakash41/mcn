"""
MSL Project Manager
Handles project structure, scaffolding, and organization
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from .msl_logger import log_step, log_error
from .msl_frontend import msl_frontend

class MSLProjectManager:
    """Manages MSL project structure and scaffolding"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)
        
    def create_project_structure(self, project_name: str, 
                               include_frontend: bool = True,
                               frontend_framework: str = None) -> Dict[str, Any]:
        """Create complete MSL project structure"""
        
        log_step(f"Creating MSL project: {project_name}")
        
        project_dir = self.project_path / project_name
        project_dir.mkdir(exist_ok=True)
        
        # Core MSL structure
        structure = {
            'msl': ['scripts/', 'config/', 'data/', 'logs/'],
            'tests': ['unit/', 'integration/', 'e2e/'],
            'docs': ['api/', 'guides/', 'examples/'],
            'deployment': ['docker/', 'kubernetes/', 'terraform/']
        }
        
        if include_frontend:
            structure['frontend'] = ['src/', 'public/', 'assets/']
            
        # Create directories
        for main_dir, subdirs in structure.items():
            main_path = project_dir / main_dir
            main_path.mkdir(exist_ok=True)
            
            for subdir in subdirs:
                (main_path / subdir).mkdir(exist_ok=True)
                
        # Create essential files
        self._create_essential_files(project_dir, project_name, include_frontend, frontend_framework)
        
        log_step(f"Project {project_name} created successfully")
        
        return {
            'project_path': str(project_dir),
            'structure': structure,
            'frontend_included': include_frontend,
            'frontend_framework': frontend_framework
        }
        
    def _create_essential_files(self, project_dir: Path, project_name: str,
                              include_frontend: bool, frontend_framework: str):
        """Create essential project files"""
        
        # MSL main script
        main_msl = f'''// {project_name} - Main MSL Application
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
    
    // Your MSL code here
    var result = ai("Welcome to {project_name}! How can I help you today?")
    
    return {{
        "status": "success",
        "message": result,
        "timestamp": now()
    }}
}}

// Export for API access
export main
'''
        
        with open(project_dir / 'msl' / 'main.msl', 'w') as f:
            f.write(main_msl)
            
        # Configuration file
        config = {
            'project': {
                'name': project_name,
                'version': '1.0.0',
                'description': f'MSL application: {project_name}'
            },
            'database': {
                'type': 'postgresql',
                'host': 'localhost',
                'port': 5432,
                'name': f'{project_name}_db'
            },
            'api': {
                'port': 8080,
                'cors': True,
                'rate_limit': 100
            },
            'ai': {
                'provider': 'openai',
                'model': 'gpt-4',
                'max_tokens': 1000
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/app.log'
            }
        }
        
        with open(project_dir / 'msl' / 'config' / 'app.json', 'w') as f:
            json.dump(config, f, indent=2)
            
        # Docker configuration
        dockerfile = f'''FROM python:3.9-slim

WORKDIR /app

# Install MSL dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy MSL application
COPY msl/ ./msl/
COPY tests/ ./tests/

# Expose API port
EXPOSE 8080

# Run MSL application
CMD ["python", "-m", "msl.msl_cli", "msl/main.msl", "--serve", "--port", "8080"]
'''
        
        with open(project_dir / 'deployment' / 'docker' / 'Dockerfile', 'w') as f:
            f.write(dockerfile)
            
        # Requirements file
        requirements = '''msl-lang>=1.0.0
fastapi>=0.68.0
uvicorn>=0.15.0
sqlalchemy>=1.4.0
psycopg2-binary>=2.9.0
openai>=0.27.0
requests>=2.25.0
python-dotenv>=0.19.0
'''
        
        with open(project_dir / 'requirements.txt', 'w') as f:
            f.write(requirements)
            
        # README
        readme = f'''# {project_name}

MSL-powered application with AI, database, and API capabilities.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your application:
   ```bash
   cp msl/config/app.json.example msl/config/app.json
   # Edit configuration as needed
   ```

3. Run the application:
   ```bash
   python -m msl.msl_cli msl/main.msl
   ```

4. Serve as API:
   ```bash
   python -m msl.msl_cli msl/main.msl --serve --port 8080
   ```

## Project Structure

- `msl/` - MSL scripts and configuration
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
'''
        
        with open(project_dir / 'README.md', 'w') as f:
            f.write(readme)
            
        # Create frontend integration if requested
        if include_frontend and frontend_framework:
            self._setup_frontend_integration(project_dir, project_name, frontend_framework)
            
    def _setup_frontend_integration(self, project_dir: Path, project_name: str, framework: str):
        """Setup frontend integration"""
        
        log_step(f"Setting up {framework} frontend integration")
        
        # Sample endpoints for frontend
        endpoints = [
            {'name': 'main', 'path': '/main', 'method': 'POST'},
            {'name': 'health', 'path': '/health', 'method': 'GET'}
        ]
        
        # Generate API client
        frontend_dir = project_dir / 'frontend'
        msl_frontend.project_path = frontend_dir
        
        config = msl_frontend.create_frontend_config(framework, endpoints)
        examples = msl_frontend.generate_frontend_examples(framework, endpoints)
        
        # Create example component
        if 'component' in examples:
            ext = 'tsx' if framework == 'react' else 'vue' if framework == 'vue' else 'ts'
            example_file = frontend_dir / f'MSLExample.{ext}'
            
            with open(example_file, 'w') as f:
                f.write(examples['component'])
                
        # Frontend README
        frontend_readme = f'''# {project_name} Frontend

{framework.title()} frontend for {project_name} MSL application.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Configure MSL API:
   ```bash
   cp .env.msl.example .env.local
   # Update MSL_API_URL if needed
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

## MSL Integration

The frontend includes:
- Auto-generated API client (`msl-api-client.{ext}`)
- Example components (`MSLExample.{ext}`)
- Environment configuration (`.env.msl`)

## Usage

```javascript
import {{ useMSLApi }} from './msl-api-client';

const {{ callApi, loading, error }} = useMSLApi();

// Call MSL endpoint
const result = await callApi('main', {{ data: 'example' }});
```
'''
        
        with open(frontend_dir / 'README.md', 'w') as f:
            f.write(frontend_readme)
            
    def validate_project_structure(self, project_path: str = None) -> Dict[str, Any]:
        """Validate MSL project structure"""
        
        if not project_path:
            project_path = self.project_path
        else:
            project_path = Path(project_path)
            
        log_step("Validating project structure")
        
        required_files = [
            'msl/main.msl',
            'msl/config/app.json',
            'requirements.txt',
            'README.md'
        ]
        
        required_dirs = [
            'msl/',
            'tests/',
            'docs/',
            'logs/'
        ]
        
        validation_result = {
            'valid': True,
            'missing_files': [],
            'missing_dirs': [],
            'recommendations': []
        }
        
        # Check required files
        for file_path in required_files:
            if not (project_path / file_path).exists():
                validation_result['missing_files'].append(file_path)
                validation_result['valid'] = False
                
        # Check required directories
        for dir_path in required_dirs:
            if not (project_path / dir_path).exists():
                validation_result['missing_dirs'].append(dir_path)
                validation_result['valid'] = False
                
        # Generate recommendations
        if validation_result['missing_files']:
            validation_result['recommendations'].append(
                "Create missing files using: msl init --template=basic"
            )
            
        if validation_result['missing_dirs']:
            validation_result['recommendations'].append(
                "Create missing directories for proper project organization"
            )
            
        # Check for frontend integration
        if not (project_path / 'frontend').exists():
            validation_result['recommendations'].append(
                "Consider adding frontend integration with: msl add-frontend --framework=react"
            )
            
        return validation_result

# Global project manager instance
msl_project_manager = MSLProjectManager()