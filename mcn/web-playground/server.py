#!/usr/bin/env python3
"""
MCN Web Playground Server
Dynamic Flask server with real MCN integration
"""

try:
    from flask import Flask, request, jsonify, send_from_directory, session
    from flask_cors import CORS
    import html
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call(["pip", "install", "flask", "flask-cors"])
    from flask import Flask, request, jsonify, send_from_directory, session
    from flask_cors import CORS
    import html

import sys
import os
import json
import uuid
from datetime import datetime
import threading
import time

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core_engine'))

try:
    from core_engine.mcn_interpreter import MCNInterpreter
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core_engine'))
    from mcn_interpreter import MCNInterpreter

# Dynamic database support without psycopg2 dependency
class DatabaseManager:
    
    def _detect_drivers(self):
        drivers = {'sqlite3': True}  # Always available
        try:
            import psycopg2
            drivers['postgresql'] = True
        except ImportError:
            drivers['postgresql'] = False
        try:
            import mysql.connector
            drivers['mysql'] = True
        except ImportError:
            drivers['mysql'] = False
        return drivers
    
    def __init__(self):
        self.connections = {}
        self.available_drivers = self._detect_drivers()
        self.default_connection = None
        self._setup_default_db()
    
    def _setup_default_db(self):
        import sqlite3
        self.default_connection = sqlite3.connect(':memory:')
        cursor = self.default_connection.cursor()
        cursor.execute('CREATE TABLE demo_data (id INTEGER PRIMARY KEY, name TEXT, value TEXT)')
        cursor.execute("INSERT INTO demo_data (name, value) VALUES ('sample', 'demo_value')")
        self.default_connection.commit()
    
    def connect(self, db_type, **kwargs):
        if db_type == 'sqlite3':
            import sqlite3
            return sqlite3.connect(kwargs.get('database', ':memory:'))
        elif db_type == 'postgresql' and self.available_drivers['postgresql']:
            import psycopg2
            return psycopg2.connect(**kwargs)
        elif db_type == 'mysql' and self.available_drivers['mysql']:
            import mysql.connector
            return mysql.connector.connect(**kwargs)
        else:
            raise ImportError(f"Database driver for {db_type} not available")
    
    def _execute_query(self, sql, params=None):
        try:
            cursor = self.default_connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            if sql.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                return {'rows': results, 'count': len(results)}
            else:
                self.default_connection.commit()
                return {'affected_rows': cursor.rowcount}
        except Exception as e:
            return {'error': str(e)}

class DynamicSystemsManager:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.ai_models = {}
        self.iot_devices = {}
        self.pipelines = {}
        self.agents = {}
        self.event_handlers = {}
        self.active_model = None
    
    def get_ai_functions(self):
        return {
            'register': self._register_ai_model,
            'set_model': self._set_ai_model,
            'run': self._run_ai_model
        }
    
    def get_iot_functions(self):
        return {
            'device': self._device_operation
        }
    
    def get_pipeline_functions(self):
        return {
            'pipeline': self._pipeline_operation
        }
    
    def _register_ai_model(self, name, provider, config):
        self.ai_models[name] = {'provider': provider, 'config': config, 'active': False}
        return f"AI model {name} registered with {provider}"
    
    def _set_ai_model(self, name):
        if name in self.ai_models:
            for model in self.ai_models.values():
                model['active'] = False
            self.ai_models[name]['active'] = True
            return f"Active model set to {name}"
        return f"Model {name} not found"
    
    def _run_ai_model(self, model, prompt, options=None):
        if model in self.ai_models:
            # Mock AI response for demo
            return f"AI response from {model}: Processed '{prompt[:30]}...'"
        return "Model not found"
    
    def _device_operation(self, action, device_id, params=None):
        if action == 'register':
            self.iot_devices[device_id] = params or {}
            return f"Device {device_id} registered"
        elif action == 'read':
            return {'device_id': device_id, 'value': 25, 'timestamp': datetime.now().isoformat()}
        elif action == 'command':
            return f"Command sent to {device_id}: {params}"
        return f"Unknown device action: {action}"
    
    def _pipeline_operation(self, action, name, config=None):
        if action == 'create':
            self.pipelines[name] = config or []
            return f"Pipeline {name} created"
        elif action == 'run':
            return {'status': 'completed', 'pipeline': name, 'result': 'processed'}
        return f"Unknown pipeline action: {action}"
    
    def _agent_operation(self, action, name, config=None):
        if action == 'create':
            self.agents[name] = config or {}
            return f"Agent {name} created"
        elif action == 'think':
            return f"Agent {name} thinking about: {config}"
        return f"Unknown agent action: {action}"
    
    def _translate_natural_language(self, text, execute=False):
        translations = {
            'create variable': 'var name = "value"',
            'log message': 'log "message"',
            'if condition': 'if condition\n    log "true"'
        }
        for pattern, code in translations.items():
            if pattern in text.lower():
                return code
        return f'log "Natural language: {text}"'
    
    def _register_event_handler(self, event, handler):
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
        return f"Event handler registered for {event}"
    
    def _trigger_event(self, event, data=None):
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    handler(data or {})
                except:
                    pass
        return f"Event {event} triggered"

