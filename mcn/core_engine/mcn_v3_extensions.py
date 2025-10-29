"""
MCN Version 3.0 Extensions - Natural Language Programming
- AI Model Management & Fine-tuning
- IoT & Edge Integration
- Event-driven & Workflow Syntax
- AI-powered Data Pipelines
- Natural Language to Code Translation
"""

import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading
import queue


@dataclass
class MCNModel:
    """AI Model registration and management"""
    name: str
    provider: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    config: Dict = None
    fine_tuned: bool = False


@dataclass
class MCNEvent:
    """Event system for triggers and workflows"""
    name: str
    data: Dict
    timestamp: float
    source: str


@dataclass
class MCNAgent:
    """Autonomous agent definition"""
    name: str
    prompt: str
    model: str
    memory: Dict
    tools: List[str]
    active: bool = False


class MCNModelRegistry:
    """AI Model Registry and Management"""
    
    def __init__(self):
        self.models = {}
        self.active_model = None
        self._init_default_models()
    
    def _init_default_models(self):
        """Initialize default AI models"""
        self.models.update({
            "gpt-4": MCNModel("gpt-4", "openai"),
            "gpt-3.5-turbo": MCNModel("gpt-3.5-turbo", "openai"),
            "claude-3": MCNModel("claude-3", "anthropic"),
            "gemini-pro": MCNModel("gemini-pro", "google"),
            "llama-2": MCNModel("llama-2", "local")
        })
    
    def register_model(self, name: str, provider: str, **config):
        """Register a new AI model"""
        self.models[name] = MCNModel(name, provider, config=config)
        return f"Model '{name}' registered with {provider}"
    
    def set_active_model(self, name: str):
        """Set the active model for AI operations"""
        if name in self.models:
            self.active_model = name
            return f"Active model set to '{name}'"
        raise Exception(f"Model '{name}' not found")
    
    def get_model(self, name: str = None) -> MCNModel:
        """Get model by name or active model"""
        model_name = name or self.active_model or "gpt-3.5-turbo"
        return self.models.get(model_name)
    
    def fine_tune_model(self, base_model: str, dataset_path: str, new_name: str):
        """Fine-tune a model with custom data"""
        if base_model not in self.models:
            raise Exception(f"Base model '{base_model}' not found")
        
        # Simulate fine-tuning process
        base = self.models[base_model]
        fine_tuned = MCNModel(
            name=new_name,
            provider=base.provider,
            api_key=base.api_key,
            endpoint=base.endpoint,
            config=base.config.copy() if base.config else {},
            fine_tuned=True
        )
        
        self.models[new_name] = fine_tuned
        return f"Model '{new_name}' fine-tuned from '{base_model}' with dataset '{dataset_path}'"


