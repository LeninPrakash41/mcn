"""
MSL (Macincode Scripting Language) Package
A business automation scripting language with AI integration
"""

from .core_engine import MSLInterpreter, MSLRuntime, MSLServer
from .plugin.msl_embedded import MSLEmbedded

__version__ = "2.0.0"
__author__ = "MSL Development Team"
__description__ = "Business automation scripting language with AI integration"

__all__ = [
    'MSLInterpreter',
    'MSLRuntime', 
    'MSLServer',
    'MSLEmbedded'
]