app = Flask(__name__)
app.secret_key = 'mcn_playground_secret_key'
CORS(app, supports_credentials=True)

# Global state management
active_sessions = {}
system_manager = DynamicSystemsManager()
db_manager = DatabaseManager()


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/execute", methods=["POST"])
def execute_mcn():
    try:
        data = request.get_json()
        code = data.get("code", "")
        session_id = data.get("session_id") or str(uuid.uuid4())

        if not code.strip():
            return jsonify({"success": False, "error": "No code provided"})

        # Get or create session interpreter
        if session_id not in active_sessions:
            active_sessions[session_id] = {
                "interpreter": MCNInterpreter(),
                "created": datetime.now(),
                "output_buffer": []
            }

        session_data = active_sessions[session_id]
        interpreter = session_data["interpreter"]
        
        # Enhanced output capture with real-time streaming
        output_lines = []
        
        def capture_output(message, msg_type="log"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            # Escape HTML to prevent XSS
            safe_message = html.escape(str(message))
            formatted_msg = f"[{timestamp}] {safe_message}"
            output_lines.append({"message": formatted_msg, "type": msg_type})
            session_data["output_buffer"].append(formatted_msg)
            
            # Store for potential real-time updates
            pass

        # Override interpreter functions for capture
        original_log = interpreter.functions.get("log", lambda x: print(x))
        interpreter.functions["log"] = lambda msg: capture_output(msg, "log")
        interpreter.functions["echo"] = lambda msg: capture_output(msg, "echo")
        
        # Add playground-specific functions
        interpreter.functions["clear"] = lambda: output_lines.clear()
        interpreter.functions["session_info"] = lambda: {
            "id": session_id,
            "created": session_data["created"].isoformat(),
            "variables": len(interpreter.variables)
        }
        
        # Add dynamic system functions
        interpreter.functions.update(system_manager.get_ai_functions())
        interpreter.functions.update(system_manager.get_iot_functions())
        interpreter.functions.update(system_manager.get_pipeline_functions())
        
        # Add database functions
        interpreter.functions["query"] = lambda sql, params=None: db_manager._execute_query(sql, params)
        interpreter.functions["connect_db"] = lambda db_type, **kwargs: db_manager.connect(db_type, **kwargs)
        
        # Add enhanced MCN v3 functions
        interpreter.functions["agent"] = lambda action, name, config=None: system_manager._agent_operation(action, name, config)
        interpreter.functions["translate"] = lambda text, execute=False: system_manager._translate_natural_language(text, execute)
        interpreter.functions["on"] = lambda event, handler: system_manager._register_event_handler(event, handler)
        interpreter.functions["trigger"] = lambda event, data=None: system_manager._trigger_event(event, data)

        # Check for CLI commands
        mode = data.get("mode", "run")
        
        if mode == "cli":
            # Execute as CLI command
            import subprocess
            import os
            
            # Write code to temp file
            temp_file = f"temp_{session_id}.mcn"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(code)
            
            try:
                # Execute MCN CLI command
                cmd = data.get("command", "run")
                if cmd == "run":
                    result = subprocess.run(["python", "../../run_mcn.py", "run", temp_file], 
                                          capture_output=True, text=True, cwd=".")
                elif cmd == "serve":
                    port = data.get("port", "8080")
                    # MCN serve is not implemented yet, show message
                    return jsonify({
                        "success": True,
                        "output": [{"message": f"MCN Serve functionality is under development. Your functions would be served at http://localhost:{port}", "type": "log"}],
                        "session_id": session_id,
                        "command": f"mcn serve --port {port}"
                    })
                elif cmd == "init":
                    result = subprocess.run(["python", "../../run_mcn.py", "postman"], 
                                          capture_output=True, text=True, cwd=".")
                elif cmd == "generate":
                    gen_type = data.get("generate_type", "docs")
                    if gen_type == "api":
                        gen_type = "docs"
                    result = subprocess.run(["python", "../../run_mcn.py", gen_type], 
                                          capture_output=True, text=True, cwd=".")
                else:
                    result = subprocess.run(["python", "../../run_mcn.py"] + cmd.split(), 
                                          capture_output=True, text=True, cwd=".")
                
                os.remove(temp_file) if os.path.exists(temp_file) else None
                
                return jsonify({
                    "success": result.returncode == 0,
                    "output": [{"message": result.stdout, "type": "log"}] if result.stdout else [],
                    "error": result.stderr if result.stderr else None,
                    "session_id": session_id,
                    "command": f"mcn {cmd}"
                })
                
            except subprocess.TimeoutExpired:
                return jsonify({
                    "success": True,
                    "output": [{"message": f"Server started on port {port}. Check http://localhost:{port}", "type": "success"}],
                    "session_id": session_id,
                    "command": f"mcn serve --port {port}"
                })
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": f"CLI execution failed: {str(e)}",
                    "session_id": session_id
                })
        
        # Execute with enhanced error handling
        start_time = time.time()
        result = interpreter.execute(code, quiet=True)
        execution_time = time.time() - start_time

        return jsonify({
            "success": True, 
            "result": result, 
            "output": output_lines,
            "session_id": session_id,
            "execution_time": round(execution_time, 3),
            "variables_count": len(interpreter.variables)
        })

    except Exception as e:
        error_msg = f"Execution Error: {str(e)}"
        return jsonify({
            "success": False, 
            "error": error_msg, 
            "output": [{"message": error_msg, "type": "error"}],
            "session_id": session_id if 'session_id' in locals() else None
        })


