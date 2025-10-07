"""
MSL Core Engine Package
Main components of the MSL interpreter and runtime
"""

from .msl_interpreter import MSLInterpreter
from .msl_runtime import MSLRuntime
from .msl_logger import msl_logger, log_error, log_step, log_performance
from .msl_server import MSLServer, serve_script, serve_directory
from .msl_extensions import (
    MSLAIContext, 
    MSLPackageManager, 
    MSLAsyncRuntime, 
    MSLTypeChecker,
    create_db_package,
    create_http_package,
    create_ai_package
)
from .msl_project_manager import msl_project_manager
from .msl_frontend import msl_frontend

__version__ = "2.0.0"
__all__ = [
    'MSLInterpreter',
    'MSLRuntime', 
    'MSLServer',
    'serve_script',
    'serve_directory',
    'msl_logger',
    'log_error',
    'log_step', 
    'log_performance',
    'MSLAIContext',
    'MSLPackageManager',
    'MSLAsyncRuntime',
    'MSLTypeChecker',
    'create_db_package',
    'create_http_package', 
    'create_ai_package',
    'msl_project_manager',
    'msl_frontend'
]