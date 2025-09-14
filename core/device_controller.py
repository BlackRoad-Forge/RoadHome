"""
Device Controller Module for Smart Assistant
Handles Home Assistant integration and device control
"""

import paho.mqtt.client as mqtt
import json
import time
import logging
from typing import Dict, List, Any, Optional, Callable
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class DeviceController:
    """Handles device control and Home Assistant integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mqtt_client = None
        self.home_assistant_url = config.get("home_assistant_url", "http://localhost:8123")
        self.home_assistant_token = config.get("home_assistant_token", "")
        self.devices = {}
        self.device_states = {}
        self.status_callbacks = []
        
        # MQTT configuration
        self.mqtt_broker = config.get("mqtt_broker", "localhost")
        self.mqtt_port = config.get("mqtt_port", 1883)
        self.mqtt_username = config.get("mqtt_username", "")
        self.mqtt_password = config.get("mqtt_password", "")
        
        # Topics
        self.topics = {
            "device_control": config.get("device_control_topic", "assistant/devices/control"),
            "device_status": config.get("device_status_topic", "assistant/devices/status"),
            "homeassistant_discovery": "homeassistant/+/+/set"
        }
        
        self._setup_mqtt()
        self._discover_devices()
    
    def _setup_mqtt(self) -> None:
        """Setup MQTT client for device communication"""
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            
            if self.mqtt_username and self.mqtt_password:
                self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            
            logger.info("MQTT client connected for device control")
            
        except Exception as e:
            logger.error(f"Error setting up MQTT: {e}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection"""
        if rc == 0:
            logger.info("Device controller connected to MQTT broker")
            # Subscribe to device control topics
            for topic in self.topics.values():
                client.subscribe(topic)
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            
            if topic == self.topics["device_control"]:
                self._handle_device_control(payload)
            elif topic.startswith("homeassistant/"):
                self._handle_homeassistant_message(topic, payload)
                
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")
    
    def _handle_device_control(self, payload: str) -> None:
        """Handle device control commands"""
        try:
            command = json.loads(payload)
            device_id = command.get("device_id")
            action = command.get("action")
            value = command.get("value")
            
            if device_id and action:
                self.control_device(device_id, action, value)
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in device control message")
        except Exception as e:
            logger.error(f"Error handling device control: {e}")
    
    def _handle_homeassistant_message(self, topic: str, payload: str) -> None:
        """Handle Home Assistant MQTT messages"""
        try:
            # Parse topic: homeassistant/domain/object_id/set
            parts = topic.split('/')
            if len(parts) >= 4:
                domain = parts[1]
                object_id = parts[2]
                action = parts[3]
                
                device_id = f"{domain}.{object_id}"
                
                if action == "set":
                    self.device_states[device_id] = payload
                    self._notify_status_callbacks(device_id, payload)
                    
        except Exception as e:
            logger.error(f"Error handling Home Assistant message: {e}")
    
    def _discover_devices(self) -> None:
        """Discover available devices from Home Assistant"""
        try:
            if not self.home_assistant_token:
                logger.warning("No Home Assistant token provided, skipping device discovery")
                return
            
            headers = {
                "Authorization": f"Bearer {self.home_assistant_token}",
                "Content-Type": "application/json"
            }
            
            # Get all entities
            response = requests.get(f"{self.home_assistant_url}/api/states", headers=headers)
            
            if response.status_code == 200:
                entities = response.json()
                
                for entity in entities:
                    entity_id = entity.get("entity_id", "")
                    if entity_id.startswith(("light.", "switch.", "fan.", "cover.", "climate.")):
                        self.devices[entity_id] = {
                            "name": entity.get("attributes", {}).get("friendly_name", entity_id),
                            "state": entity.get("state"),
                            "domain": entity_id.split('.')[0],
                            "attributes": entity.get("attributes", {}),
                            "last_updated": entity.get("last_updated")
                        }
                
                logger.info(f"Discovered {len(self.devices)} controllable devices")
                
            else:
                logger.error(f"Failed to discover devices: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error discovering devices: {e}")
    
    def control_device(self, device_id: str, action: str, value: Any = None) -> bool:
        """Control a device"""
        try:
            if device_id not in self.devices:
                logger.warning(f"Device {device_id} not found")
                return False
            
            device = self.devices[device_id]
            domain = device["domain"]
            
            # Prepare command based on domain and action
            if domain == "light":
                return self._control_light(device_id, action, value)
            elif domain == "switch":
                return self._control_switch(device_id, action, value)
            elif domain == "fan":
                return self._control_fan(device_id, action, value)
            elif domain == "cover":
                return self._control_cover(device_id, action, value)
            elif domain == "climate":
                return self._control_climate(device_id, action, value)
            else:
                logger.warning(f"Unsupported device domain: {domain}")
                return False
                
        except Exception as e:
            logger.error(f"Error controlling device {device_id}: {e}")
            return False
    
    def _control_light(self, device_id: str, action: str, value: Any) -> bool:
        """Control a light device"""
        try:
            domain, object_id = device_id.split('.', 1)
            
            if action == "turn_on":
                payload = "ON"
            elif action == "turn_off":
                payload = "OFF"
            elif action == "toggle":
                current_state = self.device_states.get(device_id, "OFF")
                payload = "OFF" if current_state == "ON" else "ON"
            elif action == "brightness" and value is not None:
                # For brightness control, we'd need to send JSON payload
                payload = json.dumps({"brightness": int(value)})
            else:
                logger.warning(f"Unsupported light action: {action}")
                return False
            
            topic = f"homeassistant/{domain}/{object_id}/set"
            self.mqtt_client.publish(topic, payload)
            
            # Update local state
            self.device_states[device_id] = payload if action != "brightness" else "ON"
            
            logger.info(f"Light {device_id} {action}: {payload}")
            return True
            
        except Exception as e:
            logger.error(f"Error controlling light {device_id}: {e}")
            return False
    
    def _control_switch(self, device_id: str, action: str, value: Any) -> bool:
        """Control a switch device"""
        try:
            domain, object_id = device_id.split('.', 1)
            
            if action == "turn_on":
                payload = "ON"
            elif action == "turn_off":
                payload = "OFF"
            elif action == "toggle":
                current_state = self.device_states.get(device_id, "OFF")
                payload = "OFF" if current_state == "ON" else "ON"
            else:
                logger.warning(f"Unsupported switch action: {action}")
                return False
            
            topic = f"homeassistant/{domain}/{object_id}/set"
            self.mqtt_client.publish(topic, payload)
            
            # Update local state
            self.device_states[device_id] = payload
            
            logger.info(f"Switch {device_id} {action}: {payload}")
            return True
            
        except Exception as e:
            logger.error(f"Error controlling switch {device_id}: {e}")
            return False
    
    def _control_fan(self, device_id: str, action: str, value: Any) -> bool:
        """Control a fan device"""
        try:
            domain, object_id = device_id.split('.', 1)
            
            if action == "turn_on":
                payload = "ON"
            elif action == "turn_off":
                payload = "OFF"
            elif action == "speed" and value is not None:
                payload = json.dumps({"speed": str(value)})
            else:
                logger.warning(f"Unsupported fan action: {action}")
                return False
            
            topic = f"homeassistant/{domain}/{object_id}/set"
            self.mqtt_client.publish(topic, payload)
            
            logger.info(f"Fan {device_id} {action}: {payload}")
            return True
            
        except Exception as e:
            logger.error(f"Error controlling fan {device_id}: {e}")
            return False
    
    def _control_cover(self, device_id: str, action: str, value: Any) -> bool:
        """Control a cover device"""
        try:
            domain, object_id = device_id.split('.', 1)
            
            if action == "open":
                payload = "OPEN"
            elif action == "close":
                payload = "CLOSE"
            elif action == "stop":
                payload = "STOP"
            elif action == "position" and value is not None:
                payload = json.dumps({"position": int(value)})
            else:
                logger.warning(f"Unsupported cover action: {action}")
                return False
            
            topic = f"homeassistant/{domain}/{object_id}/set"
            self.mqtt_client.publish(topic, payload)
            
            logger.info(f"Cover {device_id} {action}: {payload}")
            return True
            
        except Exception as e:
            logger.error(f"Error controlling cover {device_id}: {e}")
            return False
    
    def _control_climate(self, device_id: str, action: str, value: Any) -> bool:
        """Control a climate device"""
        try:
            domain, object_id = device_id.split('.', 1)
            
            if action == "set_temperature":
                payload = json.dumps({"temperature": float(value)})
            elif action == "set_mode":
                payload = json.dumps({"mode": str(value)})
            elif action == "turn_on":
                payload = "ON"
            elif action == "turn_off":
                payload = "OFF"
            else:
                logger.warning(f"Unsupported climate action: {action}")
                return False
            
            topic = f"homeassistant/{domain}/{object_id}/set"
            self.mqtt_client.publish(topic, payload)
            
            logger.info(f"Climate {device_id} {action}: {payload}")
            return True
            
        except Exception as e:
            logger.error(f"Error controlling climate {device_id}: {e}")
            return False
    
    def get_device_status(self, device_id: str) -> Optional[Dict]:
        """Get current status of a device"""
        return self.devices.get(device_id)
    
    def get_all_devices(self) -> Dict[str, Dict]:
        """Get all discovered devices"""
        return self.devices.copy()
    
    def get_device_states(self) -> Dict[str, str]:
        """Get current device states"""
        return self.device_states.copy()
    
    def add_status_callback(self, callback: Callable) -> None:
        """Add callback for device status changes"""
        self.status_callbacks.append(callback)
    
    def _notify_status_callbacks(self, device_id: str, state: str) -> None:
        """Notify all status callbacks of device state change"""
        for callback in self.status_callbacks:
            try:
                callback(device_id, state)
            except Exception as e:
                logger.error(f"Error in device status callback: {e}")
    
    def refresh_devices(self) -> None:
        """Refresh device list from Home Assistant"""
        self._discover_devices()
    
    def cleanup(self) -> None:
        """Clean up resources"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        logger.info("Device controller cleaned up")