@app.route("/api/examples")
def get_examples():
    examples = {
        "hello": {
            "name": "Hello World",
            "description": "Basic MCN syntax and variables",
            "code": """// Hello World Example
log "Hello, MCN World!"
var greeting = "Welcome to MCN"
log greeting
echo "Current time: " + session_info().created"""
        },
        "business": {
            "name": "Business Logic",
            "description": "Real business calculations and functions",
            "code": """// Business Logic Example
var order_total = 100.00
var tax_rate = 0.08
var tax = order_total * tax_rate
var final_total = order_total + tax

log "Order: $" + order_total
log "Tax: $" + tax
log "Total: $" + final_total

function calculate_discount(amount, percentage)
    return amount * (percentage / 100)

var discount = calculate_discount(order_total, 10)
log "10% Discount: $" + discount"""
        },
        "api_server": {
            "name": "API Server",
            "description": "REST API endpoints - try Serve API button",
            "code": """// REST API Server
function get_users()
    return [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

function create_user(name, email)
    log "Creating user: " + name
    return {"id": 3, "name": name, "email": email}

// Test endpoints
var users = get_users()
echo users
var new_user = create_user("Alice", "alice@example.com")
echo new_user"""
        },
        "ecommerce": {
            "name": "E-commerce",
            "description": "Complete e-commerce order processing",
            "code": """// E-commerce System
function process_payment(amount, card)
    log "Processing payment: $" + amount
    return {"status": "success", "transaction_id": "TXN123"}

function calculate_shipping(weight, distance)
    var base = 5.00
    return base + (weight * 0.5) + (distance * 0.1)

// Process order
var item_total = 99.99
var shipping = calculate_shipping(2.5, 100)
log "Final Total: $" + (item_total + shipping)"""
        },
        "crm_system": {
            "name": "CRM System",
            "description": "Customer relationship management",
            "code": """// CRM System
function create_customer(name, email, phone)
    var customer_id = "CUST" + random(1000, 9999)
    log "Customer created: " + customer_id
    return {"id": customer_id, "name": name, "email": email}

// Demo workflow
var customer = create_customer("John Smith", "john@example.com", "555-0123")
echo customer"""
        },
        "async": {
            "name": "Async Tasks",
            "description": "Asynchronous task execution",
            "code": """// Async task operations
log "Starting async operations..."

task "email_task" log "Email sent successfully"
task "db_task" log "Database updated"
task "ai_task" log "AI processing completed"

log "Tasks created, waiting for completion..."
var results = await "email_task" "db_task" "ai_task"
log "All tasks completed"
echo results"""
        },
        "ai_integration": {
            "name": "AI Integration",
            "description": "Real AI model integration",
            "code": """use "ai_v3"

// Register AI model
register "my-gpt4" "openai"
set_model "my-gpt4"

// AI analysis
var sales_data = "Q1: $100k, Q2: $150k, Q3: $200k, Q4: $250k"
var analysis = run "my-gpt4" "Analyze this sales trend"
log "AI Analysis: " + analysis

// Prediction
var forecast = run "my-gpt4" "Predict next quarter"
log "Forecast: " + forecast"""
        },
        "iot_automation": {
            "name": "IoT Automation",
            "description": "IoT device control and automation",
            "code": """use "iot"
use "events"

// Register IoT devices
device "register" "temp_sensor"
device "register" "smart_light"

// Event-driven automation
on "high_temperature" "handle_cooling"

function handle_cooling(data)
    log "Temperature alert detected"
    device "command" "smart_light"
    log "Lights dimmed to reduce heat"

// Read temperature and trigger event
var temp = device "read" "temp_sensor"
log "Current temperature: " + temp.value

if temp.value > 25
    trigger "high_temperature"""
        },
        "data_pipeline": {
            "name": "Data Pipeline",
            "description": "AI-powered data processing pipeline",
            "code": """use "pipeline"

// Create AI-powered data processing pipeline
pipeline "create" "feedback_processor"

// Process sample feedback
var feedback = "Great product! Love it!"
var result = pipeline "run" "feedback_processor" feedback

log "Pipeline result:"
echo result

// Natural language programming
use "natural"
var code = translate "create a variable name with value John"
log "Generated code: " + code"""
        },
        "ml_training": {
            "name": "ML Training",
            "description": "Machine learning model training and deployment",
            "code": """// Machine Learning Training
load_dataset "sales_data" "data/sales.csv"
var model = train "linear_regression" "sales_data" "revenue"
log "Model trained: " + model.id

var prediction = predict model.id "sample_data"
log "Prediction: $" + prediction.value

var endpoint = deploy_model model.id "sales_predictor"
log "Model deployed"""
        },
        "natural_lang": {
            "name": "Natural Language",
            "description": "Natural language to code generation",
            "code": """use "natural"

var code1 = translate "create a function that calculates interest"
log "Generated: " + code1

var code2 = translate "if age greater than 18 then approve"
log "Generated: " + code2

translate "create variable sales with value 50000" true
log "Natural language executed"""
        },
        "agent_system": {
            "name": "Agent System",
            "description": "Autonomous AI agents for business automation",
            "code": """use "agents"

agent "create" "data_analyst"
agent "activate" "data_analyst"

var analysis = agent "think" "data_analyst" "Analyze Q4 sales data"
log "Agent Analysis:"
echo analysis"""
        }
    }
    return jsonify(examples)


