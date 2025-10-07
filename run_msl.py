#!/usr/bin/env python3
"""
MSL Runner Script - Handles direct execution without import issues
"""

import sys
import os

# Add MSL to Python path
msl_path = os.path.dirname(os.path.abspath(__file__))
if msl_path not in sys.path:
    sys.path.insert(0, msl_path)

# Import and run MSL CLI
from msl.core_engine.msl_cli import main

if __name__ == '__main__':
    sys.exit(main())