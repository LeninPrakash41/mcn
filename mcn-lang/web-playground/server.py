#!/usr/bin/env python3
"""
MCN Web Playground Server
Minimal Flask server to execute MCN code via web interface
"""

try:
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
except ImportError:
    print("Flask not installed. Installing now...")
    import subprocess
    subprocess.check_call(["pip", "install", "flask", "flask-cors"])
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS

import sys
import os
import json

# Add parent directory to path to import MCN modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcn_interpreter import MCNInterpreter

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/execute', methods=['POST'])
def execute_mcn():
    try:
        data = request.get_json()
        code = data.get('code', '')

        if not code.strip():
            return jsonify({'success': False, 'error': 'No code provided'})

        # Create MCN interpreter instance
        interpreter = MCNInterpreter()

        # Capture output
        output_lines = []
        original_log = interpreter.functions['log']

        def capture_log(message):
            output_lines.append(str(message))
            original_log(message)

        interpreter.functions['log'] = capture_log

        # Execute MCN code
        result = interpreter.execute(code, quiet=True)

        return jsonify({
            'success': True,
            'result': result,
            'output': output_lines
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'output': []
        })

@app.route('/api/examples')
def get_examples():
    examples = {
        'hello': {
            'name': 'Hello World',
            'code': '''// Hello World Example
log "Hello, MCN World!"
var greeting = "Welcome to MCN"
log greeting'''
        },
        'variables': {
            'name': 'Variables & Math',
            'code': '''// Variables and calculations
var x = 10
var y = 5
var sum = x + y
var product = x * y
log "Sum: " + sum
log "Product: " + product'''
        },
        'conditions': {
            'name': 'Conditions',
            'code': '''// Conditional logic
var score = 85
if score >= 90
    log "Grade: A"
else
    if score >= 80
        log "Grade: B"
    else
        log "Grade: C"'''
        },
        'loops': {
            'name': 'Loops',
            'code': '''// For loop example
var numbers = [1, 2, 3, 4, 5]
for num in numbers
    log "Number: " + num'''
        },
        'api': {
            'name': 'API Call',
            'code': '''// API integration (mock)
var response = trigger("https://api.github.com/users/octocat", {}, "GET")
log "API Status: " + response.status_code
if response.success
    log "User found: " + response.data.name
else
    log "API call failed"'''
        },
        'ai': {
            'name': 'AI Analysis',
            'code': '''// AI integration
var sales_data = "Q1: $100k, Q2: $150k, Q3: $200k"
var analysis = ai("Analyze this sales trend: " + sales_data)
log "AI Analysis: " + analysis

var forecast = ai("Predict Q4 sales based on trend")
log "Forecast: " + forecast'''
        }
    }
    return jsonify(examples)

if __name__ == '__main__':
    print("Starting MCN Web Playground...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
