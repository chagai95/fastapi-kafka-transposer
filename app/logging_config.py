import logging
import os
from pathlib import Path

def setup_file_logging():
    """Add file logging to existing console logging"""
    # Create logs directory
    log_dir = Path("app/logs")
    log_dir.mkdir(exist_ok=True)
    
    # Add file handler to root logger
    file_handler = logging.FileHandler(log_dir / "app.log")
    file_handler.setLevel(logging.DEBUG)
    
    # Use same format as console
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    logging.info(f"File logging enabled: {log_dir / 'app.log'}")