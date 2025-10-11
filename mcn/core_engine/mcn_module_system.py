"""
MCN Module System - Enhanced Package Management
Handles dynamic loading, dependency resolution, and module lifecycle
"""

import os
import json
import importlib
import sys
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import requests
import hashlib
import tempfile
import shutil


@dataclass
class MCNPackage:
    """Package metadata and configuration"""
    name: str
    version: str
    description: str
    dependencies: List[str]
    functions: Dict[str, Any]
    author: str = ""
    license: str = "MIT"
    repository: str = ""
    installed: bool = False
    local_path: Optional[str] = None


class MCNModuleSystem:
    """Enhanced module system for MCN packages"""
    
    def __init__(self, packages_dir: str = "mcn_packages"):
        self.packages_dir = Path(packages_dir)
        self.registry_url = "https://registry.mslang.org"
        self.installed_packages: Dict[str, MCNPackage] = {}
        self.loaded_modules: Dict[str, Dict[str, Any]] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        self._ensure_directories()
        self._load_installed_packages()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        self.packages_dir.mkdir(exist_ok=True)
        (self.packages_dir / "cache").mkdir(exist_ok=True)
        (self.packages_dir / "local").mkdir(exist_ok=True)
    
    def _load_installed_packages(self):
        """Load metadata for installed packages"""
        for package_file in self.packages_dir.glob("*.json"):
            try:
                with open(package_file, 'r') as f:
                    data = json.load(f)
                    package = MCNPackage(**data)
                    self.installed_packages[package.name] = package
            except Exception as e:
                print(f"Warning: Failed to load package {package_file}: {e}")
    
    def install_package(self, package_name: str, version: str = "latest") -> str:
        """Install package from registry"""
        try:
            # Check if already installed
            if package_name in self.installed_packages:
                return f"Package '{package_name}' already installed"
            
            # Fetch package metadata
            package_info = self._fetch_package_info(package_name, version)
            if not package_info:
                return f"Package '{package_name}' not found in registry"
            
            # Install dependencies first
            for dep in package_info.get("dependencies", []):
                self.install_package(dep)
            
            # Download and install package
            package_data = self._download_package(package_name, version)
            if package_data:
                self._install_local_package(package_name, package_data)
                return f"Package '{package_name}' installed successfully"
            
            return f"Failed to install package '{package_name}'"
            
        except Exception as e:
            return f"Installation failed: {str(e)}"
    
    def _fetch_package_info(self, package_name: str, version: str) -> Optional[Dict]:
        """Fetch package information from registry"""
        try:
            url = f"{self.registry_url}/packages/{package_name}/{version}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        # Fallback to local registry simulation
        return self._get_builtin_package_info(package_name)
    
    def _get_builtin_package_info(self, package_name: str) -> Optional[Dict]:
        """Get built-in package information"""
        builtin_packages = {
            "ai_v3": {
                "name": "ai_v3",
                "version": "3.0.0",
                "description": "Advanced AI model management and fine-tuning",
                "dependencies": [],
                "functions": ["register", "set_model", "run", "train"]
            },
            "iot": {
                "name": "iot",
                "version": "3.0.0", 
                "description": "IoT device connectivity and management",
                "dependencies": ["events"],
                "functions": ["register", "read", "command"]
            },
            "events": {
                "name": "events",
                "version": "3.0.0",
                "description": "Event-driven programming system",
                "dependencies": [],
                "functions": ["on", "trigger", "emit"]
            },
            "agents": {
                "name": "agents",
                "version": "3.0.0",
                "description": "Autonomous AI agents",
                "dependencies": ["ai_v3"],
                "functions": ["create", "activate", "think"]
            },
            "natural": {
                "name": "natural",
                "version": "3.0.0",
                "description": "Natural language programming",
                "dependencies": ["ai_v3"],
                "functions": ["translate", "execute"]
            },
            "pipeline": {
                "name": "pipeline",
                "version": "3.0.0",
                "description": "AI-powered data pipelines",
                "dependencies": ["ai_v3"],
                "functions": ["create", "run", "transform"]
            }
        }
        return builtin_packages.get(package_name)
    
    def _download_package(self, package_name: str, version: str) -> Optional[Dict]:
        """Download package from registry"""
        # For now, return built-in package data
        return self._get_builtin_package_info(package_name)
    
    def _install_local_package(self, package_name: str, package_data: Dict):
        """Install package locally"""
        package = MCNPackage(
            name=package_data["name"],
            version=package_data["version"],
            description=package_data["description"],
            dependencies=package_data.get("dependencies", []),
            functions={},  # Will be loaded dynamically
            installed=True
        )
        
        # Save package metadata
        package_file = self.packages_dir / f"{package_name}.json"
        with open(package_file, 'w') as f:
            json.dump(package_data, f, indent=2)
        
        self.installed_packages[package_name] = package
    
    def use_package(self, package_name: str, interpreter=None) -> Dict[str, Any]:
        """Load and use a package"""
        if package_name in self.loaded_modules:
            return self.loaded_modules[package_name]
        
        # Check if package is installed
        if package_name not in self.installed_packages:
            # Try to install it
            result = self.install_package(package_name)
            if "successfully" not in result:
                raise Exception(f"Package '{package_name}' not available: {result}")
        
        # Load package functions
        package_functions = self._load_package_functions(package_name, interpreter)
        self.loaded_modules[package_name] = package_functions
        
        return package_functions
    
    def _load_package_functions(self, package_name: str, interpreter=None) -> Dict[str, Any]:
        """Load functions for a specific package"""
        # Import the appropriate module system
        if package_name == "ai_v3" and interpreter:
            from .mcn_v3_extensions import create_v3_ai_package
            return create_v3_ai_package(interpreter.model_registry)
        elif package_name == "iot" and interpreter:
            from .mcn_v3_extensions import create_v3_iot_package
            return create_v3_iot_package(interpreter.iot_connector)
        elif package_name == "events" and interpreter:
            from .mcn_v3_extensions import create_v3_event_package
            return create_v3_event_package(interpreter.event_system)
        elif package_name == "agents" and interpreter:
            from .mcn_v3_extensions import create_v3_agent_package
            return create_v3_agent_package(interpreter.agent_system)
        elif package_name == "natural" and interpreter:
            from .mcn_v3_extensions import create_v3_nl_package
            return create_v3_nl_package(interpreter.nl_system)
        elif package_name == "pipeline" and interpreter:
            from .mcn_v3_extensions import create_v3_pipeline_package
            return create_v3_pipeline_package(interpreter.pipeline_system)
        else:
            # Load from existing package manager
            if interpreter and hasattr(interpreter, 'package_manager'):
                return interpreter.package_manager.get_package_functions(package_name)
        
        return {}
    
    def list_packages(self, installed_only: bool = False) -> List[Dict]:
        """List available packages"""
        packages = []
        
        if installed_only:
            for name, package in self.installed_packages.items():
                packages.append({
                    "name": package.name,
                    "version": package.version,
                    "description": package.description,
                    "installed": package.installed
                })
        else:
            # Include built-in packages
            builtin_names = ["ai_v3", "iot", "events", "agents", "natural", "pipeline"]
            for name in builtin_names:
                info = self._get_builtin_package_info(name)
                if info:
                    packages.append({
                        "name": info["name"],
                        "version": info["version"],
                        "description": info["description"],
                        "installed": name in self.installed_packages
                    })
        
        return packages
    
    def uninstall_package(self, package_name: str) -> str:
        """Uninstall a package"""
        if package_name not in self.installed_packages:
            return f"Package '{package_name}' is not installed"
        
        # Check for dependencies
        dependents = self._find_dependents(package_name)
        if dependents:
            return f"Cannot uninstall '{package_name}': required by {', '.join(dependents)}"
        
        # Remove package files
        package_file = self.packages_dir / f"{package_name}.json"
        if package_file.exists():
            package_file.unlink()
        
        # Remove from memory
        del self.installed_packages[package_name]
        if package_name in self.loaded_modules:
            del self.loaded_modules[package_name]
        
        return f"Package '{package_name}' uninstalled successfully"
    
    def _find_dependents(self, package_name: str) -> List[str]:
        """Find packages that depend on the given package"""
        dependents = []
        for name, package in self.installed_packages.items():
            if package_name in package.dependencies:
                dependents.append(name)
        return dependents
    
    def get_package_info(self, package_name: str) -> Optional[Dict]:
        """Get detailed package information"""
        if package_name in self.installed_packages:
            package = self.installed_packages[package_name]
            return {
                "name": package.name,
                "version": package.version,
                "description": package.description,
                "dependencies": package.dependencies,
                "functions": list(package.functions.keys()) if package.functions else [],
                "installed": package.installed,
                "author": package.author,
                "license": package.license
            }
        
        # Check built-in packages
        return self._get_builtin_package_info(package_name)
    
    def update_package(self, package_name: str) -> str:
        """Update package to latest version"""
        if package_name not in self.installed_packages:
            return f"Package '{package_name}' is not installed"
        
        # For now, just reinstall
        self.uninstall_package(package_name)
        return self.install_package(package_name)
    
    def create_local_package(self, name: str, functions: Dict[str, Any], 
                           description: str = "", dependencies: List[str] = None) -> str:
        """Create a local package"""
        package_data = {
            "name": name,
            "version": "1.0.0",
            "description": description,
            "dependencies": dependencies or [],
            "functions": list(functions.keys()),
            "local": True
        }
        
        # Save package
        self._install_local_package(name, package_data)
        
        # Store functions in memory
        self.loaded_modules[name] = functions
        
        return f"Local package '{name}' created successfully"