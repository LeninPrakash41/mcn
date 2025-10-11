"""
MCN AI Model Management System
Advanced AI model registration, fine-tuning, and multi-provider support
"""

import os
import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import requests


@dataclass
class AIModel:
    """AI Model configuration and metadata"""
    name: str
    provider: str
    model_id: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    config: Dict[str, Any] = None
    fine_tuned: bool = False
    base_model: Optional[str] = None
    training_data: Optional[str] = None
    created_at: float = None
    last_used: float = None
    usage_count: int = 0
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.created_at is None:
            self.created_at = time.time()


class MCNAIModelManager:
    """Advanced AI model management system"""
    
    def __init__(self, models_dir: str = "mcn_models"):
        self.models_dir = Path(models_dir)
        self.models: Dict[str, AIModel] = {}
        self.active_model: Optional[str] = None
        self.providers: Dict[str, Dict] = {}
        
        self._ensure_directories()
        self._init_providers()
        self._load_models()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        self.models_dir.mkdir(exist_ok=True)
        (self.models_dir / "fine_tuned").mkdir(exist_ok=True)
        (self.models_dir / "cache").mkdir(exist_ok=True)
    
    def _init_providers(self):
        """Initialize AI providers configuration"""
        self.providers = {
            "openai": {
                "base_url": "https://api.openai.com/v1",
                "models": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
                "supports_fine_tuning": True,
                "api_key_env": "OPENAI_API_KEY"
            },
            "anthropic": {
                "base_url": "https://api.anthropic.com/v1",
                "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                "supports_fine_tuning": False,
                "api_key_env": "ANTHROPIC_API_KEY"
            },
            "google": {
                "base_url": "https://generativelanguage.googleapis.com/v1",
                "models": ["gemini-pro", "gemini-pro-vision"],
                "supports_fine_tuning": True,
                "api_key_env": "GOOGLE_API_KEY"
            },
            "local": {
                "base_url": "http://localhost:11434/v1",
                "models": ["llama2", "codellama", "mistral"],
                "supports_fine_tuning": True,
                "api_key_env": None
            },
            "huggingface": {
                "base_url": "https://api-inference.huggingface.co/models",
                "models": ["microsoft/DialoGPT-medium", "facebook/blenderbot-400M-distill"],
                "supports_fine_tuning": False,
                "api_key_env": "HUGGINGFACE_API_KEY"
            }
        }
    
    def _load_models(self):
        """Load saved model configurations"""
        models_file = self.models_dir / "models.json"
        if models_file.exists():
            try:
                with open(models_file, 'r') as f:
                    data = json.load(f)
                    for model_data in data.get("models", []):
                        model = AIModel(**model_data)
                        self.models[model.name] = model
                    self.active_model = data.get("active_model")
            except Exception as e:
                print(f"Warning: Failed to load models: {e}")
        
        # Add default models if none exist
        if not self.models:
            self._add_default_models()
    
    def _add_default_models(self):
        """Add default AI models"""
        default_models = [
            AIModel("gpt-4", "openai", "gpt-4"),
            AIModel("gpt-3.5-turbo", "openai", "gpt-3.5-turbo"),
            AIModel("claude-3-sonnet", "anthropic", "claude-3-sonnet-20240229"),
            AIModel("gemini-pro", "google", "gemini-pro"),
            AIModel("llama2", "local", "llama2:latest")
        ]
        
        for model in default_models:
            self.models[model.name] = model
        
        # Set default active model
        if not self.active_model:
            self.active_model = "gpt-3.5-turbo"
    
    def _save_models(self):
        """Save model configurations to disk"""
        models_file = self.models_dir / "models.json"
        data = {
            "models": [asdict(model) for model in self.models.values()],
            "active_model": self.active_model
        }
        
        with open(models_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_model(self, name: str, provider: str, model_id: str = None, **config) -> str:
        """Register a new AI model"""
        if provider not in self.providers:
            return f"Unsupported provider: {provider}. Available: {list(self.providers.keys())}"
        
        # Use name as model_id if not provided
        if model_id is None:
            model_id = name
        
        # Get API key from environment if available
        api_key = None
        if self.providers[provider]["api_key_env"]:
            api_key = os.getenv(self.providers[provider]["api_key_env"])
        
        model = AIModel(
            name=name,
            provider=provider,
            model_id=model_id,
            api_key=api_key,
            config=config
        )
        
        self.models[name] = model
        self._save_models()
        
        return f"Model '{name}' registered with provider '{provider}'"
    
    def set_active_model(self, name: str) -> str:
        """Set the active model for AI operations"""
        if name not in self.models:
            available = list(self.models.keys())
            return f"Model '{name}' not found. Available models: {available}"
        
        self.active_model = name
        self._save_models()
        
        return f"Active model set to '{name}'"
    
    def get_model(self, name: str = None) -> Optional[AIModel]:
        """Get model by name or return active model"""
        model_name = name or self.active_model
        if model_name and model_name in self.models:
            return self.models[model_name]
        return None
    
    def list_models(self, provider: str = None) -> List[Dict]:
        """List available models"""
        models = []
        for name, model in self.models.items():
            if provider is None or model.provider == provider:
                models.append({
                    "name": name,
                    "provider": model.provider,
                    "model_id": model.model_id,
                    "fine_tuned": model.fine_tuned,
                    "active": name == self.active_model,
                    "usage_count": model.usage_count,
                    "last_used": model.last_used
                })
        
        return sorted(models, key=lambda x: x["usage_count"], reverse=True)
    
    def fine_tune_model(self, base_model: str, training_data: str, new_name: str, **config) -> str:
        """Fine-tune a model with custom data"""
        if base_model not in self.models:
            return f"Base model '{base_model}' not found"
        
        base = self.models[base_model]
        
        # Check if provider supports fine-tuning
        if not self.providers[base.provider]["supports_fine_tuning"]:
            return f"Provider '{base.provider}' does not support fine-tuning"
        
        # Validate training data
        if not os.path.exists(training_data):
            return f"Training data file '{training_data}' not found"
        
        # Create fine-tuned model
        fine_tuned_model = AIModel(
            name=new_name,
            provider=base.provider,
            model_id=f"{base.model_id}-ft-{int(time.time())}",
            api_key=base.api_key,
            endpoint=base.endpoint,
            config={**base.config, **config},
            fine_tuned=True,
            base_model=base_model,
            training_data=training_data
        )
        
        # Simulate fine-tuning process
        self._simulate_fine_tuning(fine_tuned_model, training_data)
        
        self.models[new_name] = fine_tuned_model
        self._save_models()
        
        return f"Model '{new_name}' fine-tuned from '{base_model}' using '{training_data}'"
    
    def _simulate_fine_tuning(self, model: AIModel, training_data: str):
        """Simulate the fine-tuning process"""
        # In a real implementation, this would:
        # 1. Upload training data to the provider
        # 2. Start fine-tuning job
        # 3. Monitor progress
        # 4. Update model with new ID when complete
        
        # For now, just create a training log
        log_file = self.models_dir / "fine_tuned" / f"{model.name}_training.log"
        with open(log_file, 'w') as f:
            f.write(f"Fine-tuning started: {time.ctime()}\n")
            f.write(f"Base model: {model.base_model}\n")
            f.write(f"Training data: {training_data}\n")
            f.write(f"Model ID: {model.model_id}\n")
            f.write("Status: Completed (simulated)\n")
    
    def run_model(self, prompt: str, model_name: str = None, **kwargs) -> Dict[str, Any]:
        """Run inference on a model"""
        model = self.get_model(model_name)
        if not model:
            return {"error": f"Model '{model_name or self.active_model}' not found"}
        
        # Update usage statistics
        model.last_used = time.time()
        model.usage_count += 1
        self._save_models()
        
        # Prepare request
        provider_config = self.providers[model.provider]
        
        try:
            if model.provider == "openai":
                return self._run_openai_model(model, prompt, **kwargs)
            elif model.provider == "anthropic":
                return self._run_anthropic_model(model, prompt, **kwargs)
            elif model.provider == "google":
                return self._run_google_model(model, prompt, **kwargs)
            elif model.provider == "local":
                return self._run_local_model(model, prompt, **kwargs)
            else:
                return {"error": f"Provider '{model.provider}' not implemented"}
                
        except Exception as e:
            return {"error": f"Model execution failed: {str(e)}"}
    
    def _run_openai_model(self, model: AIModel, prompt: str, **kwargs) -> Dict[str, Any]:
        """Run OpenAI model"""
        if not model.api_key:
            return {"error": "OpenAI API key not configured"}
        
        headers = {
            "Authorization": f"Bearer {model.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 150),
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        try:
            response = requests.post(
                f"{self.providers['openai']['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "response": data["choices"][0]["message"]["content"],
                    "model": model.name,
                    "provider": model.provider,
                    "usage": data.get("usage", {})
                }
            else:
                return {"error": f"API error: {response.status_code}"}
                
        except Exception as e:
            # Fallback to simulation
            return {
                "response": f"[Simulated {model.name}] Response to: {prompt[:50]}...",
                "model": model.name,
                "provider": model.provider,
                "simulated": True
            }
    
    def _run_anthropic_model(self, model: AIModel, prompt: str, **kwargs) -> Dict[str, Any]:
        """Run Anthropic model"""
        # Simulate Anthropic API call
        return {
            "response": f"[Simulated Claude] Thoughtful response to: {prompt[:50]}...",
            "model": model.name,
            "provider": model.provider,
            "simulated": True
        }
    
    def _run_google_model(self, model: AIModel, prompt: str, **kwargs) -> Dict[str, Any]:
        """Run Google model"""
        # Simulate Google API call
        return {
            "response": f"[Simulated Gemini] Comprehensive response to: {prompt[:50]}...",
            "model": model.name,
            "provider": model.provider,
            "simulated": True
        }
    
    def _run_local_model(self, model: AIModel, prompt: str, **kwargs) -> Dict[str, Any]:
        """Run local model (Ollama, etc.)"""
        # Simulate local model call
        return {
            "response": f"[Local {model.model_id}] Local response to: {prompt[:50]}...",
            "model": model.name,
            "provider": model.provider,
            "simulated": True
        }
    
    def delete_model(self, name: str) -> str:
        """Delete a model"""
        if name not in self.models:
            return f"Model '{name}' not found"
        
        model = self.models[name]
        
        # Don't delete if it's the active model and there are others
        if name == self.active_model and len(self.models) > 1:
            # Set a different active model
            for other_name in self.models:
                if other_name != name:
                    self.active_model = other_name
                    break
        
        # Remove fine-tuning files if it's a fine-tuned model
        if model.fine_tuned:
            log_file = self.models_dir / "fine_tuned" / f"{name}_training.log"
            if log_file.exists():
                log_file.unlink()
        
        del self.models[name]
        self._save_models()
        
        return f"Model '{name}' deleted successfully"
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get model usage statistics"""
        total_models = len(self.models)
        fine_tuned_count = sum(1 for m in self.models.values() if m.fine_tuned)
        
        provider_counts = {}
        for model in self.models.values():
            provider_counts[model.provider] = provider_counts.get(model.provider, 0) + 1
        
        most_used = max(self.models.values(), key=lambda m: m.usage_count, default=None)
        
        return {
            "total_models": total_models,
            "fine_tuned_models": fine_tuned_count,
            "providers": provider_counts,
            "active_model": self.active_model,
            "most_used_model": most_used.name if most_used else None,
            "total_usage": sum(m.usage_count for m in self.models.values())
        }
    
    def export_model_config(self, name: str) -> Optional[Dict]:
        """Export model configuration"""
        if name not in self.models:
            return None
        
        model = self.models[name]
        return {
            "name": model.name,
            "provider": model.provider,
            "model_id": model.model_id,
            "config": model.config,
            "fine_tuned": model.fine_tuned,
            "base_model": model.base_model
        }
    
    def import_model_config(self, config: Dict) -> str:
        """Import model configuration"""
        try:
            model = AIModel(
                name=config["name"],
                provider=config["provider"],
                model_id=config["model_id"],
                config=config.get("config", {}),
                fine_tuned=config.get("fine_tuned", False),
                base_model=config.get("base_model")
            )
            
            self.models[model.name] = model
            self._save_models()
            
            return f"Model '{model.name}' imported successfully"
            
        except Exception as e:
            return f"Import failed: {str(e)}"