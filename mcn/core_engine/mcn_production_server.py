"""
MCN Production Server - High-performance API server
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import os
from .mcn_production_runtime import get_production_runtime


app = Flask(__name__)
if os.getenv("MCN_ENABLE_CORS", "false").lower() == "true":
    CORS(app)

runtime = get_production_runtime()


@app.route('/api/execute', methods=['POST'])
def execute_code():
    """Execute MCN code endpoint"""
    try:
        data = request.get_json()
        code = data.get('code', '')
        context = data.get('context', {})
        
        if not code:
            return jsonify({"error": "No code provided"}), 400
        
        result = runtime.execute_secure(code, context)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def system_status():
    """Get system status"""
    return jsonify(runtime.get_system_status())


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "version": "3.0.0"
    })


if __name__ == '__main__':
    port = int(os.getenv('MCN_PORT', 8080))
    debug = os.getenv('MCN_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)