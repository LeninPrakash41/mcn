"""
MCN Enhanced Logging System
Provides comprehensive error tracking and developer-friendly debugging
"""

import logging
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import sys

class MCNLogger:
    """Enhanced logging system for MCN with developer-friendly error messages"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Setup different log files
        self.setup_loggers()

    def setup_loggers(self):
        """Setup different loggers for different purposes"""

        # Main MCN logger
        self.mcn_logger = logging.getLogger('mcn')
        self.mcn_logger.setLevel(logging.DEBUG)

        # Error logger for critical issues
        self.error_logger = logging.getLogger('mcn.errors')
        self.error_logger.setLevel(logging.ERROR)

        # Developer logger for debugging
        self.dev_logger = logging.getLogger('mcn.dev')
        self.dev_logger.setLevel(logging.DEBUG)

        # Setup handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup file and console handlers"""

        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)

        # File handlers
        error_handler = logging.FileHandler(self.log_dir / 'mcn_errors.log')
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        error_handler.setFormatter(error_formatter)

        debug_handler = logging.FileHandler(self.log_dir / 'mcn_debug.log')
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
        )
        debug_handler.setFormatter(debug_formatter)

        # Add handlers to loggers
        self.mcn_logger.addHandler(console_handler)
        self.mcn_logger.addHandler(debug_handler)
        self.error_logger.addHandler(error_handler)
        self.dev_logger.addHandler(debug_handler)

    def log_mcn_error(self, error_type: str, message: str, context: Dict[str, Any] = None,
                      line_number: int = None, file_path: str = None):
        """Log MCN-specific errors with context"""

        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'message': message,
            'context': context or {},
            'line_number': line_number,
            'file_path': file_path,
            'traceback': traceback.format_exc() if sys.exc_info()[0] else None
        }

        # Log to error file
        self.error_logger.error(json.dumps(error_data, indent=2))

        # Developer-friendly console output
        self._print_developer_error(error_data)

    def _print_developer_error(self, error_data: Dict[str, Any]):
        """Print developer-friendly error messages"""

        print("\n" + "="*60)
        print("MCN ERROR DETECTED")
        print("="*60)
        print(f"Error Type: {error_data['error_type']}")
        print(f"Message: {error_data['message']}")

        if error_data.get('file_path'):
            print(f"File: {error_data['file_path']}")
        if error_data.get('line_number'):
            print(f"Line: {error_data['line_number']}")

        if error_data.get('context'):
            print("\nContext:")
            for key, value in error_data['context'].items():
                print(f"  {key}: {value}")

        print("\nDEVELOPER TIPS:")
        self._provide_error_tips(error_data['error_type'])
        print("="*60 + "\n")

    def _provide_error_tips(self, error_type: str):
        """Provide helpful tips based on error type"""

        tips = {
            'SYNTAX_ERROR': [
                "Check for missing quotes, parentheses, or semicolons",
                "Verify MCN syntax matches the documentation",
                "Use MCN IDE extension for syntax highlighting"
            ],
            'RUNTIME_ERROR': [
                "Check if all variables are properly defined",
                "Verify database connections and API endpoints",
                "Ensure all required packages are installed"
            ],
            'DATABASE_ERROR': [
                "Verify database connection string",
                "Check if tables exist and have correct schema",
                "Ensure database user has proper permissions"
            ],
            'API_ERROR': [
                "Check API endpoint URLs and authentication",
                "Verify request payload format",
                "Check network connectivity"
            ],
            'AI_ERROR': [
                "Verify AI service configuration",
                "Check API keys and rate limits",
                "Ensure prompt format is correct"
            ]
        }

        error_tips = tips.get(error_type, ["Check MCN documentation for guidance"])
        for tip in error_tips:
            print(f"  - {tip}")

    def log_execution_step(self, step: str, details: Dict[str, Any] = None):
        """Log execution steps for debugging"""
        self.dev_logger.info(f"STEP: {step}", extra={'details': details or {}})

    def log_performance(self, operation: str, duration: float, details: Dict[str, Any] = None):
        """Log performance metrics"""
        perf_data = {
            'operation': operation,
            'duration_ms': duration * 1000,
            'details': details or {}
        }
        self.dev_logger.info(f"PERFORMANCE: {json.dumps(perf_data)}")

    def log_warning(self, message: str, context: Dict[str, Any] = None):
        """Log warnings with context"""
        self.mcn_logger.warning(f"{message} | Context: {json.dumps(context or {})}")

# Global logger instance
mcn_logger = MCNLogger()

def log_error(error_type: str, message: str, **kwargs):
    """Convenience function for logging errors"""
    mcn_logger.log_mcn_error(error_type, message, **kwargs)

def log_step(step: str, **kwargs):
    """Convenience function for logging execution steps"""
    mcn_logger.log_execution_step(step, kwargs)

def log_performance(operation: str, duration: float, **kwargs):
    """Convenience function for logging performance"""
    mcn_logger.log_performance(operation, duration, kwargs)
