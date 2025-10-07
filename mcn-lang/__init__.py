"""
MCN (Macincode Scripting Language) Package
A business automation scripting language with AI integration
"""

from .core_engine import MSNInterpreter, MSNRuntime, MSNServer
from .plugin.mcn_embedded import MSNEmbedded

__version__ = "2.0.0"
__author__ = "MCN Development Team"
__description__ = "Business automation scripting language with AI integration"

__all__ = [
    'MSNInterpreter',
    'MSNRuntime',
    'MSNServer',
    'MSNEmbedded'
]
