# MSL Installation Guide

## Fixed Import Paths - No More Manual Path Configuration!

MSL now uses proper Python package structure with relative imports. Developers no longer need to modify paths manually.

## Installation Options

### Option 1: Development Installation (Recommended)
```bash
# Clone or download MSL
cd d:\msl

# Install in development mode
pip install -e .
```

### Option 2: Direct Installation
```bash
# Install from source
cd d:\msl
pip install .
```

### Option 3: Use Without Installation
```bash
# Method 1: Use runner script (Recommended)
python run_msl.py run script.msl

# Method 2: Add MSL to Python path temporarily
export PYTHONPATH="d:\msl:$PYTHONPATH"  # Linux/Mac
set PYTHONPATH=d:\msl;%PYTHONPATH%      # Windows
python -m msl run script.msl

# Method 3: Use in Python code
import sys
sys.path.insert(0, 'd:/msl')
from msl import MSLInterpreter
```

## Usage Options

### Command Line Interface

**After Installation:**
```bash
# Run MSL script
msl run script.msl

# Start REPL
msl repl

# Serve as API
msl serve --file script.msl --port 8080

# Initialize new project
msl init my_project --frontend react
```

**Without Installation (Direct Usage):**
```bash
# Use the runner script
python run_msl.py run script.msl

# Or use module execution
python -m msl run script.msl  # (requires PYTHONPATH setup)

# Windows batch file
msl.bat run script.msl
```

### Python Integration
```python
# Import MSL components
from msl import MSLInterpreter, MSLEmbedded, MSLServer

# Basic usage
interpreter = MSLInterpreter()
result = interpreter.execute('var x = 42')

# Embedded usage
msl = MSLEmbedded()
msl.register_function('my_func', lambda x: x * 2)
result = msl.execute('var result = my_func(21)')
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

If you were using MSL with manual path modifications:

**Before (Required manual path setup):**
```python
import sys
sys.path.insert(0, 'd:/msl/msl')  # Manual path
from msl_interpreter import MSLInterpreter
```

**After (Clean imports):**
```python
from msl import MSLInterpreter  # Clean import
```

## Package Structure

```
msl/
├── __init__.py                 # Main package
├── __main__.py                 # Entry point for python -m msl
├── core_engine/                # Core MSL components
│   ├── __init__.py
│   ├── msl_interpreter.py      # Main interpreter
│   ├── msl_runtime.py          # Runtime functions
│   ├── msl_server.py           # API server
│   ├── msl_cli.py              # Command line interface
│   └── ...
├── plugin/                     # Integration plugins
│   ├── __init__.py
│   └── msl_embedded.py         # Embedded integration
└── examples/                   # Example scripts
    └── *.msl
```

## Troubleshooting

**Import Error**: If you get import errors, ensure MSL is in your Python path or install it with pip.

**Path Issues**: The new version eliminates all hardcoded paths. If you see path-related errors, you might be using old code.

**CLI Not Found**: After installation, `msl` command should be available. If not, try `python -m msl` instead.