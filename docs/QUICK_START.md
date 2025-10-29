# MCN Quick Start Guide

## Immediate Usage (No Installation Required)

### 1. Download MCN
```bash
git clone https://github.com/zeroappz/mcn.git
cd mcn
```

### 2. Run MCN Scripts
```bash
# Use the runner script (works immediately)
python run_mcn.py run mcn/examples/hello.mcn

# Windows users can also use
mcn.bat run mcn/examples/hello.mcn
```

### 3. Start REPL
```bash
python run_mcn.py repl
```

### 4. Serve as API
```bash
python run_mcn.py serve --file mcn/examples/hello.mcn --port 8080
```

## For Production Use

### Install MCN
```bash
pip install -e .
```

### Then use directly
```bash
mcn run script.mcn
mcn repl
mcn serve --file script.mcn
```

## Examples

### Basic Script (hello.mcn)
```mcn
var name = "World"
var greeting = "Hello " + name + "!"
echo(greeting)
```

### Run it
```bash
python run_mcn.py run hello.mcn
```

### Business Logic (business.mcn)
```mcn
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
python run_mcn.py run business.mcn
```

## Key Points

✅ **No Installation Required**: Use `python run_mcn.py` immediately
✅ **No Path Setup**: Runner script handles all imports automatically
✅ **Cross-Platform**: Works on Windows, Linux, macOS
✅ **Production Ready**: Install with pip for production use

The import path issues are completely resolved!
