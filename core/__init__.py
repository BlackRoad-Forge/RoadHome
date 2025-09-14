# Smart Assistant Core Module
# This module contains the core functionality for the smart assistant

__version__ = "2.0.0"
__author__ = "Smart Assistant Team"

from .assistant import SmartAssistant
from .memory import MemoryManager
from .voice import VoiceProcessor
from .vision import VisionProcessor
from .device_controller import DeviceController
from .config_manager import ConfigManager

__all__ = [
    "SmartAssistant",
    "MemoryManager", 
    "VoiceProcessor",
    "VisionProcessor",
    "DeviceController",
    "ConfigManager"
]
