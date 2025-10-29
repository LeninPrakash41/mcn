"""
MCN Embedded Integration - Dynamic integration into existing Python projects
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core_engine'))

from mcn_interpreter import MCNInterpreter
# from mcn_dynamic_systems import DynamicSystemsManager
class DynamicSystemsManager:
    def __init__(self):
        self.systems = {}
    def get_system(self, name):
        return self.systems.get(name, {})
    def register_system(self, name, system):
        self.systems[name] = system
# from mcn_v3_extensions import V3ExtensionsManager
class V3ExtensionsManager:
    def __init__(self):
        self.extensions = {}
    def get_extension(self, name):
        return self.extensions.get(name, {})
    def register_extension(self, name, ext):
        self.extensions[name] = ext
    def get_ai_functions(self):
        return {}
    def get_iot_functions(self):
        return {}
    def get_pipeline_functions(self):
        return {}
from typing import Dict, Any, Callable, Optional
import asyncio
import threading
from datetime import datetime


class MCNEmbedded:
    """Enhanced MCN integration with v3.0 features for existing Python applications"""

    def __init__(self, enable_v3_features: bool = True):
        self.interpreter = MCNInterpreter()
        self.systems_manager = DynamicSystemsManager() if enable_v3_features else None
        self.v3_manager = V3ExtensionsManager() if enable_v3_features else None
        self.event_handlers = {}
        self.background_tasks = []
        self._setup_enhanced_functions()

    def _setup_enhanced_functions(self):
        """Setup enhanced MCN functions for embedded use"""
        # Real-time event system
        self.interpreter.functions["on_event"] = self._register_event_handler
        self.interpreter.functions["emit_event"] = self._emit_event
        
        # Background task management
        self.interpreter.functions["start_background_task"] = self._start_background_task
        self.interpreter.functions["stop_background_task"] = self._stop_background_task
        
        # System integration
        self.interpreter.functions["get_system_info"] = self._get_system_info
        self.interpreter.functions["log_to_file"] = self._log_to_file
        
        # Enhanced AI integration if v3 enabled
        if self.v3_manager:
            self.interpreter.functions.update(self.v3_manager.get_ai_functions())
            self.interpreter.functions.update(self.v3_manager.get_iot_functions())
            self.interpreter.functions.update(self.v3_manager.get_pipeline_functions())

    def register_function(self, name: str, func: Callable, description: str = ""):
        """Register Python function for MCN scripts with optional description"""
        self.interpreter.register_function(name, func)
        if description and not hasattr(self.interpreter, 'function_docs'):
            self.interpreter.function_docs = {}
        if description:
            self.interpreter.function_docs[name] = description

    def set_context(self, context: Dict[str, Any]):
        """Set context variables for MCN execution"""
        self.interpreter.variables.update(context)

    def execute(
        self, script: str, context: Dict[str, Any] = None, quiet: bool = False
    ) -> Any:
        """Execute MCN script with optional context"""
        if context:
            self.set_context(context)
        return self.interpreter.execute(script, quiet=quiet)

    def execute_file(
        self, script_path: str, context: Dict[str, Any] = None, quiet: bool = False
    ) -> Any:
        """Execute MCN script from file with enhanced error handling"""
        try:
            with open(script_path, "r", encoding='utf-8') as f:
                script = f.read()
            return self.execute(script, context, quiet)
        except FileNotFoundError:
            raise FileNotFoundError(f"MCN script file not found: {script_path}")
        except Exception as e:
            raise RuntimeError(f"Error executing MCN file {script_path}: {str(e)}")
    
    def execute_async(self, script: str, context: Dict[str, Any] = None) -> asyncio.Future:
        """Execute MCN script asynchronously"""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, self.execute, script, context, True)
    
    def _register_event_handler(self, event_name: str, handler_func: Callable):
        """Register event handler for real-time events"""
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler_func)
        return f"Event handler registered for: {event_name}"
    
    def _emit_event(self, event_name: str, data: Dict[str, Any] = None):
        """Emit event to registered handlers"""
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                try:
                    handler(data or {})
                except Exception as e:
                    print(f"Error in event handler for {event_name}: {e}")
        return f"Event emitted: {event_name}"
    
    def _start_background_task(self, task_name: str, script: str, interval: float = 1.0):
        """Start background MCN script execution"""
        def run_background():
            while task_name in [t['name'] for t in self.background_tasks]:
                try:
                    self.execute(script, quiet=True)
                    threading.Event().wait(interval)
                except Exception as e:
                    print(f"Background task {task_name} error: {e}")
                    break
        
        thread = threading.Thread(target=run_background, daemon=True)
        self.background_tasks.append({'name': task_name, 'thread': thread})
        thread.start()
        return f"Background task started: {task_name}"
    
    def _stop_background_task(self, task_name: str):
        """Stop background task"""
        self.background_tasks = [t for t in self.background_tasks if t['name'] != task_name]
        return f"Background task stopped: {task_name}"
    
    def _get_system_info(self):
        """Get system information"""
        return {
            "timestamp": datetime.now().isoformat(),
            "variables_count": len(self.interpreter.variables),
            "functions_count": len(self.interpreter.functions),
            "background_tasks": len(self.background_tasks),
            "event_handlers": len(self.event_handlers)
        }
    
    def _log_to_file(self, message: str, filename: str = "mcn_embedded.log"):
        """Log message to file with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(filename, "a", encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
        return f"Logged to {filename}"


# Enhanced integration examples with v3.0 features
def enhanced_crm_integration():
    """Example: Enhanced CRM workflow with AI and automation"""
    mcn = MCNEmbedded(enable_v3_features=True)

    # Register enhanced CRM functions
    def send_email(to: str, subject: str, body: str = ""):
        print(f"📧 Email sent to {to}: {subject}")
        return {"status": "sent", "to": to, "timestamp": datetime.now().isoformat()}
    
    def create_lead(name: str, email: str, source: str = "web"):
        lead_id = f"lead_{hash(name)}_{int(datetime.now().timestamp())}"
        print(f"👤 Lead created: {name} ({lead_id})")
        return {"id": lead_id, "name": name, "email": email, "source": source}
    
    def analyze_lead_quality(lead_data: dict):
        # Mock AI analysis
        score = hash(lead_data.get('email', '')) % 100
        return {"quality_score": score, "recommendation": "high" if score > 70 else "medium"}

    mcn.register_function("send_email", send_email, "Send email to customer")
    mcn.register_function("create_lead", create_lead, "Create new lead in CRM")
    mcn.register_function("analyze_lead_quality", analyze_lead_quality, "AI-powered lead quality analysis")

    # Enhanced workflow with AI integration
    workflow = """
    use "ai_v3"
    
    var lead_name = customer_name
    var lead_email = customer_email
    var lead_source = customer_source

    // Create lead
    var lead = create_lead(lead_name, lead_email, lead_source)
    log "Lead created: " + lead.id

    // AI quality analysis
    var quality = analyze_lead_quality(lead)
    log "Lead quality score: " + quality.quality_score

    // Conditional workflow based on quality
    if quality.recommendation == "high"
        send_email(lead_email, "Welcome Premium Customer!", "Thank you for your interest")
        log "High-quality lead - premium welcome sent"
    else
        send_email(lead_email, "Welcome!", "Thank you for your interest")
        log "Standard welcome sent"

    // Log to file for tracking
    log_to_file("Lead processed: " + lead_name + " (Score: " + quality.quality_score + ")")
    
    lead
    """

    result = mcn.execute(workflow, {
        "customer_name": "Alice Johnson", 
        "customer_email": "alice@techcorp.com",
        "customer_source": "website_form"
    })

    return result


def enhanced_ai_agent_integration():
    """Example: Enhanced AI Agent with memory and learning"""
    mcn = MCNEmbedded(enable_v3_features=True)
    
    # Agent memory storage
    agent_memory = {"conversations": [], "user_preferences": {}}

    def classify_intent(text: str):
        intents = {
            "support": ["help", "issue", "problem", "support"],
            "booking": ["book", "reserve", "schedule", "appointment"],
            "info": ["what", "how", "when", "where", "info"],
            "greeting": ["hello", "hi", "hey", "good"]
        }
        
        text_lower = text.lower()
        for intent, keywords in intents.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent
        return "unknown"
    
    def generate_contextual_response(intent: str, user_message: str, context: dict):
        # Store conversation in memory
        agent_memory["conversations"].append({
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "intent": intent
        })
        
        responses = {
            "support": "I understand you need help. Based on our previous conversations, I can assist you better. What specific issue are you facing?",
            "booking": "I'd be happy to help you make a booking. What type of service are you looking for?",
            "info": "I can provide detailed information. What would you like to know more about?",
            "greeting": f"Hello! Nice to see you again. How can I help you today?",
            "unknown": "I'm learning to understand you better. Could you rephrase that or provide more context?"
        }
        
        return responses.get(intent, responses["unknown"])
    
    def update_user_preferences(user_id: str, preferences: dict):
        agent_memory["user_preferences"][user_id] = preferences
        return f"Preferences updated for user {user_id}"

    mcn.register_function("classify_intent", classify_intent, "Classify user intent from message")
    mcn.register_function("generate_contextual_response", generate_contextual_response, "Generate response with context")
    mcn.register_function("update_user_preferences", update_user_preferences, "Update user preferences")
    mcn.register_function("get_conversation_history", lambda: agent_memory["conversations"], "Get conversation history")

    # Enhanced agent script with memory and learning
    agent_script = """
    use "agents"
    
    var user_message = input_text
    var user_id = user_id || "anonymous"
    
    // Classify intent
    var intent = classify_intent(user_message)
    log "Detected intent: " + intent
    
    // Get conversation context
    var history = get_conversation_history()
    var context = {"history_length": history.length, "user_id": user_id}
    
    // Generate contextual response
    var response = generate_contextual_response(intent, user_message, context)
    
    // Log interaction
    log_to_file("Agent interaction - Intent: " + intent + ", Response generated")
    
    // Emit event for other systems
    emit_event("agent_interaction", {
        "intent": intent,
        "user_message": user_message,
        "response": response,
        "timestamp": get_system_info().timestamp
    })
    
    response
    """

    result = mcn.execute(agent_script, {
        "input_text": "Hi, I need help with booking a table for tonight",
        "user_id": "user_123"
    })

    return result, agent_memory
