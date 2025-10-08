#!/usr/bin/env python3
"""
MCN v3.0 Features Test Suite
Tests all new v3.0 functionality including AI models, IoT, events, agents, pipelines, and natural language
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcn.core_engine.mcn_interpreter import MCNInterpreter

def test_v3_ai_models():
    """Test AI model management features"""
    print("=== Testing AI Model Management ===")
    
    interpreter = MCNInterpreter()
    
    # Test model registration
    code = '''
    use "ai_v3"
    register("test-model", "openai", {"temperature": 0.5})
    set_model("test-model")
    var result = run("test-model", "Hello world")
    log("AI Model test: " + result)
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ AI Model Management test passed")
        return True
    except Exception as e:
        print(f"✗ AI Model Management test failed: {e}")
        return False

def test_v3_iot_integration():
    """Test IoT device integration"""
    print("=== Testing IoT Integration ===")
    
    interpreter = MCNInterpreter()
    
    code = '''
    use "iot"
    device("register", "test_sensor", {"type": "temperature_sensor"})
    var reading = device("read", "test_sensor")
    log("Sensor reading: " + reading)
    device("command", "test_sensor", {"command": "calibrate"})
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ IoT Integration test passed")
        return True
    except Exception as e:
        print(f"✗ IoT Integration test failed: {e}")
        return False

def test_v3_event_system():
    """Test event-driven programming"""
    print("=== Testing Event System ===")
    
    interpreter = MCNInterpreter()
    
    code = '''
    use "events"
    on("test_event", "log")
    trigger("test_event", {"message": "Event triggered successfully"})
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ Event System test passed")
        return True
    except Exception as e:
        print(f"✗ Event System test failed: {e}")
        return False

def test_v3_agents():
    """Test autonomous agents"""
    print("=== Testing Autonomous Agents ===")
    
    interpreter = MCNInterpreter()
    
    code = '''
    use "agents"
    agent("create", "test_agent", {"prompt": "You are a test agent"})
    agent("activate", "test_agent")
    var response = agent("think", "test_agent", {"input": "Hello"})
    log("Agent response: " + response)
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ Autonomous Agents test passed")
        return True
    except Exception as e:
        print(f"✗ Autonomous Agents test failed: {e}")
        return False

def test_v3_pipelines():
    """Test data pipelines"""
    print("=== Testing Data Pipelines ===")
    
    interpreter = MCNInterpreter()
    
    code = '''
    use "pipeline"
    pipeline("create", "test_pipeline", [{"type": "clean"}, {"type": "transform"}])
    var result = pipeline("run", "test_pipeline", "Test Data 123!")
    log("Pipeline result: " + result)
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ Data Pipelines test passed")
        return True
    except Exception as e:
        print(f"✗ Data Pipelines test failed: {e}")
        return False

def test_v3_natural_language():
    """Test natural language programming"""
    print("=== Testing Natural Language Programming ===")
    
    interpreter = MCNInterpreter()
    
    code = '''
    use "natural"
    var mcn_code = translate("create a variable name with value test")
    log("Translated code: " + mcn_code)
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ Natural Language Programming test passed")
        return True
    except Exception as e:
        print(f"✗ Natural Language Programming test failed: {e}")
        return False

def test_v3_integration():
    """Test integrated v3.0 features"""
    print("=== Testing v3.0 Integration ===")
    
    interpreter = MCNInterpreter()
    
    code = '''
    // Test integrated v3.0 features
    use "ai_v3"
    use "iot" 
    use "events"
    use "agents"
    use "pipeline"
    use "natural"
    
    // Register components
    register("integration-model", "local", {})
    device("register", "integration_sensor", {"type": "test_sensor"})
    agent("create", "integration_agent", {"prompt": "Integration test agent"})
    pipeline("create", "integration_pipeline", [{"type": "clean"}])
    
    // Test interactions
    var nl_result = translate("read sensor integration_sensor")
    log("Natural language result: " + nl_result)
    
    agent("activate", "integration_agent")
    var agent_result = agent("think", "integration_agent", {"input": "Integration test"})
    log("Agent integration result: " + agent_result)
    
    log("v3.0 Integration test completed successfully")
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ v3.0 Integration test passed")
        return True
    except Exception as e:
        print(f"✗ v3.0 Integration test failed: {e}")
        return False

def test_v3_syntax():
    """Test new v3.0 syntax features"""
    print("=== Testing v3.0 Syntax ===")
    
    interpreter = MCNInterpreter()
    
    code = '''
    // Test new v3.0 syntax
    on event "syntax_test"
    trigger "syntax_test" {"data": "test"}
    device "register" "syntax_device" {"type": "test"}
    agent "create" "syntax_agent" {"prompt": "test"}
    pipeline "create" "syntax_pipeline" [{"type": "clean"}]
    natural "create variable test with value hello"
    
    log("v3.0 syntax test completed")
    '''
    
    try:
        result = interpreter.execute(code)
        print("✓ v3.0 Syntax test passed")
        return True
    except Exception as e:
        print(f"✗ v3.0 Syntax test failed: {e}")
        return False

def run_all_tests():
    """Run all v3.0 tests"""
    print("MCN v3.0 Feature Test Suite")
    print("=" * 50)
    
    tests = [
        test_v3_ai_models,
        test_v3_iot_integration,
        test_v3_event_system,
        test_v3_agents,
        test_v3_pipelines,
        test_v3_natural_language,
        test_v3_integration,
        test_v3_syntax
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"Test failed with exception: {e}")
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All v3.0 features are working correctly!")
        return True
    else:
        print("⚠️  Some v3.0 features need attention")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)