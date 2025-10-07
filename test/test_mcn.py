#!/usr/bin/env python3
"""
Test script for MCN (Macincode Scripting Language)
"""

from mcn.core_engine.mcn_interpreter import MCNInterpreter


def test_basic_operations():
    print("Testing basic MCN operations...")

    interpreter = MCNInterpreter()

    # Test variable assignment
    result = interpreter.execute("var x = 10")
    assert interpreter.variables["x"] == 10

    # Test arithmetic
    result = interpreter.execute("var y = x + 5")
    assert interpreter.variables["y"] == 15

    # Test string operations
    result = interpreter.execute('var name = "MCN"')
    result = interpreter.execute('var greeting = "Hello " + name')
    assert interpreter.variables["greeting"] == "Hello MCN"

    # Test conditionals
    interpreter.execute(
        """
        var age = 25
        if age > 18
            var status = "adult"
        else
            var status = "minor"
    """
    )
    assert interpreter.variables["status"] == "adult"

    print("✓ Basic operations test passed")


def test_functions():
    print("Testing MCN built-in functions...")

    interpreter = MCNInterpreter()

    # Test log function
    interpreter.execute('log("Hello from MCN!")')

    # Test AI function (mock response)
    result = interpreter.execute('var response = ai("Test prompt")')
    assert "Test prompt" in interpreter.variables["response"]

    print("✓ Functions test passed")


def test_database_operations():
    print("Testing database operations...")

    interpreter = MCNInterpreter()

    # Test database query
    interpreter.execute('var users = query("SELECT * FROM users")')

    # Test insert
    interpreter.execute(
        """
        var name = "Test User"
        var email = "test@example.com"
        query("INSERT INTO users (name, email, age) VALUES (?, ?, ?)", (name, email, 30))
    """
    )

    print("✓ Database operations test passed")


def test_error_handling():
    print("Testing error handling...")

    interpreter = MCNInterpreter()

    # Test try-catch
    interpreter.execute(
        """
        try
            var result = 10 / 0
        catch
            var error_handled = true
    """
    )

    assert interpreter.variables.get("error_handled") == True

    print("✓ Error handling test passed")


def test_loops():
    print("Testing loops...")

    interpreter = MCNInterpreter()

    # Test while loop
    interpreter.execute(
        """
        var counter = 0
        var sum = 0
        while counter < 5
            sum = sum + counter
            counter = counter + 1
    """
    )

    assert interpreter.variables["sum"] == 10  # 0+1+2+3+4
    assert interpreter.variables["counter"] == 5

    print("✓ Loops test passed")


def run_example_script():
    print("Running example script...")

    example_code = """
        log "=== MCN Demo Script ==="

        var user_name = "Alice"
        var user_age = 28

        log "User: " + user_name + ", Age: " + user_age

        if user_age >= 18
            log user_name + " is an adult"
            var can_vote = true
        else
            log user_name + " is a minor"
            var can_vote = false

        var counter = 1
        while counter <= 3
            log "Count: " + counter
            counter = counter + 1

        var ai_response = ai("Generate a welcome message for " + user_name)
        log "AI Response: " + ai_response

        log "=== Demo Complete ==="
    """

    interpreter = MCNInterpreter()
    interpreter.execute(example_code)

    print("✓ Example script executed successfully")


if __name__ == "__main__":
    print("MCN (Macincode Scripting Language) Test Suite")
    print("=" * 50)

    try:
        test_basic_operations()
        test_functions()
        test_database_operations()
        test_error_handling()
        test_loops()
        run_example_script()

        print("\n" + "=" * 50)
        print("🎉 All tests passed! MCN is working correctly.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
