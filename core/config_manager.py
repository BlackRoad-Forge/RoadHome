"""
Configuration Manager for Smart Assistant
Handles loading, validation, and management of configuration settings
"""

import yaml
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration for the smart assistant system"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as file:
                    self.config = yaml.safe_load(file) or {}
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                logger.warning(f"Config file {self.config_path} not found, using defaults")
                self._create_default_config()
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self._create_default_config()
    
    def _create_default_config(self) -> None:
        """Create default configuration if none exists"""
        self.config = {
            "system": {
                "name": "Smart Assistant",
                "version": "2.0.0",
                "debug": True,
                "log_level": "INFO",
                "data_dir": "/home/pi/smart-assistant-data"
            },
            "mqtt": {
                "broker": "localhost",
                "port": 1883,
                "username": "",
                "password": ""
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get("mqtt.broker") -> "localhost"
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation
        Example: config.set("mqtt.broker", "192.168.1.100")
        """
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the value
        config[keys[-1]] = value
    
    def save(self) -> None:
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as file:
                yaml.dump(self.config, file, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def validate(self) -> bool:
        """Validate configuration for required fields"""
        required_fields = [
            "system.name",
            "mqtt.broker",
            "mqtt.port"
        ]
        
        for field in required_fields:
            if self.get(field) is None:
                logger.error(f"Required configuration field missing: {field}")
                return False
        
        return True
    
    def get_mqtt_config(self) -> Dict[str, Any]:
        """Get MQTT configuration"""
        return {
            "broker": self.get("mqtt.broker", "localhost"),
            "port": self.get("mqtt.port", 1883),
            "username": self.get("mqtt.username", ""),
            "password": self.get("mqtt.password", ""),
            "topics": self.get("mqtt.topics", {})
        }
    
    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI configuration"""
        return {
            "llm": self.get("ai.llm", {}),
            "voice": self.get("ai.voice", {}),
            "vision": self.get("ai.vision", {})
        }
    
    def get_hardware_config(self) -> Dict[str, Any]:
        """Get hardware configuration"""
        return {
            "hailo": self.get("hardware.hailo", {}),
            "camera": self.get("hardware.camera", {}),
            "audio": self.get("hardware.audio", {}),
            "zbt_dongle": self.get("hardware.zbt_dongle", {})
        }
