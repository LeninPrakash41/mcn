"""
MCN (Macincode Scripting Language) Package
A business automation scripting language with AI integration
"""

try:
    from .core_engine.mcn_interpreter import MCNInterpreter
    from .core_engine.mcn_runtime import MCNRuntime
    from .core_engine.mcn_server import MCNServer
    from .plugin.mcn_embedded import MCNEmbedded
except ImportError:
    # Fallback for development
    pass

__version__ = "2.0.0"
__author__ = "MCN Development Team"
__description__ = "Business automation scripting language with AI integration"

__all__ = ["MCNInterpreter", "MCNRuntime", "MCNServer", "MCNEmbedded"]
