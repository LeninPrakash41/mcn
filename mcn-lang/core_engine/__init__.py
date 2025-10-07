"""
MCN Core Engine Package
Main components of the MCN interpreter and runtime
"""

from .mcn_interpreter import MCNInterpreter
from .mcn_runtime import MCNRuntime
from .mcn_logger import mcn_logger, log_error, log_step, log_performance
from .mcn_server import MCNServer, serve_script, serve_directory
from .mcn_extensions import (
    MCNAIContext,
    MCNPackageManager,
    MCNAsyncRuntime,
    MCNTypeChecker,
    create_db_package,
    create_http_package,
    create_ai_package
)
from .mcn_project_manager import mcn_project_manager
from .mcn_frontend import mcn_frontend

__version__ = "2.0.0"
__all__ = [
    'MCNInterpreter',
    'MCNRuntime',
    'MCNServer',
    'serve_script',
    'serve_directory',
    'mcn_logger',
    'log_error',
    'log_step',
    'log_performance',
    'MCNAIContext',
    'MCNPackageManager',
    'MCNAsyncRuntime',
    'MCNTypeChecker',
    'create_db_package',
    'create_http_package',
    'create_ai_package',
    'mcn_project_manager',
    'mcn_frontend'
]
