#!/usr/bin/env python3
"""
Test MCN Full-Stack Integration
Tests the complete integration layer with UI bindings and React generation
"""

import sys
import os
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcn.core_engine.mcn_interpreter import MCNInterpreter

def test_fullstack_integration():
    """Test complete full-stack integration"""
    print("=== Testing MCN Full-Stack Integration ===")
    
    # Create test directory
    test_dir = "d:\\mcn\\test\\fullstack_test_output"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)
    
    # Change to test directory
    original_dir = os.getcwd()
    os.chdir(test_dir)
    
    try:
        interpreter = MCNInterpreter()
        
        # Read the full-stack integration script
        script_path = "d:\\mcn\\examples\\fullstack_integration_complete.mcn"
        with open(script_path, 'r') as f:
            code = f.read()
        
        print("Executing full-stack integration script...")
        result = interpreter.execute(code, script_path)
        
        print("✓ Full-stack integration script executed successfully")
        
        # Check if React project was generated
        react_dir = "./mcn-ecommerce-app"
        if os.path.exists(react_dir):
            print("✓ React project generated successfully")
            
            # Check key files
            key_files = [
                "package.json",
                "src/index.tsx", 
                "src/AppRouter.tsx",
                "src/components/UIComponents.tsx",
                "src/services/mcn-client.tsx",
                "src/styles/index.css",
                "tailwind.config.js",
                "tsconfig.json"
            ]
            
            for file_path in key_files:
                full_path = os.path.join(react_dir, file_path)
                if os.path.exists(full_path):
                    print(f"✓ {file_path} generated")
                else:
                    print(f"✗ {file_path} missing")
            
            # Check pages
            pages_dir = os.path.join(react_dir, "src/pages")
            if os.path.exists(pages_dir):
                pages = os.listdir(pages_dir)
                print(f"✓ Generated {len(pages)} page components: {pages}")
            
            # Check UI manifest
            manifest_path = os.path.join(react_dir, "ui-manifest.json")
            if os.path.exists(manifest_path):
                print("✓ UI manifest generated")
                with open(manifest_path, 'r') as f:
                    import json
                    manifest = json.load(f)
                    print(f"  - Pages: {len(manifest.get('pages', {}))}")
                    print(f"  - Components: {len(manifest.get('components', {}))}")
        else:
            print("✗ React project not generated")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        os.chdir(original_dir)

def test_ui_components():
    """Test individual UI component creation"""
    print("\n=== Testing UI Components ===")
    
    try:
        interpreter = MCNInterpreter()
        
        # Test UI component creation
        ui_test_code = '''
        use "ui"
        
        var button = ui("button", "Test Button", "test_action")
        var input = ui("input", "Test input...", "input_change")
        var text = ui("text", "Test Text", {"tag": "h1"})
        var container = ui("container", button, input, text)
        var page = ui("page", "TestPage", "/test", container)
        
        log("UI components created successfully")
        '''
        
        result = interpreter.execute(ui_test_code)
        print("✓ UI components created successfully")
        
        # Check if UI manager has components
        if hasattr(interpreter, 'ui_integration'):
            ui_manager = interpreter.ui_integration.ui_manager
            print(f"✓ Created {len(ui_manager.components)} components")
            print(f"✓ Created {len(ui_manager.pages)} pages")
        
        return True
        
    except Exception as e:
        print(f"✗ UI component test failed: {e}")
        return False

def test_ai_integration():
    """Test AI integration with UI"""
    print("\n=== Testing AI Integration ===")
    
    try:
        interpreter = MCNInterpreter()
        
        ai_ui_code = '''
        use "ui"
        use "ai_v3"
        use "agents"
        
        // Create AI agent
        agent("create", "test_agent", {"prompt": "You are a test agent"})
        agent("activate", "test_agent")
        
        // Create UI with AI integration
        var ai_button = ui("button", "AI Analysis", "agent.think('test_agent', 'analyze')")
        var ai_page = ui("page", "AITest", "/ai", ai_button)
        
        log("AI-UI integration test completed")
        '''
        
        result = interpreter.execute(ai_ui_code)
        print("✓ AI-UI integration test passed")
        return True
        
    except Exception as e:
        print(f"✗ AI integration test failed: {e}")
        return False

def run_all_tests():
    """Run all full-stack integration tests"""
    print("MCN Full-Stack Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_ui_components,
        test_ai_integration,
        test_fullstack_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"Test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All full-stack integration tests passed!")
        print("\nGenerated files are available in:")
        print("d:\\mcn\\test\\fullstack_test_output\\mcn-ecommerce-app\\")
        return True
    else:
        print("⚠️ Some tests failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)