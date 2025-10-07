# MCN Developer Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Language Syntax](#language-syntax)
3. [Built-in Functions](#built-in-functions)
4. [MCN 2.0 Features](#mcn-20-features)
5. [Package System](#package-system)
6. [Server Runtime](#server-runtime)
7. [Extending MCN](#extending-mcn)
8. [Best Practices](#best-practices)

## Getting Started

### Installation
```bash
git clone <repository>
cd mcn
pip install -r requirements.txt
```

### Your First MCN Script
Create `hello.mcn`:
```mcn
var name = "World"
log "Hello " + name + "!"
```

Run it:
```bash
python mcn_cli.py hello.mcn
```

### REPL Mode
```bash
python mcn_cli.py --repl
```

## Language Syntax

### Variables
```mcn
var name = "Alice"
var age = 25
var is_active = true
var scores = [85, 92, 78]
```

### Conditionals
```mcn
if age >= 18
    log "Adult"
else
    log "Minor"
```

### Loops
```mcn
var counter = 0
while counter < 5
    log "Count: " + counter
    counter = counter + 1
```

### Error Handling
```mcn
try
    var result = risky_operation()
catch
    log "Error occurred: " + error
```

## Built-in Functions

### Core Functions
- `log(message)` - Print with timestamp
- `query(sql, params)` - Database operations
- `trigger(url, data, method)` - HTTP requests
- `ai(prompt, model, tokens)` - AI integration
- `workflow(name, params)` - Execute workflows

### Example Usage
```mcn
// Database
var users = query("SELECT * FROM users WHERE age > ?", (18,))

// API Call
var response = trigger("https://api.example.com/data", {"key": "value"})

// AI
var summary = ai("Summarize this data: " + users)
```

## MCN 2.0 Features

### 1. Type Hints (Optional)
```mcn
type "username" "string"
type "age" "number"
type "is_admin" "boolean"

var username = "alice"  // ✓ Valid
var age = "25"          // ✗ Type error if strict mode
```

### 2. Package System
```mcn
// Load packages
use "db"
use "http"
use "ai"

// Use package functions
var data = get_json("https://api.example.com/users")
var result = batch_insert("users", data)
```

### 3. Parallel Tasks
```mcn
// Create tasks
task "email" "trigger" "https://mail.api.com/send" {"to": "user@example.com"}
task "log" "query" "INSERT INTO logs VALUES (?)" ("User registered")

// Wait for completion
var results = await "email" "log"
log "All tasks completed: " + results
```

### 4. Enhanced AI Context
```mcn
var user_name = "Alice"
var department = "Engineering"

// AI automatically includes context variables
var recommendation = ai("Suggest training programs for this user")
```

## Package System

### Built-in Packages

#### Database Package (`db`)
```mcn
use "db"
batch_insert("users", [{"name": "Alice"}, {"name": "Bob"}])
backup_table("users")
```

#### HTTP Package (`http`)
```mcn
use "http"
var data = get_json("https://api.example.com/data")
post_form("https://forms.example.com", {"name": "Alice"})
```

#### AI Package (`ai`)
```mcn
use "ai"
var sentiment = analyze_sentiment("I love this product!")
var summary = summarize("Long text here...")
var trend = predict_trend([1, 2, 3, 4, 5])
```

### Creating Custom Packages
```python
# my_package.py
def custom_function(param):
    return f"Processed: {param}"

def another_function():
    return "Hello from package"

# Register in MCN
interpreter = MCNInterpreter()
interpreter.package_manager.add_package('my_package', {
    'custom_function': custom_function,
    'another_function': another_function
})
```

## Server Runtime

### Serve Single Script
```bash
python mcn_cli.py api_service.mcn --serve --port 8000
```

### Serve Directory
```bash
python mcn_cli.py --serve-dir examples/ --port 8000
```

### API Script Example
```mcn
// api_endpoint.mcn
var user_id = request_data.user_id
var user = query("SELECT * FROM users WHERE id = ?", (user_id,))

if user
    var response = {"status": "success", "user": user[0]}
else
    var response = {"status": "error", "message": "User not found"}

response  // Automatically returned as JSON
```

### Making API Calls
```bash
curl -X POST http://localhost:8000/api_endpoint \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}'
```

## Extending MCN

### Register Custom Functions
```python
from mcn_interpreter import MCNInterpreter

def my_custom_function(param1, param2):
    return param1 * param2

interpreter = MCNInterpreter()
interpreter.register_function("multiply", my_custom_function)
```

### Register Workflows
```python
from mcn_runtime import MCNRuntime

def approval_workflow(params):
    # Custom logic
    return {"approved": True, "id": params.get("request_id")}

runtime = MCNRuntime()
runtime.register_workflow("approval", approval_workflow)
```

### Custom AI Models
```python
def custom_ai_handler(prompt, model="custom", max_tokens=100):
    # Your AI integration
    return "Custom AI response"

interpreter.register_function("custom_ai", custom_ai_handler)
```

## Best Practices

### 1. Code Organization
```mcn
// Good: Clear variable names
var user_email = "alice@example.com"
var is_verified = true

// Bad: Unclear names
var e = "alice@example.com"
var v = true
```

### 2. Error Handling
```mcn
// Always handle potential errors
try
    var api_result = trigger("https://external-api.com/data")
    log "Success: " + api_result.data
catch
    log "API call failed: " + error
    var api_result = {"data": "fallback_data"}
```

### 3. Database Operations
```mcn
// Use parameterized queries
var user_id = 123
var user = query("SELECT * FROM users WHERE id = ?", (user_id,))

// Avoid string concatenation
// Bad: query("SELECT * FROM users WHERE id = " + user_id)
```

### 4. AI Integration
```mcn
// Provide context for better AI responses
var context = "User: " + user_name + ", Role: " + user_role
var ai_response = ai("Generate welcome message. Context: " + context)
```

### 5. Async Tasks
```mcn
// Use tasks for independent operations
task "notification" "trigger" "https://notify.com/send" {"message": "Welcome"}
task "analytics" "trigger" "https://analytics.com/track" {"event": "signup"}

// Don't await if you don't need the results immediately
```

### 6. Package Usage
```mcn
// Load packages at the top
use "db"
use "http"
use "ai"

// Group related operations
var user_data = get_json("https://api.com/user/123")
batch_insert("users", [user_data])
var insights = analyze_sentiment(user_data.bio)
```

### 7. Type Safety
```mcn
// Use type hints for critical variables
type "user_id" "number"
type "email" "string"
type "permissions" "array"

var user_id = 123
var email = "user@example.com"
var permissions = ["read", "write"]
```

## Development Workflow

### 1. Development
```bash
# Start REPL for testing
python mcn_cli.py --repl

# Test script
python mcn_cli.py my_script.mcn
```

### 2. Testing
```bash
# Run test suite
python test_mcn.py

# Test specific features
python mcn_cli.py examples/v2_features_demo.mcn
```

### 3. Deployment
```bash
# Serve as API
python mcn_cli.py my_api.mcn --serve --host 0.0.0.0 --port 8000

# Serve multiple scripts
python mcn_cli.py --serve-dir ./api_scripts/ --port 8000
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
   ```bash
   pip install -r requirements.txt
   ```

2. **Database Errors**: Check if SQLite database is accessible
   ```mcn
   try
       var result = query("SELECT 1")
   catch
       log "Database connection failed: " + error
   ```

3. **API Timeouts**: Add error handling for external calls
   ```mcn
   try
       var response = trigger("https://slow-api.com/data")
   catch
       log "API timeout: " + error
       var response = {"data": "cached_data"}
   ```

4. **Type Errors**: Check variable types when using type hints
   ```mcn
   type "count" "number"
   var count = 10  // ✓ Correct
   // var count = "10"  // ✗ Type error
   ```

## Next Steps

1. **Learn Advanced Features**: Explore async tasks and package system
2. **Build APIs**: Create MCN scripts that serve as REST endpoints
3. **Integrate AI**: Use AI functions for intelligent automation
4. **Extend MCN**: Create custom packages and functions
5. **Deploy**: Serve MCN scripts in production environments

For more examples, check the `examples/` directory in the MCN repository.
