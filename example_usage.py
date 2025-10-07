#!/usr/bin/env python3
"""
Example demonstrating MSL usage with proper imports
This script can be run from anywhere without path modifications
"""

def example_basic_usage():
    """Basic MSL usage example"""
    print("=== Basic MSL Usage ===")
    
    # Import MSL components
    from msl import MSLInterpreter
    
    # Create interpreter
    interpreter = MSLInterpreter()
    
    # Execute MSL code
    msl_code = '''
var name = "MSL Developer"
var version = "2.0"

echo("Welcome to MSL " + version + "!")
echo("Hello, " + name)

var x = 10
var y = 20
var result = x + y

echo("Calculation: " + x + " + " + y + " = " + result)
    '''
    
    result = interpreter.execute(msl_code, quiet=True)
    print(f"Execution completed. Variables: {list(interpreter.variables.keys())}")

def example_embedded_usage():
    """Embedded MSL usage example"""
    print("\n=== Embedded MSL Usage ===")
    
    # Import embedded MSL
    from msl import MSLEmbedded
    
    # Create embedded instance
    msl = MSLEmbedded()
    
    # Register Python functions
    def calculate_tax(amount, rate=0.1):
        return amount * rate
    
    def format_currency(amount):
        return f"${amount:.2f}"
    
    msl.register_function('calculate_tax', calculate_tax)
    msl.register_function('format_currency', format_currency)
    
    # Execute MSL script with registered functions
    business_script = '''
var order_amount = 100.00
var tax_rate = 0.08

var tax = calculate_tax(order_amount, tax_rate)
var total = order_amount + tax

var formatted_total = format_currency(total)

echo("Order Amount: " + format_currency(order_amount))
echo("Tax: " + format_currency(tax))
echo("Total: " + formatted_total)

formatted_total
    '''
    
    result = msl.execute(business_script, quiet=True)
    print(f"Business calculation result: {result}")

def example_cli_usage():
    """Example of using MSL CLI programmatically"""
    print("\n=== CLI Usage Example ===")
    
    # Create a simple MSL script
    script_content = '''
echo("=== MSL CLI Demo ===")

var greeting = "Hello from MSL CLI!"
echo(greeting)

var data = {
    "message": greeting,
    "timestamp": "2024-01-01",
    "version": "2.0"
}

echo("Data object created with message: " + data.message)
    '''
    
    # Write script to file
    with open('demo_script.msl', 'w') as f:
        f.write(script_content)
    
    print("Created demo_script.msl")
    print("You can run it with: python -m msl run demo_script.msl")
    print("Or serve as API with: python -m msl serve --file demo_script.msl")

def main():
    """Run all examples"""
    print("MSL Usage Examples")
    print("=" * 50)
    
    try:
        example_basic_usage()
        example_embedded_usage()
        example_cli_usage()
        
        print("\n" + "=" * 50)
        print("SUCCESS: All examples completed successfully!")
        print("\nMSL is now properly configured with:")
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

if __name__ == '__main__':
    import sys
    sys.exit(main())