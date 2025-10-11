"""
MCN Package Registry System
Handles package discovery, publishing, and distribution
"""

import os
import json
import time
import hashlib
import zipfile
import tempfile
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import requests
from urllib.parse import urljoin


@dataclass
class PackageMetadata:
    """Package metadata for registry"""
    name: str
    version: str
    description: str
    author: str
    license: str
    keywords: List[str]
    dependencies: List[str]
    functions: List[str]
    repository: str = ""
    homepage: str = ""
    downloads: int = 0
    created_at: float = None
    updated_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = time.time()


class MCNPackageRegistry:
    """MCN Package Registry for publishing and discovering packages"""
    
    def __init__(self, registry_url: str = "https://registry.mslang.org"):
        self.registry_url = registry_url
        self.local_cache = Path("mcn_cache")
        self.local_registry = Path("mcn_local_registry")
        
        self._ensure_directories()
        self._init_local_registry()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        self.local_cache.mkdir(exist_ok=True)
        self.local_registry.mkdir(exist_ok=True)
        (self.local_registry / "packages").mkdir(exist_ok=True)
        (self.local_registry / "metadata").mkdir(exist_ok=True)
    
    def _init_local_registry(self):
        """Initialize local registry with built-in packages"""
        builtin_packages = self._get_builtin_packages()
        
        for package_name, package_data in builtin_packages.items():
            self._save_package_metadata(package_name, package_data)
    
    def _get_builtin_packages(self) -> Dict[str, Dict]:
        """Get built-in MCN packages"""
        return {
            "ai_v3": {
                "name": "ai_v3",
                "version": "3.0.0",
                "description": "Advanced AI model management with multi-provider support and fine-tuning",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["ai", "machine-learning", "models", "fine-tuning"],
                "dependencies": [],
                "functions": ["register", "set_model", "run", "train", "list_models"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/ai_v3"
            },
            "iot": {
                "name": "iot",
                "version": "3.0.0",
                "description": "IoT device connectivity and edge computing integration",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["iot", "devices", "sensors", "edge-computing"],
                "dependencies": ["events"],
                "functions": ["register", "read", "command", "monitor"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/iot"
            },
            "events": {
                "name": "events",
                "version": "3.0.0",
                "description": "Event-driven programming and workflow automation",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["events", "workflows", "automation", "triggers"],
                "dependencies": [],
                "functions": ["on", "trigger", "emit", "schedule"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/events"
            },
            "agents": {
                "name": "agents",
                "version": "3.0.0",
                "description": "Autonomous AI agents with memory and tool integration",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["agents", "ai", "autonomous", "memory"],
                "dependencies": ["ai_v3"],
                "functions": ["create", "activate", "think", "memory"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/agents"
            },
            "natural": {
                "name": "natural",
                "version": "3.0.0",
                "description": "Natural language programming and code generation",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["natural-language", "code-generation", "ai"],
                "dependencies": ["ai_v3"],
                "functions": ["translate", "execute", "generate"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/natural"
            },
            "pipeline": {
                "name": "pipeline",
                "version": "3.0.0",
                "description": "AI-powered data processing and transformation pipelines",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["data", "pipeline", "processing", "ai"],
                "dependencies": ["ai_v3"],
                "functions": ["create", "run", "transform", "analyze"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/pipeline"
            },
            "ui": {
                "name": "ui",
                "version": "2.0.0",
                "description": "Frontend UI components and React integration",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["ui", "frontend", "react", "components"],
                "dependencies": [],
                "functions": ["button", "input", "form", "table", "chart"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/ui"
            },
            "db": {
                "name": "db",
                "version": "2.0.0",
                "description": "Database connectivity and operations",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["database", "sql", "nosql", "orm"],
                "dependencies": [],
                "functions": ["connect", "query", "insert", "update", "delete"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/db"
            },
            "http": {
                "name": "http",
                "version": "2.0.0",
                "description": "HTTP client and API integration utilities",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["http", "api", "rest", "client"],
                "dependencies": [],
                "functions": ["get", "post", "put", "delete", "fetch"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/http"
            },
            "auth": {
                "name": "auth",
                "version": "2.0.0",
                "description": "Authentication and authorization utilities",
                "author": "MCN Foundation",
                "license": "MIT",
                "keywords": ["auth", "authentication", "jwt", "oauth"],
                "dependencies": [],
                "functions": ["login", "logout", "register", "verify"],
                "repository": "https://github.com/zeroappz/mcn",
                "homepage": "https://mslang.org/packages/auth"
            }
        }
    
    def _save_package_metadata(self, package_name: str, package_data: Dict):
        """Save package metadata to local registry"""
        metadata_file = self.local_registry / "metadata" / f"{package_name}.json"
        
        # Add registry metadata
        package_data.update({
            "downloads": package_data.get("downloads", 0),
            "created_at": package_data.get("created_at", time.time()),
            "updated_at": time.time()
        })
        
        with open(metadata_file, 'w') as f:
            json.dump(package_data, f, indent=2)
    
    def search_packages(self, query: str = "", category: str = "", limit: int = 20) -> List[Dict]:
        """Search for packages in the registry"""
        results = []
        
        # Search local registry first
        metadata_dir = self.local_registry / "metadata"
        for metadata_file in metadata_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    package_data = json.load(f)
                
                # Apply filters
                if query and not self._matches_query(package_data, query):
                    continue
                
                if category and category not in package_data.get("keywords", []):
                    continue
                
                results.append({
                    "name": package_data["name"],
                    "version": package_data["version"],
                    "description": package_data["description"],
                    "author": package_data["author"],
                    "keywords": package_data.get("keywords", []),
                    "downloads": package_data.get("downloads", 0),
                    "updated_at": package_data.get("updated_at")
                })
                
            except Exception as e:
                continue
        
        # Sort by relevance (downloads, then name)
        results.sort(key=lambda x: (-x["downloads"], x["name"]))
        
        return results[:limit]
    
    def _matches_query(self, package_data: Dict, query: str) -> bool:
        """Check if package matches search query"""
        query_lower = query.lower()
        
        # Search in name, description, and keywords
        if query_lower in package_data["name"].lower():
            return True
        
        if query_lower in package_data["description"].lower():
            return True
        
        for keyword in package_data.get("keywords", []):
            if query_lower in keyword.lower():
                return True
        
        return False
    
    def get_package_info(self, package_name: str, version: str = "latest") -> Optional[Dict]:
        """Get detailed package information"""
        metadata_file = self.local_registry / "metadata" / f"{package_name}.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Try remote registry
        return self._fetch_remote_package_info(package_name, version)
    
    def _fetch_remote_package_info(self, package_name: str, version: str) -> Optional[Dict]:
        """Fetch package info from remote registry"""
        try:
            url = urljoin(self.registry_url, f"/packages/{package_name}/{version}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        
        return None
    
    def download_package(self, package_name: str, version: str = "latest") -> Optional[str]:
        """Download package from registry"""
        # Check local cache first
        cache_file = self.local_cache / f"{package_name}-{version}.zip"
        if cache_file.exists():
            return str(cache_file)
        
        # Try to download from remote registry
        try:
            url = urljoin(self.registry_url, f"/packages/{package_name}/{version}/download")
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                with open(cache_file, 'wb') as f:
                    f.write(response.content)
                return str(cache_file)
        except Exception:
            pass
        
        # For built-in packages, create a virtual package file
        if package_name in self._get_builtin_packages():
            return self._create_virtual_package(package_name, version)
        
        return None
    
    def _create_virtual_package(self, package_name: str, version: str) -> str:
        """Create a virtual package file for built-in packages"""
        cache_file = self.local_cache / f"{package_name}-{version}.zip"
        
        # Create a simple zip with metadata
        with zipfile.ZipFile(cache_file, 'w') as zf:
            package_data = self._get_builtin_packages()[package_name]
            zf.writestr("package.json", json.dumps(package_data, indent=2))
            zf.writestr("README.md", f"# {package_name}\n\n{package_data['description']}")
        
        return str(cache_file)
    
    def publish_package(self, package_path: str, api_key: str = None) -> str:
        """Publish a package to the registry"""
        package_file = Path(package_path)
        
        if not package_file.exists():
            return f"Package file '{package_path}' not found"
        
        # Extract and validate package
        try:
            with zipfile.ZipFile(package_file, 'r') as zf:
                # Check for required files
                if "package.json" not in zf.namelist():
                    return "Package must contain package.json"
                
                # Read package metadata
                with zf.open("package.json") as f:
                    package_data = json.load(f)
                
                # Validate required fields
                required_fields = ["name", "version", "description", "author"]
                for field in required_fields:
                    if field not in package_data:
                        return f"Missing required field: {field}"
                
                # Save to local registry
                self._save_package_metadata(package_data["name"], package_data)
                
                # Copy package file to local registry
                package_dest = self.local_registry / "packages" / f"{package_data['name']}-{package_data['version']}.zip"
                package_dest.parent.mkdir(exist_ok=True)
                
                import shutil
                shutil.copy2(package_file, package_dest)
                
                return f"Package '{package_data['name']}' v{package_data['version']} published successfully"
                
        except Exception as e:
            return f"Failed to publish package: {str(e)}"
    
    def create_package_template(self, name: str, description: str, author: str) -> str:
        """Create a package template"""
        template_dir = Path(f"mcn-{name}")
        
        if template_dir.exists():
            return f"Directory '{template_dir}' already exists"
        
        try:
            # Create directory structure
            template_dir.mkdir()
            (template_dir / "src").mkdir()
            (template_dir / "tests").mkdir()
            (template_dir / "docs").mkdir()
            
            # Create package.json
            package_json = {
                "name": name,
                "version": "1.0.0",
                "description": description,
                "author": author,
                "license": "MIT",
                "keywords": [],
                "dependencies": [],
                "functions": [],
                "main": "src/main.mcn",
                "repository": "",
                "homepage": ""
            }
            
            with open(template_dir / "package.json", 'w') as f:
                json.dump(package_json, f, indent=2)
            
            # Create main MCN file
            main_mcn = f'''// {name} - {description}
// Author: {author}

// Export your functions here
function hello(name) {{
    return "Hello " + name + " from {name}!"
}}

// Package initialization
log("Package '{name}' loaded successfully")
'''
            
            with open(template_dir / "src" / "main.mcn", 'w') as f:
                f.write(main_mcn)
            
            # Create README
            readme = f'''# {name}

{description}

## Installation

```bash
mcn install {name}
```

## Usage

```mcn
use "{name}"

var result = hello("World")
echo(result)
```

## Author

{author}

## License

MIT
'''
            
            with open(template_dir / "README.md", 'w') as f:
                f.write(readme)
            
            # Create test file
            test_mcn = f'''// Tests for {name}
use "{name}"

// Test hello function
var result = hello("Test")
if result == "Hello Test from {name}!" {{
    log("✓ hello function test passed")
}} else {{
    log("✗ hello function test failed")
}}
'''
            
            with open(template_dir / "tests" / "test.mcn", 'w') as f:
                f.write(test_mcn)
            
            return f"Package template created in '{template_dir}'"
            
        except Exception as e:
            return f"Failed to create template: {str(e)}"
    
    def list_categories(self) -> List[str]:
        """List available package categories"""
        categories = set()
        
        metadata_dir = self.local_registry / "metadata"
        for metadata_file in metadata_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    package_data = json.load(f)
                    categories.update(package_data.get("keywords", []))
            except Exception:
                continue
        
        return sorted(list(categories))
    
    def get_popular_packages(self, limit: int = 10) -> List[Dict]:
        """Get most popular packages"""
        packages = self.search_packages(limit=100)  # Get all packages
        
        # Sort by downloads
        packages.sort(key=lambda x: x["downloads"], reverse=True)
        
        return packages[:limit]
    
    def get_recent_packages(self, limit: int = 10) -> List[Dict]:
        """Get recently updated packages"""
        packages = self.search_packages(limit=100)  # Get all packages
        
        # Sort by update time
        packages.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        
        return packages[:limit]
    
    def increment_download_count(self, package_name: str):
        """Increment download count for a package"""
        metadata_file = self.local_registry / "metadata" / f"{package_name}.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    package_data = json.load(f)
                
                package_data["downloads"] = package_data.get("downloads", 0) + 1
                package_data["updated_at"] = time.time()
                
                with open(metadata_file, 'w') as f:
                    json.dump(package_data, f, indent=2)
                    
            except Exception:
                pass
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        metadata_dir = self.local_registry / "metadata"
        
        total_packages = len(list(metadata_dir.glob("*.json")))
        total_downloads = 0
        categories = set()
        
        for metadata_file in metadata_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    package_data = json.load(f)
                    total_downloads += package_data.get("downloads", 0)
                    categories.update(package_data.get("keywords", []))
            except Exception:
                continue
        
        return {
            "total_packages": total_packages,
            "total_downloads": total_downloads,
            "categories": len(categories),
            "registry_url": self.registry_url
        }