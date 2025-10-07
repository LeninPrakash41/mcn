#!/usr/bin/env python3
"""
Basic MCN functionality tests
"""

from mcn.core_engine.mcn_interpreter import MCNInterpreter


def test_basic_variables():
    """Test basic variable operations"""
    interpreter = MCNInterpreter()

    # Test variable assignment
    interpreter.execute("var x = 10", quiet=True)
    assert interpreter.variables["x"] == 10

    # Test string variables
    interpreter.execute('var name = "MCN"', quiet=True)
    assert interpreter.variables["name"] == "MCN"


def test_basic_functions():
    """Test basic built-in functions"""
    interpreter = MCNInterpreter()

    # Test log function (should not raise error)
    interpreter.execute('log("Hello MCN!")', quiet=True)

    # Test echo function - it prints but doesn't return
    interpreter.execute('echo("Test")', quiet=True)
    # Just verify no exception was raised


def test_arithmetic():
    """Test basic arithmetic operations"""
    interpreter = MCNInterpreter()

    interpreter.execute("var a = 5", quiet=True)
    interpreter.execute("var b = 3", quiet=True)
    interpreter.execute("var sum = a + b", quiet=True)

    assert interpreter.variables["sum"] == 8


def test_string_operations():
    """Test string concatenation"""
    interpreter = MCNInterpreter()

    interpreter.execute('var first = "Hello"', quiet=True)
    interpreter.execute('var second = "World"', quiet=True)
    interpreter.execute('var greeting = first + " " + second', quiet=True)

    assert interpreter.variables["greeting"] == "Hello World"


if __name__ == "__main__":
    test_basic_variables()
    test_basic_functions()
    test_arithmetic()
    test_string_operations()
    print("✅ All basic tests passed!")
