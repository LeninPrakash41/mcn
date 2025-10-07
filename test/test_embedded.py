#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, "d:/mcn/mcn")
sys.path.insert(0, "d:/mcn/mcn/plugin")

from mcn.plugin.mcn_embedded import MCNEmbedded


def my_existing_function(name, age):
    """Example existing Python function"""
    return f"Hello {name}, you are {age} years old!"


def calculate_discount(price, discount_percent):
    """Another existing function"""
    return price * (1 - discount_percent / 100)


def main():
    print("Testing MCN Embedded Integration...")

    # Create MCN embedded instance
    mcn = MCNEmbedded()

    # Register existing Python functions
    mcn.register_function("my_function", my_existing_function)
    mcn.register_function("calculate_discount", calculate_discount)

    # Test 1: Simple function call
    script1 = """
    var result = my_function("Alice", 25)
    echo result
    result
    """

    print("\n=== Test 1: Function Registration ===")
    result1 = mcn.execute(script1)
    print(f"Result: {result1}")

    # Test 2: Business logic with context
    script2 = """
    var customer_name = user_name
    var original_price = base_price
    var discount = discount_rate

    var final_price = calculate_discount(original_price, discount)
    var greeting = my_function(customer_name, user_age)

    echo greeting
    echo "Original price: $" + original_price
    echo "Discount: " + discount + "%"
    echo "Final price: $" + final_price

    {"customer": customer_name, "final_price": final_price}
    """

    print("\n=== Test 2: Business Logic with Context ===")
    context = {
        "user_name": "Bob",
        "user_age": 30,
        "base_price": 100,
        "discount_rate": 15,
    }

    result2 = mcn.execute(script2, context)
    print(f"Result: {result2}")

    print("\n=== MCN Embedded Integration Working! ===")


if __name__ == "__main__":
    main()