# Session cleanup endpoint
@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

# Additional API endpoints
@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Get active sessions info"""
    sessions_info = []
    for sid, data in active_sessions.items():
        sessions_info.append({
            "id": sid,
            "created": data["created"].isoformat(),
            "variables": len(data["interpreter"].variables),
            "output_lines": len(data["output_buffer"])
        })
    return jsonify({"sessions": sessions_info, "total": len(sessions_info)})

@app.route("/api/session/<session_id>/variables", methods=["GET"])
def get_session_variables(session_id):
    """Get session variables"""
    if session_id in active_sessions:
        variables = active_sessions[session_id]["interpreter"].variables
        return jsonify({"variables": variables})
    return jsonify({"error": "Session not found"}), 404

@app.route("/api/session/<session_id>/clear", methods=["POST"])
def clear_session(session_id):
    """Clear session state"""
    if session_id in active_sessions:
        active_sessions[session_id]["interpreter"].variables.clear()
        active_sessions[session_id]["output_buffer"].clear()
        return jsonify({"success": True, "message": "Session cleared"})
    return jsonify({"error": "Session not found"}), 404

# Cleanup old sessions periodically
def cleanup_sessions():
    while True:
        time.sleep(300)  # 5 minutes
        current_time = datetime.now()
        expired_sessions = []
        
        for sid, data in active_sessions.items():
            if (current_time - data["created"]).seconds > 3600:  # 1 hour
                expired_sessions.append(sid)
        
        for sid in expired_sessions:
            del active_sessions[sid]
            print(f"Cleaned up expired session: {sid}")

if __name__ == "__main__":
    print("Starting MCN Web Playground...")
    print("Open http://localhost:5000 in your browser")
    print("Features: Dynamic execution, session management and more")
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
    cleanup_thread.start()
    
    app.run(debug=True, host="0.0.0.0", port=5000)
