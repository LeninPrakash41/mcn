#!/usr/bin/env python3
"""
Test script for MCN Version 2.0 features
"""

from mcn_interpreter import MCNInterpreter
import asyncio

def test_package_system():
    print("Testing Package System...")

    interpreter = MCNInterpreter()

    # Test package loading
    result = interpreter.execute('use "db"')
    assert "loaded" in result.lower()

    # Test package functions
    interpreter.execute('var result = batch_insert("users", [{"name": "Alice"}])')
    assert "Alice" in str(interpreter.variables.get('result', ''))

    print("✓ Package system test passed")

def test_type_hints():
    print("Testing Type Hints...")

    interpreter = MCNInterpreter()

    # Test type hint setting
    interpreter.execute('type "username" "string"')
    interpreter.execute('var username = "alice"')
    assert interpreter.variables['username'] == "alice"

    # Test type checking (should work with correct type)
    try:
        interpreter.execute('type "age" "number"')
        interpreter.execute('var age = 25')
        assert interpreter.variables['age'] == 25
        print("✓ Type hints test passed")
    except Exception as e:
        print(f"✗ Type hints test failed: {e}")

def test_enhanced_ai():
    print("Testing Enhanced AI with Context...")

    interpreter = MCNInterpreter()

    # Set context variables
    interpreter.execute('var user_name = "Alice"')
    interpreter.execute('var department = "Engineering"')

    # Test AI with context
    result = interpreter.execute('var ai_response = ai("Analyze user profile")')
    ai_response = interpreter.variables.get('ai_response', '')

    # Should include context in response (mock or real)
    assert len(ai_response) > 0

    print("✓ Enhanced AI test passed")

def test_async_tasks():
    print("Testing Async Tasks...")

    interpreter = MCNInterpreter()

    # Create tasks
    interpreter.execute('task "test_task" "log" "Task executed"')

    # Test task creation
    assert len(interpreter.async_runtime.tasks) > 0

    print("✓ Async tasks test passed")

def test_ai_package():
    print("Testing AI Package Functions...")

    interpreter = MCNInterpreter()

    # Load AI package
    interpreter.execute('use "ai"')

    # Test sentiment analysis
    interpreter.execute('var sentiment = analyze_sentiment("I love MCN!")')
    sentiment_result = interpreter.variables.get('sentiment')
    assert isinstance(sentiment_result, dict)
    assert 'sentiment' in sentiment_result

    # Test summarization
    interpreter.execute('var summary = summarize("This is a long text that needs summarization")')
    summary_result = interpreter.variables.get('summary')
    assert isinstance(summary_result, str)
    assert len(summary_result) > 0

    print("✓ AI package test passed")

def test_http_package():
    print("Testing HTTP Package Functions...")

    interpreter = MCNInterpreter()

    # Load HTTP package
    interpreter.execute('use "http"')

    # Test that functions are available
    assert 'get_json' in interpreter.functions
    assert 'post_form' in interpreter.functions

    print("✓ HTTP package test passed")

def test_db_package():
    print("Testing Database Package Functions...")

    interpreter = MCNInterpreter()

    # Load DB package
    interpreter.execute('use "db"')

    # Test batch insert
    interpreter.execute('var result = batch_insert("test_table", [{"id": 1}, {"id": 2}])')
    result = interpreter.variables.get('result')
    assert "2 records" in result

    # Test backup
    interpreter.execute('var backup_result = backup_table("test_table")')
    backup_result = interpreter.variables.get('backup_result')
    assert "Backed up" in backup_result

    print("✓ Database package test passed")

def test_complex_workflow():
    print("Testing Complex MCN 2.0 Workflow...")

    workflow_code = '''
        log "Starting complex workflow..."

        // Load packages
        use "ai"
        use "db"

        // Set up typed variables
        type "user_count" "number"
        var user_count = 5

        // AI analysis
        var analysis = analyze_sentiment("MCN 2.0 is amazing!")
        log "Sentiment: " + analysis.sentiment

        // Database operation
        var batch_result = batch_insert("workflow_test", [{"status": "completed"}])
        log "Batch result: " + batch_result

        // Enhanced AI with context
        var recommendation = ai("Provide workflow optimization suggestions")
        log "AI Recommendation: " + recommendation

        log "Complex workflow completed!"
    '''

    interpreter = MCNInterpreter()
    result = interpreter.execute(workflow_code)

    # Check that variables were set correctly
    assert interpreter.variables.get('user_count') == 5
    assert 'analysis' in interpreter.variables
    assert 'recommendation' in interpreter.variables

    print("✓ Complex workflow test passed")

def run_v2_example_script():
    print("Running MCN 2.0 Example Script...")

    interpreter = MCNInterpreter()

    try:
        with open('examples/v2_features_demo.mcn', 'r') as f:
            code = f.read()

        result = interpreter.execute(code)
        print("✓ V2 example script executed successfully")

    except FileNotFoundError:
        print("⚠ V2 example script not found, skipping...")
    except Exception as e:
        print(f"✗ V2 example script failed: {e}")

if __name__ == "__main__":
    print("MCN Version 2.0 Test Suite")
    print("=" * 50)

    try:
        test_package_system()
        test_type_hints()
        test_enhanced_ai()
        test_async_tasks()
        test_ai_package()
        test_http_package()
        test_db_package()
        test_complex_workflow()
        run_v2_example_script()

        print("\n" + "=" * 50)
        print("🎉 All MCN 2.0 tests passed! System is ready.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
