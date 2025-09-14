"""
Main HailoHome Class
Orchestrates all components and provides the main interface
"""

import logging
import threading
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from .config_manager import ConfigManager
from .memory import MemoryManager
from .voice import VoiceProcessor
from .vision import VisionProcessor
from .device_controller import DeviceController

# Try to import AI dependencies
try:
    from langchain_ollama.llms import OllamaLLM
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain_core.tools import tool
    from langchain import hub
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("AI dependencies not available, using fallback")

logger = logging.getLogger(__name__)

class SmartAssistant:
    """Main HailoHome class that orchestrates all components"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_ai_config()
        
        # Initialize components
        self.memory = MemoryManager(
            self.config_manager.get("memory.database_path", "memory.db")
        )
        
        self.voice = VoiceProcessor(
            self.config_manager.get_hardware_config().get("audio", {})
        )
        
        self.vision = VisionProcessor(
            self.config_manager.get_hardware_config().get("camera", {})
        )
        
        self.device_controller = DeviceController(
            self.config_manager.get("home_assistant", {})
        )
        
        # AI Agent
        self.agent = None
        self._setup_ai_agent()
        
        # State management
        self.is_running = False
        self.current_session_id = str(uuid.uuid4())
        self.conversation_context = []
        
        # Event handlers
        self.event_handlers = {
            "voice_input": [],
            "vision_event": [],
            "device_status": [],
            "system_event": []
        }
        
        # Setup component callbacks
        self._setup_callbacks()
        
        logger.info("HailoHome initialized")
    
    def _setup_ai_agent(self) -> None:
        """Setup the AI agent with tools and capabilities"""
        if not AI_AVAILABLE:
            logger.warning("AI not available, using fallback responses")
            return
        
        try:
            # Initialize LLM
            llm_config = self.config.get("llm", {})
            llm = OllamaLLM(
                model=llm_config.get("model", "qwen2.5:3b-instruct-q4_K_M"),
                temperature=llm_config.get("temperature", 0.7)
            )
            
            # Define tools for the agent
            tools = [
                self._create_device_control_tool(),
                self._create_memory_tool(),
                self._create_vision_query_tool(),
                self._create_system_status_tool()
            ]
            
            # Create agent
            prompt = hub.pull("hwchase17/react")
            agent = create_react_agent(llm, tools, prompt)
            self.agent = AgentExecutor(agent=agent, tools=tools, verbose=True)
            
            logger.info("AI agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Error setting up AI agent: {e}")
            self.agent = None
    
    def _create_device_control_tool(self):
        """Create tool for device control"""
        @tool
        def control_device(device_id: str, action: str, value: str = None) -> str:
            """Control a smart home device. 
            device_id: The ID of the device (e.g., 'light.living_room')
            action: The action to perform (e.g., 'turn_on', 'turn_off', 'toggle')
            value: Optional value for the action (e.g., brightness level)
            """
            try:
                success = self.device_controller.control_device(device_id, action, value)
                if success:
                    return f"Successfully {action} {device_id}"
                else:
                    return f"Failed to {action} {device_id}"
            except Exception as e:
                return f"Error controlling device: {str(e)}"
        
        return control_device
    
    def _create_memory_tool(self):
        """Create tool for memory operations"""
        @tool
        def query_memory(query: str) -> str:
            """Query the assistant's memory for information.
            query: What you want to know from memory
            """
            try:
                # Search recent conversations
                conversations = self.memory.get_recent_conversations(limit=5)
                
                # Search learned patterns
                patterns = self.memory.get_learned_patterns()
                
                # Simple keyword matching for now
                relevant_info = []
                query_lower = query.lower()
                
                for conv in conversations:
                    if any(word in conv["user_input"].lower() for word in query_lower.split()):
                        relevant_info.append(f"Previous conversation: {conv['user_input']} -> {conv['assistant_response']}")
                
                if relevant_info:
                    return "\n".join(relevant_info[:3])  # Return top 3 matches
                else:
                    return "No relevant information found in memory"
                    
            except Exception as e:
                return f"Error querying memory: {str(e)}"
        
        return query_memory
    
    def _create_vision_query_tool(self):
        """Create tool for vision queries"""
        @tool
        def get_vision_info() -> str:
            """Get current information from the camera/vision system.
            Returns what the assistant can currently see.
            """
            try:
                # Get current frame
                frame = self.vision.capture_frame()
                if frame is None:
                    return "Camera not available"
                
                # Get camera info
                camera_info = self.vision.get_camera_info()
                
                return f"Camera is active: {camera_info.get('width', 0)}x{camera_info.get('height', 0)} @ {camera_info.get('fps', 0)}fps"
                
            except Exception as e:
                return f"Error getting vision info: {str(e)}"
        
        return get_vision_info
    
    def _create_system_status_tool(self):
        """Create tool for system status"""
        @tool
        def get_system_status() -> str:
            """Get current system status and available devices.
            Returns information about the assistant's current state.
            """
            try:
                devices = self.device_controller.get_all_devices()
                device_list = list(devices.keys())
                
                status = {
                    "assistant_running": self.is_running,
                    "session_id": self.current_session_id,
                    "available_devices": device_list,
                    "memory_available": self.memory is not None,
                    "voice_available": self.voice is not None,
                    "vision_available": self.vision is not None
                }
                
                return f"System Status: {status}"
                
            except Exception as e:
                return f"Error getting system status: {str(e)}"
        
        return get_system_status
    
    def _setup_callbacks(self) -> None:
        """Setup callbacks between components"""
        # Voice callbacks
        self.voice.add_event_callback(self._on_voice_event)
        
        # Vision callbacks
        self.vision.add_event_callback(self._on_vision_event)
        
        # Device controller callbacks
        self.device_controller.add_status_callback(self._on_device_status_change)
    
    def _on_voice_event(self, event: Dict[str, Any]) -> None:
        """Handle voice events"""
        try:
            if event.get("type") == "wake_word_detected":
                logger.info("Wake word detected, starting voice input")
                self._start_voice_input()
            elif event.get("type") == "speech_recognized":
                text = event.get("text", "")
                if text:
                    self._process_voice_input(text)
                    
        except Exception as e:
            logger.error(f"Error handling voice event: {e}")
    
    def _on_vision_event(self, event: Dict[str, Any]) -> None:
        """Handle vision events"""
        try:
            # Store vision event in memory
            self.memory.store_conversation(
                user_input=f"Vision event: {event.get('type', 'unknown')}",
                assistant_response="",
                context={"vision_event": event},
                session_id=self.current_session_id
            )
            
            # Notify event handlers
            for handler in self.event_handlers["vision_event"]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in vision event handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling vision event: {e}")
    
    def _on_device_status_change(self, device_id: str, state: str) -> None:
        """Handle device status changes"""
        try:
            # Store device state in memory
            self.memory.store_device_state(device_id, state)
            
            # Notify event handlers
            for handler in self.event_handlers["device_status"]:
                try:
                    handler(device_id, state)
                except Exception as e:
                    logger.error(f"Error in device status handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling device status change: {e}")
    
    def _start_voice_input(self) -> None:
        """Start listening for voice input after wake word"""
        try:
            # Capture audio for a few seconds
            audio_data = self._capture_voice_input()
            if audio_data:
                # Process the audio
                text = self.voice.process_audio(audio_data)
                if text:
                    self._process_voice_input(text)
                    
        except Exception as e:
            logger.error(f"Error in voice input: {e}")
    
    def _capture_voice_input(self, duration: float = 3.0) -> Optional[bytes]:
        """Capture voice input for specified duration"""
        try:
            # This is a simplified implementation
            # In practice, you'd want to use the voice processor's audio queue
            import pyaudio
            import wave
            import io
            
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )
            
            frames = []
            for _ in range(int(16000 / 1024 * duration)):
                data = stream.read(1024)
                frames.append(data)
            
            stream.stop_stream()
            stream.close()
            audio.terminate()
            
            # Convert to bytes
            audio_data = b''.join(frames)
            return audio_data
            
        except Exception as e:
            logger.error(f"Error capturing voice input: {e}")
            return None
    
    def _process_voice_input(self, text: str) -> None:
        """Process voice input and generate response"""
        try:
            logger.info(f"Processing voice input: {text}")
            
            # Store in conversation context
            self.conversation_context.append({
                "role": "user",
                "content": text,
                "timestamp": time.time()
            })
            
            # Generate response
            response = self._generate_response(text)
            
            # Store conversation in memory
            self.memory.store_conversation(
                user_input=text,
                assistant_response=response,
                context={"conversation_context": self.conversation_context[-5:]},
                session_id=self.current_session_id
            )
            
            # Add to conversation context
            self.conversation_context.append({
                "role": "assistant",
                "content": response,
                "timestamp": time.time()
            })
            
            # Speak the response
            self.voice.speak(response)
            
            # Notify event handlers
            for handler in self.event_handlers["voice_input"]:
                try:
                    handler(text, response)
                except Exception as e:
                    logger.error(f"Error in voice input handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing voice input: {e}")
    
    def _generate_response(self, text: str) -> str:
        """Generate response using AI agent or fallback"""
        try:
            if self.agent:
                # Use AI agent
                result = self.agent.invoke({"input": text})
                return result.get("output", "I'm not sure how to respond to that.")
            else:
                # Fallback responses
                return self._fallback_response(text)
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm sorry, I encountered an error processing your request."
    
    def _fallback_response(self, text: str) -> str:
        """Fallback response when AI agent is not available"""
        text_lower = text.lower()
        
        # Simple keyword matching
        if any(word in text_lower for word in ["hello", "hi", "hey"]):
            return "Hello! How can I help you today?"
        elif any(word in text_lower for word in ["light", "lights"]):
            return "I can help you control lights. What would you like to do with them?"
        elif any(word in text_lower for word in ["temperature", "thermostat"]):
            return "I can help you control the temperature. What temperature would you like?"
        elif any(word in text_lower for word in ["thank", "thanks"]):
            return "You're welcome! Is there anything else I can help you with?"
        else:
            return "I understand you said: " + text + ". How can I help you with that?"
    
    def start(self) -> None:
        """Start the smart assistant"""
        if self.is_running:
            logger.warning("Assistant is already running")
            return
        
        try:
            self.is_running = True
            
            # Start voice processing
            self.voice.start_listening(self._on_wake_word_detected)
            
            # Start vision processing
            self.vision.start_processing()
            
            # Create new session
            self.current_session_id = str(uuid.uuid4())
            self.memory.create_session(self.current_session_id)
            
            logger.info("HailoHome started successfully")
            
        except Exception as e:
            logger.error(f"Error starting assistant: {e}")
            self.is_running = False
            raise
    
    def stop(self) -> None:
        """Stop the smart assistant"""
        if not self.is_running:
            logger.warning("Assistant is not running")
            return
        
        try:
            self.is_running = False
            
            # Stop components
            self.voice.stop_listening()
            self.vision.stop_processing()
            
            # Update session
            self.memory.update_session(self.current_session_id)
            
            logger.info("HailoHome stopped")
            
        except Exception as e:
            logger.error(f"Error stopping assistant: {e}")
    
    def _on_wake_word_detected(self) -> None:
        """Handle wake word detection"""
        logger.info("Wake word detected!")
        self._start_voice_input()
    
    def add_event_handler(self, event_type: str, handler) -> None:
        """Add event handler for specific event type"""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current assistant status"""
        return {
            "is_running": self.is_running,
            "session_id": self.current_session_id,
            "components": {
                "voice": self.voice is not None,
                "vision": self.vision is not None,
                "memory": self.memory is not None,
                "device_controller": self.device_controller is not None,
                "ai_agent": self.agent is not None
            },
            "devices": self.device_controller.get_all_devices(),
            "conversation_context": self.conversation_context[-3:]  # Last 3 exchanges
        }
    
    def cleanup(self) -> None:
        """Clean up all resources"""
        try:
            self.stop()
            
            # Cleanup components
            if self.voice:
                self.voice.cleanup()
            if self.vision:
                self.vision.cleanup()
            if self.device_controller:
                self.device_controller.cleanup()
            
            logger.info("HailoHome cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
