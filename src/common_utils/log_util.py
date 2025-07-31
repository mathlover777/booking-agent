import logging
import os
import sys
from typing import Optional

# Global logger instance
_logger: Optional[logging.Logger] = None

def setup_logging(name: str = None, level: str = None) -> logging.Logger:
    """
    Setup logging configuration for the entire application.
    
    Args:
        name: Logger name (usually __name__ from the calling module)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    global _logger
    
    # Get log level from environment or default to INFO
    log_level = level or os.getenv('LOG_LEVEL', 'INFO')
    
    # Configure root logging if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            stream=sys.stdout
        )
    
    # Create logger for the specific module
    logger_name = name or __name__
    logger = logging.getLogger(logger_name)
    
    # Set the global logger if this is the first call
    if _logger is None:
        _logger = logger
    
    return logger

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance for the specified name.
    
    Args:
        name: Logger name (usually __name__ from the calling module)
    
    Returns:
        Logger instance
    """
    if name is None:
        # Try to get the calling module's name
        import inspect
        frame = inspect.currentframe()
        try:
            # Go up one frame to get the calling module
            caller_frame = frame.f_back
            if caller_frame:
                module_name = caller_frame.f_globals.get('__name__', __name__)
            else:
                module_name = __name__
        finally:
            del frame
        name = module_name
    
    return logging.getLogger(name)

# Initialize logging when module is imported
setup_logging(__name__) 