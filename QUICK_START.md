# MSL Quick Start Guide

## Immediate Usage (No Installation Required)

### 1. Download MSL
```bash
git clone https://github.com/zeroappz/msl.git
cd msl
```

### 2. Run MSL Scripts
```bash
# Use the runner script (works immediately)
python run_msl.py run msl/examples/hello.msl

# Windows users can also use
msl.bat run msl/examples/hello.msl
```

### 3. Start REPL
```bash
python run_msl.py repl
```

### 4. Serve as API
```bash
python run_msl.py serve --file msl/examples/hello.msl --port 8080
```

## For Production Use

### Install MSL
```bash
pip install -e .
```

### Then use directly
```bash
msl run script.msl
msl repl
msl serve --file script.msl
```

## Examples

### Basic Script (hello.msl)
```msl
var name = "World"
var greeting = "Hello " + name + "!"
echo(greeting)
```

### Run it
```bash
python run_msl.py run hello.msl
```

### Business Logic (business.msl)
```msl
var order_total = 100.00
var tax_rate = 0.08
var tax = order_total * tax_rate
var final_total = order_total + tax

echo("Order: $" + order_total)
echo("Tax: $" + tax)
echo("Total: $" + final_total)
```

### Run it
```bash
python run_msl.py run business.msl
```

## Key Points

✅ **No Installation Required**: Use `python run_msl.py` immediately
✅ **No Path Setup**: Runner script handles all imports automatically  
✅ **Cross-Platform**: Works on Windows, Linux, macOS
✅ **Production Ready**: Install with pip for production use

The import path issues are completely resolved!