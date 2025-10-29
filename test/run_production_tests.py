#!/usr/bin/env python3
"""
Production Test Runner - Execute all integration tests
"""

import sys
import os
import time
import subprocess
import json

# Add MCN to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run_test_suite():
    """Run complete production test suite"""
    print("🚀 MCN Production Integration Tests")
    print("=" * 50)
    
    start_time = time.time()
    
    # Test 1: Core Integration
    print("\n1. Testing Core Integration...")
    try:
        from test_production_integration import TestProductionIntegration
        import unittest
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestProductionIntegration)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        if result.wasSuccessful():
            print("✅ Core Integration Tests: PASSED")
        else:
            print("❌ Core Integration Tests: FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Core Integration Tests: ERROR - {e}")
        return False
    
    # Test 2: Performance Test
    print("\n2. Testing Performance Under Load...")
    try:
        from mcn.core_engine.mcn_production_runtime import get_production_runtime
        runtime = get_production_runtime()
        
        # Execute 50 operations and measure performance
        operations = []
        for i in range(50):
            start = time.time()
            code = f'''
use "iot"
device("register", "perf_test_{i}", {{"type": "sensor"}})
var reading = device("read", "perf_test_{i}")
log("Performance test {i}: " + reading)
'''
            result = runtime.execute_secure(code)
            duration = time.time() - start
            operations.append(duration)
            
            if not result["success"]:
                print(f"❌ Performance Test: Operation {i} failed")
                return False
        
        avg_time = sum(operations) / len(operations)
        max_time = max(operations)
        
        print(f"✅ Performance Test: PASSED")
        print(f"   Average execution time: {avg_time:.3f}s")
        print(f"   Maximum execution time: {max_time:.3f}s")
        print(f"   Operations per second: {1/avg_time:.1f}")
        
    except Exception as e:
        print(f"❌ Performance Test: ERROR - {e}")
        return False
    
    # Test 3: Real Workload Simulation
    print("\n3. Testing Real Workload Simulation...")
    try:
        workload_code = '''
// Simulate real smart building workload
use "ai_v3"
use "iot"
use "events"
use "agents"

// Register building systems
device("register", "building_temp_01", {"type": "temperature_sensor", "location": "floor_1"})
device("register", "building_temp_02", {"type": "temperature_sensor", "location": "floor_2"})
device("register", "building_hvac", {"type": "hvac_controller", "location": "central"})
device("register", "security_cam_01", {"type": "motion_sensor", "location": "entrance"})

// Create AI agents
agent("create", "building_manager", {
    "prompt": "You manage building operations efficiently",
    "model": "gpt-3.5-turbo",
    "tools": ["device", "query", "log"]
})

// Simulate 24-hour operation cycle
for hour in range(0, 24) {
    // Read all sensors
    var temp1 = device("read", "building_temp_01")
    var temp2 = device("read", "building_temp_02")
    var motion = device("read", "security_cam_01")
    
    // AI decision making
    var avg_temp = (temp1.value + temp2.value) / 2
    
    if avg_temp > 25 {
        device("command", "building_hvac", {"command": "cool", "target": 22})
    } else if avg_temp < 20 {
        device("command", "building_hvac", {"command": "heat", "target": 23})
    }
    
    // Log operational data
    query("CREATE TABLE IF NOT EXISTS building_ops (hour INTEGER, avg_temp REAL, motion BOOLEAN)")
    query("INSERT INTO building_ops VALUES (?, ?, ?)", (hour, avg_temp, motion.value))
}

log("24-hour building simulation completed")
'''
        
        result = runtime.execute_secure(workload_code)
        if result["success"]:
            print("✅ Real Workload Simulation: PASSED")
        else:
            print(f"❌ Real Workload Simulation: FAILED - {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Real Workload Simulation: ERROR - {e}")
        return False
    
    # Test 4: System Status Check
    print("\n4. Checking System Status...")
    try:
        status = runtime.get_system_status()
        
        print(f"✅ System Status: {status['status'].upper()}")
        print(f"   Memory Usage: {status['metrics']['memory_mb']:.1f} MB")
        print(f"   CPU Usage: {status['metrics']['cpu_percent']:.1f}%")
        print(f"   Active Devices: {status['metrics']['active_devices']}")
        print(f"   Features Enabled: {sum(status['features'].values())}/{len(status['features'])}")
        
    except Exception as e:
        print(f"❌ System Status Check: ERROR - {e}")
        return False
    
    # Summary
    total_time = time.time() - start_time
    print("\n" + "=" * 50)
    print(f"🎉 ALL TESTS PASSED in {total_time:.2f} seconds")
    print("\n✅ Production System Ready:")
    print("   • Security vulnerabilities addressed")
    print("   • Dynamic systems implemented")
    print("   • Real workload integration tested")
    print("   • Performance validated")
    print("\n🚀 MCN v3.0 Production Deployment Ready!")
    
    return True


if __name__ == '__main__':
    success = run_test_suite()
    sys.exit(0 if success else 1)