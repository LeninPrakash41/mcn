#!/usr/bin/env python3
"""
Test script to verify MSL imports work correctly
"""

def test_core_imports():
    """Test core MSL imports"""
    print("Testing core MSL imports...")
    
    try:
        from msl import MSLInterpreter, MSLRuntime, MSLServer, MSLEmbedded
        print("[OK] Main package imports successful")
    except ImportError as e:
        print(f"[FAIL] Main package import failed: {e}")
        return False
    
    try:
        from msl.core_engine import MSLInterpreter as CoreInterpreter
        print("[OK] Core engine imports successful")
    except ImportError as e:
        print(f"[FAIL] Core engine import failed: {e}")
        return False
    
    try:
        from msl.plugin import MSLEmbedded as PluginEmbedded
        print("[OK] Plugin imports successful")
    except ImportError as e:
        print(f"[FAIL] Plugin import failed: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Test basic MSL functionality"""
    print("\nTesting basic MSL functionality...")
    
    try:
        from msl import MSLInterpreter
        
        # Create interpreter
        interpreter = MSLInterpreter()
        print("[OK] MSL interpreter created")
        
        # Test simple execution
        result = interpreter.execute('var x = 42', quiet=True)
        if interpreter.variables.get('x') == 42:
            print("[OK] Variable assignment works")
        else:
            print("[FAIL] Variable assignment failed")
            return False
        
        # Test function call
        interpreter.execute('echo("Hello MSL!")', quiet=True)
        print("[OK] Function calls work")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Basic functionality test failed: {e}")
        return False

def test_embedded_integration():
    """Test embedded integration"""
    print("\nTesting embedded integration...")
    
    try:
        from msl import MSLEmbedded
        
        # Create embedded instance
        msl = MSLEmbedded()
        print("[OK] MSL embedded instance created")
        
        # Register a test function
        def test_func(message):
            return f"Test: {message}"
        
        msl.register_function('test_func', test_func)
        print("[OK] Function registration works")
        
        # Test execution
        result = msl.execute('var result = test_func("Hello")', quiet=True)
        if msl.interpreter.variables.get('result') == "Test: Hello":
            print("[OK] Embedded execution works")
        else:
            print("[FAIL] Embedded execution failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Embedded integration test failed: {e}")
        return False

def main():
    """Run all import tests"""
    print("MSL Import Test Suite")
    print("=" * 40)
    
    tests = [
        test_core_imports,
        test_basic_functionality,
        test_embedded_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("SUCCESS: All import tests passed! MSL is properly configured.")
        return 0
    else:
        print("ERROR: Some tests failed. Check the import configuration.")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())