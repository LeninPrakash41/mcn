#!/usr/bin/env python3
"""
Example demonstrating MCN usage with proper imports
This script can be run from anywhere without path modifications
"""


def example_basic_usage():
    """Basic MCN usage example"""
    print("=== Basic MCN Usage ===")

    # Import MCN components
    from mcn import MCNInterpreter

    # Create interpreter
    interpreter = MCNInterpreter()

    # Execute MCN code
    mcn_code = """
var name = "MCN Developer"
var version = "2.0"

echo("Welcome to MCN " + version + "!")
echo("Hello, " + name)

var x = 10
var y = 20
var result = x + y

echo("Calculation: " + x + " + " + y + " = " + result)
    """

    result = interpreter.execute(mcn_code, quiet=True)
    print(f"Execution completed. Variables: {list(interpreter.variables.keys())}")


def example_embedded_usage():
    """Embedded MCN usage example"""
    print("\n=== Embedded MCN Usage ===")

    # Import embedded MCN
    from mcn import MCNEmbedded

    # Create embedded instance
    mcn = MCNEmbedded()

    # Register Python functions
    def calculate_tax(amount, rate=0.1):
        return amount * rate

    def format_currency(amount):
        return f"${amount:.2f}"

    mcn.register_function("calculate_tax", calculate_tax)
    mcn.register_function("format_currency", format_currency)

    # Execute MCN script with registered functions
    business_script = """
var order_amount = 100.00
var tax_rate = 0.08

var tax = calculate_tax(order_amount, tax_rate)
var total = order_amount + tax

var formatted_total = format_currency(total)

echo("Order Amount: " + format_currency(order_amount))
echo("Tax: " + format_currency(tax))
echo("Total: " + formatted_total)

formatted_total
    """

    result = mcn.execute(business_script, quiet=True)
    print(f"Business calculation result: {result}")


def example_cli_usage():
    """Example of using MCN CLI programmatically"""
    print("\n=== CLI Usage Example ===")

    # Create a simple MCN script
    script_content = """
echo("=== MCN CLI Demo ===")

var greeting = "Hello from MCN CLI!"
echo(greeting)

var data = {
    "message": greeting,
    "timestamp": "2025-10-01",
    "version": "2.0"
}

echo("Data object created with message: " + data.message)
    """

    # Write script to file
    with open("demo_script.mcn", "w") as f:
        f.write(script_content)

    print("Created demo_script.mcn")
    print("You can run it with: python -m mcn run demo_script.mcn")
    print("Or serve as API with: python -m mcn serve --file demo_script.mcn")


def main():
    """Run all examples"""
    print("MCN Usage Examples")
    print("=" * 50)

    try:
        example_basic_usage()
        example_embedded_usage()
        example_cli_usage()

        print("\n" + "=" * 50)
        print("SUCCESS: All examples completed successfully!")
        print("\nMCN is now properly configured with:")
        print("- Proper package structure")
        print("- Relative imports")
        print("- No hardcoded paths")
        print("- Works from any directory")

    except Exception as e:
        print(f"\nERROR: Example failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
