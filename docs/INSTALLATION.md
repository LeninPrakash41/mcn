# MCN Installation Guide

## Fixed Import Paths - No More Manual Path Configuration!

MCN now uses proper Python package structure with relative imports. Developers no longer need to modify paths manually.

## Installation Options

### Option 1: Development Installation (Recommended)
```bash
# Clone or download MCN
cd d:\mcn

# Install in development mode
pip install -e .
```

### Option 2: Direct Installation
```bash
# Install from source
cd d:\mcn
pip install .
```

### Option 3: Use Without Installation
```bash
# Method 1: Use runner script (Recommended)
python run_mcn.py run script.mcn

# Method 2: Add MCN to Python path temporarily
export PYTHONPATH="d:\mcn:$PYTHONPATH"  # Linux/Mac
set PYTHONPATH=d:\mcn;%PYTHONPATH%      # Windows
python -m mcn run script.mcn

# Method 3: Use in Python code
import sys
sys.path.insert(0, 'd:/mcn')
from mcn import MCNInterpreter
```

## Usage Options

### Command Line Interface

**After Installation:**
```bash
# Run MCN script
mcn run script.mcn

# Start REPL
mcn repl

# Serve as API
mcn serve --file script.mcn --port 8080

# Initialize new project
mcn init my_project --frontend react
```

**Without Installation (Direct Usage):**
```bash
# Use the runner script
python run_mcn.py run script.mcn

# Or use module execution
python -m mcn run script.mcn  # (requires PYTHONPATH setup)

# Windows batch file
mcn.bat run script.mcn
```

### Python Integration
```python
# Import MCN components
from mcn import MCNInterpreter, MCNEmbedded, MCNServer

# Basic usage
interpreter = MCNInterpreter()
result = interpreter.execute('var x = 42')

# Embedded usage
mcn = MCNEmbedded()
mcn.register_function('my_func', lambda x: x * 2)
result = mcn.execute('var result = my_func(21)')
```

## Key Improvements

✅ **Proper Package Structure**: All modules use relative imports
✅ **No Hardcoded Paths**: Works from any directory
✅ **Standard Python Packaging**: Uses setup.py and proper entry points
✅ **Cross-Platform**: Works on Windows, Linux, and macOS
✅ **IDE Friendly**: Proper imports work with IDEs and linters

## Verification

Test that imports work correctly:
```bash
python test_imports.py
```

Test usage examples:
```bash
python example_usage.py
```

## Migration from Old Version

If you were using MCN with manual path modifications:

**Before (Required manual path setup):**
```python
import sys
sys.path.insert(0, 'd:/mcn/mcn')  # Manual path
from mcn_interpreter import MCNInterpreter
```

**After (Clean imports):**
```python
from mcn import MCNInterpreter  # Clean import
```

## Package Structure

```
mcn/
├── __init__.py                 # Main package
├── __main__.py                 # Entry point for python -m mcn
├── core_engine/                # Core MCN components
│   ├── __init__.py
│   ├── mcn_interpreter.py      # Main interpreter
│   ├── mcn_runtime.py          # Runtime functions
│   ├── mcn_server.py           # API server
│   ├── mcn_cli.py              # Command line interface
│   └── ...
├── plugin/                     # Integration plugins
│   ├── __init__.py
│   └── mcn_embedded.py         # Embedded integration
└── examples/                   # Example scripts
    └── *.mcn
```

## Troubleshooting

**Import Error**: If you get import errors, ensure MCN is in your Python path or install it with pip.

**Path Issues**: The new version eliminates all hardcoded paths. If you see path-related errors, you might be using old code.

**CLI Not Found**: After installation, `mcn` command should be available. If not, try `python -m mcn` instead.
