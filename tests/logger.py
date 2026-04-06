import logging
import sys
import os

def get_logger(name: str = "bus_pipeline") -> logging.Logger:
    """
    Creates and configures a simple console logger.
    If the logger already exists, it returns the existing instance 
    to prevent duplicate log messages.
    
    Args:
        name (str): The name of the logger.
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    
    # If the logger doesn't have handlers built yet, configure it
    if not logger.handlers:
        # Fallback to DEBUG if specified in environment, else INFO
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # StreamHandler outputs to the console
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Simple, readable format
        formatter = logging.Formatter(
            fmt='[%(asctime)s] %(levelname)s - %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
        # Disable propagating to the root logger to avoid terminal spam
        logger.propagate = False

    return logger