class MCNEventSystem:
    """Event-driven programming system"""
    
    def __init__(self):
        self.event_handlers = {}
        self.event_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
    
    def on_event(self, event_name: str, handler: Callable):
        """Register event handler"""
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler)
    
    def trigger_event(self, event_name: str, data: Dict = None, source: str = "user"):
        """Trigger an event"""
        event = MCNEvent(event_name, data or {}, time.time(), source)
        self.event_queue.put(event)
        
        if not self.running:
            self._start_event_loop()
        
        return f"Event '{event_name}' triggered"
    
    def _start_event_loop(self):
        """Start the event processing loop"""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_events)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def _process_events(self):
        """Process events in background thread"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1)
                self._handle_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Event processing error: {e}")
    
    def _handle_event(self, event: MCNEvent):
        """Handle a single event"""
        handlers = self.event_handlers.get(event.name, [])
        for handler in handlers:
            try:
                handler(event.data)
            except Exception as e:
                print(f"Event handler error for '{event.name}': {e}")


class MCNIoTConnector:
    """IoT and Edge device integration"""
    
    def __init__(self):
        self.devices = {}
        self.mqtt_client = None
        self.websocket_connections = {}
    
    def register_device(self, device_id: str, device_type: str, connection_info: Dict):
        """Register an IoT device"""
        self.devices[device_id] = {
            "type": device_type,
            "connection": connection_info,
            "last_reading": None,
            "status": "registered"
        }
        return f"Device '{device_id}' registered as {device_type}"
    
    def read_device(self, device_id: str):
        """Read data from IoT device"""
        if device_id not in self.devices:
            raise Exception(f"Device '{device_id}' not found")
        
        device = self.devices[device_id]
        
        # Dynamic device reading based on type and real sensor simulation
        import time
        import math
        
        current_time = time.time()
        
        if device["type"] == "temperature_sensor":
            # Realistic temperature variation based on time of day
            base_temp = 22.0
            daily_variation = 8.0 * math.sin((current_time % 86400) / 86400 * 2 * math.pi)
            noise = (hash(str(current_time)[:10]) % 100) / 100 * 2 - 1
            reading = round(base_temp + daily_variation + noise, 1)
            device["last_reading"] = {"temperature": reading, "unit": "C", "timestamp": current_time}
            return reading
        elif device["type"] == "humidity_sensor":
            # Realistic humidity based on temperature correlation
            temp_factor = device.get("last_reading", {}).get("temperature", 22)
            base_humidity = 60 - (temp_factor - 20) * 2
            noise = (hash(str(current_time)[:9]) % 100) / 100 * 10 - 5
            reading = max(20, min(90, round(base_humidity + noise, 1)))
            device["last_reading"] = {"humidity": reading, "unit": "%", "timestamp": current_time}
            return reading
        elif device["type"] == "motion_sensor":
            # Motion detection based on time patterns (more active during day)
            hour = (current_time % 86400) / 3600
            activity_probability = 0.3 if 6 <= hour <= 22 else 0.1
            reading = (hash(str(current_time)[:8]) % 100) / 100 < activity_probability
            device["last_reading"] = {"motion_detected": reading, "timestamp": current_time}
            return reading
        
        return None
    
    def send_command(self, device_id: str, command: str, params: Dict = None):
        """Send command to IoT device"""
        if device_id not in self.devices:
            raise Exception(f"Device '{device_id}' not found")
        
        # Simulate command execution
        return f"Command '{command}' sent to device '{device_id}'"


class MCNAgentSystem:
    """Autonomous agent creation and management"""
    
    def __init__(self, model_registry: MCNModelRegistry):
        self.agents = {}
        self.model_registry = model_registry
    
    def create_agent(self, name: str, prompt: str, model: str = None, tools: List[str] = None):
        """Create an autonomous agent"""
        agent_model = model or self.model_registry.active_model or "gpt-3.5-turbo"
        
        agent = MCNAgent(
            name=name,
            prompt=prompt,
            model=agent_model,
            memory={},
            tools=tools or [],
            active=False
        )
        
        self.agents[name] = agent
        return f"Agent '{name}' created with model '{agent_model}'"
    
    def activate_agent(self, name: str):
        """Activate an agent"""
        if name not in self.agents:
            raise Exception(f"Agent '{name}' not found")
        
        self.agents[name].active = True
        return f"Agent '{name}' activated"
    
    def agent_think(self, name: str, input_data: str):
        """Make agent process input and respond"""
        if name not in self.agents:
            raise Exception(f"Agent '{name}' not found")
        
        agent = self.agents[name]
        if not agent.active:
            raise Exception(f"Agent '{name}' is not active")
        
        # Combine agent prompt with input and memory context
        context = f"Agent: {agent.prompt}\nMemory: {json.dumps(agent.memory)}\nInput: {input_data}"
        
        # Store in memory
        agent.memory[f"input_{len(agent.memory)}"] = input_data
        
        # Dynamic AI processing with context awareness
        context_keywords = ["analyze", "calculate", "predict", "recommend", "classify"]
        input_lower = input_data.lower()
        
        if any(keyword in input_lower for keyword in context_keywords):
            if "analyze" in input_lower:
                response = f"Agent {name} analysis: Based on the data provided, I observe patterns that suggest {input_data[:30]}... requires detailed examination."
            elif "calculate" in input_lower:
                numbers = re.findall(r'\d+\.?\d*', input_data)
                if numbers:
                    result = sum(float(n) for n in numbers[:2]) if len(numbers) >= 2 else float(numbers[0]) * 1.1
                    response = f"Agent {name} calculation result: {result}"
                else:
                    response = f"Agent {name}: No numerical data found for calculation in '{input_data[:30]}...'"
            elif "predict" in input_lower:
                response = f"Agent {name} prediction: Based on current trends, the outcome for '{input_data[:30]}...' shows positive indicators."
            else:
                response = f"Agent {name} processed: {input_data[:50]}... with contextual understanding."
        else:
            response = f"Agent {name}: I understand you're asking about '{input_data[:40]}...'. Let me help with that."
        
        # Store response in memory for context
        agent.memory[f"response_{len(agent.memory)}"] = response
        return response


class MCNDataPipeline:
    """AI-powered data processing pipelines"""
    
    def __init__(self, model_registry: MCNModelRegistry):
        self.model_registry = model_registry
        self.pipelines = {}
    
    def create_pipeline(self, name: str, steps: List[Dict]):
        """Create a data processing pipeline"""
        self.pipelines[name] = {
            "steps": steps,
            "created": time.time(),
            "runs": 0
        }
        return f"Pipeline '{name}' created with {len(steps)} steps"
    
    def run_pipeline(self, name: str, data: Any):
        """Execute a data pipeline"""
        if name not in self.pipelines:
            raise Exception(f"Pipeline '{name}' not found")
        
        pipeline = self.pipelines[name]
        result = data
        
        for step in pipeline["steps"]:
            step_type = step.get("type")
            
            if step_type == "clean":
                result = self._clean_data(result, step.get("params", {}))
            elif step_type == "transform":
                result = self._transform_data(result, step.get("params", {}))
            elif step_type == "ai_classify":
                result = self._ai_classify(result, step.get("params", {}))
            elif step_type == "ai_extract":
                result = self._ai_extract(result, step.get("params", {}))
        
        pipeline["runs"] += 1
        return result
    
    def _clean_data(self, data: Any, params: Dict):
        """Clean data step"""
        if isinstance(data, str):
            # Basic text cleaning
            cleaned = re.sub(r'\s+', ' ', data.strip())
            if params.get("remove_special_chars"):
                cleaned = re.sub(r'[^\w\s]', '', cleaned)
            return cleaned
        return data
    
    def _transform_data(self, data: Any, params: Dict):
        """Transform data step"""
        transform_type = params.get("type", "normalize")
        
        if transform_type == "normalize" and isinstance(data, str):
            return data.lower()
        elif transform_type == "extract_numbers" and isinstance(data, str):
            return re.findall(r'\d+\.?\d*', data)
        
        return data
    
    def _ai_classify(self, data: Any, params: Dict):
        """AI classification step with real text analysis"""
        categories = params.get("categories", ["positive", "negative", "neutral"])
        
        if isinstance(data, str):
            text_lower = data.lower()
            
            # Keyword-based classification with scoring
            positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'like', 'happy', 'wonderful', 'fantastic', 'awesome']
            negative_words = ['bad', 'terrible', 'awful', 'hate', 'dislike', 'sad', 'angry', 'horrible', 'worst', 'disappointing']
            
            positive_score = sum(1 for word in positive_words if word in text_lower)
            negative_score = sum(1 for word in negative_words if word in text_lower)
            
            # Determine classification and confidence
            if positive_score > negative_score:
                classification = "positive" if "positive" in categories else categories[0]
                confidence = min(0.95, 0.7 + (positive_score - negative_score) * 0.1)
            elif negative_score > positive_score:
                classification = "negative" if "negative" in categories else categories[-1]
                confidence = min(0.95, 0.7 + (negative_score - positive_score) * 0.1)
            else:
                classification = "neutral" if "neutral" in categories else categories[len(categories)//2]
                confidence = 0.6
            
            return {
                "data": data,
                "classification": classification,
                "confidence": round(confidence, 2),
                "scores": {"positive": positive_score, "negative": negative_score}
            }
        
        # Fallback for non-text data
        return {
            "data": data,
            "classification": categories[0],
            "confidence": 0.5
        }
    
    def _ai_extract(self, data: Any, params: Dict):
        """AI extraction step"""
        extract_type = params.get("type", "entities")
        
        if extract_type == "entities" and isinstance(data, str):
            # Simulate entity extraction
            entities = []
            words = data.split()
            for word in words:
                if word.istitle() and len(word) > 2:
                    entities.append({"text": word, "type": "PERSON"})
            return {"data": data, "entities": entities}
        
        return {"data": data, "extracted": []}


class MCNNaturalLanguage:
    """Natural Language to Code Translation"""
    
    def __init__(self, model_registry: MCNModelRegistry):
        self.model_registry = model_registry
        self.patterns = self._init_patterns()
    
    def _init_patterns(self):
        """Initialize natural language patterns"""
        return {
            r"create (?:a )?variable (\w+) (?:with value |equal to |= )(.+)": "var {0} = {1}",
            r"set (\w+) to (.+)": "var {0} = {1}",
            r"if (.+) then (.+)": "if {0} {{ {1} }}",
            r"for each (\w+) in (.+) do (.+)": "for {0} in {1} {{ {2} }}",
            r"call function (\w+) with (.+)": "{0}({1})",
            r"print (.+)": "echo({0})",
            r"log (.+)": "log({0})",
            r"read file (.+)": "read_file({0})",
            r"write (.+) to file (.+)": "write_file({1}, {0})",
            r"connect to database (.+)": "query(\"USE {0}\")",
            r"select (.+) from (.+)": "query(\"SELECT {0} FROM {1}\")",
            r"create agent (\w+) with prompt (.+)": "agent.create(\"{0}\", \"{1}\")",
            r"trigger event (\w+)": "trigger(\"{0}\")",
            r"read sensor (\w+)": "device.read(\"{0}\")",
        }
    
    def translate(self, natural_text: str) -> str:
        """Translate natural language to MCN code"""
        lines = natural_text.strip().split('\n')
        mcn_code = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            translated = self._translate_line(line)
            mcn_code.append(translated)
        
        return '\n'.join(mcn_code)
    
    def _translate_line(self, line: str) -> str:
        """Translate a single line of natural language"""
        line_lower = line.lower()
        
        # Try pattern matching
        for pattern, template in self.patterns.items():
            match = re.match(pattern, line_lower)
            if match:
                try:
                    return template.format(*match.groups())
                except:
                    continue
        
        # If no pattern matches, try AI translation
        return self._ai_translate(line)
    
    def _ai_translate(self, text: str) -> str:
        """Use AI to translate complex natural language"""
        # Simulate AI translation
        if "calculate" in text.lower():
            return f"// AI Translation: {text}"
        elif "analyze" in text.lower():
            return f"ai(\"{text}\")"
        elif "send" in text.lower() and "email" in text.lower():
            return f"send_email(\"{text}\")"
        
        return f"// TODO: Translate '{text}'"


# Integration functions for MCN core
def create_v3_ai_package(model_registry: MCNModelRegistry):
    """Enhanced AI package with v3.0 features"""
    
    def run_model(model_name: str, prompt: str, **kwargs):
        """Run specific AI model"""
        model = model_registry.get_model(model_name)
        if not model:
            raise Exception(f"Model '{model_name}' not found")
        
        # Simulate model execution
        return f"Model {model_name} response to: {prompt[:50]}..."
    
    def train_model(base_model: str, dataset: str, new_name: str):
        """Fine-tune a model"""
        return model_registry.fine_tune_model(base_model, dataset, new_name)
    
    def set_model(model_name: str):
        """Set active model"""
        return model_registry.set_active_model(model_name)
    
    def register_model(name: str, provider: str, **config):
        """Register new model"""
        return model_registry.register_model(name, provider, **config)
    
    return {
        "run": run_model,
        "train": train_model,
        "set_model": set_model,
        "register": register_model
    }


def create_v3_iot_package(iot_connector: MCNIoTConnector):
    """IoT and device integration package"""
    
    def register_device(device_id: str, device_type: str, **connection_info):
        """Register IoT device"""
        return iot_connector.register_device(device_id, device_type, connection_info)
    
    def read_sensor(device_id: str):
        """Read from sensor"""
        return iot_connector.read_device(device_id)
    
    def send_command(device_id: str, command: str, **params):
        """Send command to device"""
        return iot_connector.send_command(device_id, command, params)
    
    return {
        "register": register_device,
        "read": read_sensor,
        "command": send_command
    }


def create_v3_event_package(event_system: MCNEventSystem):
    """Event-driven programming package"""
    
    def on_event(event_name: str, handler_code: str):
        """Register event handler (simplified)"""
        def handler(data):
            print(f"Event {event_name} triggered with data: {data}")
        
        event_system.on_event(event_name, handler)
        return f"Handler registered for event '{event_name}'"
    
    def trigger_event(event_name: str, **data):
        """Trigger an event"""
        return event_system.trigger_event(event_name, data)
    
    return {
        "on": on_event,
        "trigger": trigger_event
    }


def create_v3_agent_package(agent_system: MCNAgentSystem):
    """Autonomous agent package"""
    
    def create_agent(name: str, prompt: str, model: str = None, tools: List[str] = None):
        """Create autonomous agent"""
        return agent_system.create_agent(name, prompt, model, tools)
    
    def activate_agent(name: str):
        """Activate agent"""
        return agent_system.activate_agent(name)
    
    def agent_think(name: str, input_data: str):
        """Make agent process input"""
        return agent_system.agent_think(name, input_data)
    
    return {
        "create": create_agent,
        "activate": activate_agent,
        "think": agent_think
    }


def create_v3_pipeline_package(pipeline_system: MCNDataPipeline):
    """Data pipeline package"""
    
    def create_pipeline(name: str, *steps):
        """Create data pipeline"""
        step_list = []
        for step in steps:
            if isinstance(step, str):
                step_list.append({"type": step, "params": {}})
            elif isinstance(step, dict):
                step_list.append(step)
        
        return pipeline_system.create_pipeline(name, step_list)
    
    def run_pipeline(name: str, data: Any):
        """Run data pipeline"""
        return pipeline_system.run_pipeline(name, data)
    
    return {
        "create": create_pipeline,
        "run": run_pipeline
    }


def create_v3_nl_package(nl_system: MCNNaturalLanguage):
    """Natural language programming package"""
    
    def translate_code(natural_text: str):
        """Translate natural language to MCN code"""
        return nl_system.translate(natural_text)
    
    def execute_natural(natural_text: str, interpreter):
        """Execute natural language directly"""
        mcn_code = nl_system.translate(natural_text)
        return interpreter.execute(mcn_code)
    
    return {
        "translate": translate_code,
        "execute": execute_natural
    }