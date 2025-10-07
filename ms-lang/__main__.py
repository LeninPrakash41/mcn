#!/usr/bin/env python3
"""
MSL Package Entry Point
Allows running MSL with: python -m msl
"""

import sys
from .core_engine.msl_cli import main

if __name__ == '__main__':
    sys.exit(main())