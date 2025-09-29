# core/logging_config.py
"""
Centralized logging configuration (fixed for Windows, emojis, no duplicate logs)
"""
import logging
import sys
import os
from datetime import datetime

def setup_logging(level=logging.INFO) -> logging.Logger:
    """Setup application logging (console + file, UTF-8, no duplicate handlers)"""
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler using UTF-8
    console_handler = logging.StreamHandler(sys.stdout)
    if hasattr(console_handler.stream, "reconfigure"):  # Python 3.7+
        console_handler.stream.reconfigure(encoding="utf-8")
    console_handler.setFormatter(formatter)

    # File handler
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler(
        f"logs/app_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # ✅ Add handlers only if none exist to prevent duplicate logs
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    return root_logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module"""
    return logging.getLogger(name)
