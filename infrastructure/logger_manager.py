"""Logger Manager - Centralized logging management"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

class LoggerManager:
    def __init__(self, log_dir: str = "./logs", log_level: str = "INFO"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_level = getattr(logging, log_level.upper())
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler
        file_handler = RotatingFileHandler(
            self.log_dir / 'bot.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        logging.info("Logging initialized")
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance"""
        return logging.getLogger(name)
        
    def set_level(self, level: str):
        """Change log level"""
        self.log_level = getattr(logging, level.upper())
        logging.getLogger().setLevel(self.log_level)
        logging.info(f"Log level changed to {level}")
