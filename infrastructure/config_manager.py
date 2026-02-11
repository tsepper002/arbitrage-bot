"""Config Manager - Dynamic configuration management"""
import logging
import json
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str = "./config.json"):
        self.config_path = Path(config_path)
        self.config: Dict = {}
        self.load()
        
    def load(self):
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self.config = {}
        else:
            logger.warning(f"Config file {self.config_path} not found, using defaults")
            self.config = self._get_default_config()
            self.save()
            
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
        
    def set(self, key: str, value: Any):
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
            
        config[keys[-1]] = value
        self.save()
        
    def reload(self):
        """Reload configuration from file"""
        self.load()
        logger.info("Configuration reloaded")
        
    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            'trading': {
                'dry_run': True,
                'max_exposure_usdt': 500.0,
                'min_roi_pct': 0.03
            },
            'risk': {
                'max_position_size': 1000.0,
                'stop_loss_pct': 0.05
            },
            'system': {
                'log_level': 'INFO',
                'scan_interval_sec': 30
            }
        }
