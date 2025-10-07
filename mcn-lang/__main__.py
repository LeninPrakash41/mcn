#!/usr/bin/env python3
"""
MCN Package Entry Point
Allows running MCN with: python -m mcn
"""

import sys
from .core_engine.mcn_cli import main

if __name__ == '__main__':
    sys.exit(main())
