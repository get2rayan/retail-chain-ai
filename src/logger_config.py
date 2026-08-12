import logging
from logging import Logger
import os
import sys
import logging.handlers
from dotenv import load_dotenv

load_dotenv()

def setup_logging(log_level=None, log_file='retail-chain.log', logger_name='retail-chain') -> Logger:
    """
    Configure the logger for the application.
    """
    if log_level is None:
        log_level = logging.DEBUG if (
            os.getenv('DEBUG_MODE','').lower() in ['true', '1', 'yes'] or 
            sys.stdout.isatty()
            ) else logging.INFO
    
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.handlers.clear()  # Clear existing handlers to avoid duplicate logs
    logger.propagate = False  # Prevent log messages from being propagated to the root logger

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Create console handler and set level to debug
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(log_level)
    ch.setFormatter(formatter)

    # Create file handler and set level to INFO
    fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    fh.setLevel(logging.WARNING)
    fh.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger

# Convenience: module-level logger for this package
logger = setup_logging()