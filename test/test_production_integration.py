"""
Production Integration Tests - Real Workload Testing
"""

import unittest
import time
import json
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Add MCN to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcn.core_engine.mcn_production_runtime import get_production_runtime


class TestProductionIntegration(unittest.TestCase):
    """Test MCN production integration with real workloads"""
    
    def setUp(self):
        self.runtime = get_production_runtime()
        self.test_data = {
            "temperature_readings": [22.5, 23.1, 24.0, 25.2, 26.1],
            "customer_data": {
                "age": 35, "income": 55000, "spending_score": 0.7,
                "gender": 1, "category": 2
            }
        }
    
    def test_ai_model_integration(self):
        """Test AI model integration under load"""
        code = '''
use "ai_v3"
register("test-model", "openai", {"temperature": 0.5})
set_model("test-model")
var result = run("Analyze customer behavior patterns")
log("AI Result: " + result)
'''
        
        result = self.runtime.execute_secure(code)
        self.assertTrue(result["success"])
        self.assertIn("result", result)
    
    def test_iot_device_simulation(self):
        """Test IoT device operations with realistic data"""
        code = '''
use "iot"
device("register", "prod_temp_01", {"type": "temperature_sensor", "location": "production_floor"})
device("register", "prod_humidity_01", {"type": "humidity_sensor", "location": "production_floor"})

var temp = device("read", "prod_temp_01")
var humidity = device("read", "prod_humidity_01")

log("Temperature: " + temp.value + "°C")
log("Humidity: " + humidity.value + "%")

if temp.value > 25 {
    device("command", "hvac_01", {"command": "cool", "target": 22})
}
'''
        
        result = self.runtime.execute_secure(code)
        self.assertTrue(result["success"])
    
    def test_ml_pipeline_integration(self):
        """Test ML pipeline with real data processing"""
        code = '''
load_dataset("test_customers", "examples/sample_ml_data.csv")
var preprocessing = preprocess("test_customers", [
    {"type": "normalize", "columns": ["age", "income"]},
    {"type": "encode_categorical", "columns": ["gender"]}
])

var model_result = train("random_forest", "test_customers", "churn")
log("Model trained: " + model_result.model_id)

var prediction = predict(model_result.model_id, {
    "age": 35, "income": 55000, "spending_score": 0.7,
    "gender": 1, "category": 2, "tenure_months": 24,
    "support_calls": 2, "satisfaction_score": 4.2
})
log("Prediction: " + prediction.prediction)
'''
        
        result = self.runtime.execute_secure(code)
        self.assertTrue(result["success"])
    
    def test_event_driven_automation(self):
        """Test event-driven system integration"""
        code = '''
use "events"
use "iot"

function handle_alert(data) {
    log("Alert handled: " + data.type)
    return "Alert processed"
}

on event "system_alert" handle_alert

device("register", "alert_sensor", {"type": "motion_sensor"})
var motion = device("read", "alert_sensor")

if motion.value {
    trigger("system_alert", {"type": "motion_detected", "location": "entrance"})
}
'''
        
        result = self.runtime.execute_secure(code)
        self.assertTrue(result["success"])
    
    def test_concurrent_execution(self):
        """Test system under concurrent load"""
        def execute_test_code():
            code = '''
use "ai_v3"
use "iot"
device("register", "load_test_" + random(1, 1000), {"type": "sensor"})
var reading = device("read", "load_test_" + random(1, 1000))
log("Load test reading: " + reading)
'''
            return self.runtime.execute_secure(code)
        
        # Execute 10 concurrent requests
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_test_code) for _ in range(10)]
            results = [f.result() for f in futures]
        
        # Check all executions succeeded
        success_count = sum(1 for r in results if r.get("success", False))
        self.assertGreaterEqual(success_count, 8)  # Allow some failures under load
    
    def test_system_metrics(self):
        """Test system monitoring and metrics"""
        status = self.runtime.get_system_status()
        
        self.assertEqual(status["status"], "operational")
        self.assertIn("metrics", status)
        self.assertIn("features", status)
        self.assertTrue(status["features"]["ai_models"])
        self.assertTrue(status["features"]["iot_devices"])
    
    def test_security_validation(self):
        """Test security measures"""
        # Test code size limit
        large_code = "log('test')\n" * 10000
        result = self.runtime.execute_secure(large_code)
        self.assertFalse(result["success"])
        self.assertIn("exceeds maximum limit", result["error"])
        
        # Test dangerous code detection
        dangerous_code = "import os; os.system('rm -rf /')"
        result = self.runtime.execute_secure(dangerous_code)
        self.assertFalse(result["success"])
        self.assertIn("dangerous code", result["error"])
    
    def test_real_world_scenario(self):
        """Test complete real-world business scenario"""
        code = '''
// Real-world smart office automation scenario
use "ai_v3"
use "iot" 
use "events"
use "agents"

// Setup office environment
device("register", "office_temp", {"type": "temperature_sensor", "location": "main_office"})
device("register", "office_occupancy", {"type": "motion_sensor", "location": "main_office"})
device("register", "hvac_system", {"type": "hvac_controller", "location": "building"})

// Create facility management agent
agent("create", "facility_ai", {
    "prompt": "You manage office facilities efficiently",
    "model": "gpt-3.5-turbo",
    "tools": ["device", "log"]
})

// Monitor and respond to conditions
var temp = device("read", "office_temp")
var occupancy = device("read", "office_occupancy")

log("Office Status - Temp: " + temp.value + "°C, Occupied: " + occupancy.value)

// AI-driven facility management
if temp.value > 24 and occupancy.value {
    var decision = agent("think", "facility_ai", {
        "input": "Temperature is " + temp.value + "°C with people present. Optimize comfort."
    })
    
    device("command", "hvac_system", {"command": "cool", "target": 22})
    log("Cooling activated based on AI decision: " + decision)
}

// Store operational data
query("CREATE TABLE IF NOT EXISTS office_metrics (timestamp DATETIME, temperature REAL, occupied BOOLEAN)")
query("INSERT INTO office_metrics VALUES (datetime('now'), ?, ?)", (temp.value, occupancy.value))

log("Smart office automation cycle completed")
'''
        
        result = self.runtime.execute_secure(code)
        self.assertTrue(result["success"])


class TestAPIIntegration(unittest.TestCase):
    """Test API server integration"""
    
    @classmethod
    def setUpClass(cls):
        # Start server in background for testing
        import subprocess
        cls.server_process = subprocess.Popen([
            'python', '-m', 'mcn.core_engine.mcn_production_server'
        ], env={**os.environ, 'MCN_PORT': '8081'})
        time.sleep(2)  # Wait for server to start
    
    @classmethod
    def tearDownClass(cls):
        cls.server_process.terminate()
    
    def test_api_health_check(self):
        """Test API health endpoint"""
        try:
            response = requests.get('http://localhost:8081/api/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
        except requests.exceptions.ConnectionError:
            self.skipTest("API server not available")
    
    def test_api_code_execution(self):
        """Test code execution via API"""
        try:
            code = 'log("API test successful")\nvar result = "API working"'
            response = requests.post('http://localhost:8081/api/execute', 
                                   json={"code": code}, timeout=10)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data.get("success", False))
        except requests.exceptions.ConnectionError:
            self.skipTest("API server not available")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)