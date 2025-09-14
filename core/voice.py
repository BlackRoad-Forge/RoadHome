"""
Voice Processing Module for Smart Assistant
Handles wake word detection, speech-to-text, and text-to-speech
"""

import pyaudio
import wave
import threading
import queue
import time
import logging
from typing import Callable, Optional, Dict, Any
import numpy as np
from pathlib import Path

# Try to import optional dependencies
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logging.warning("Whisper not available, STT will use fallback")

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    logging.warning("Porcupine not available, wake word detection disabled")

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """Handles all voice processing including wake word detection, STT, and TTS"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_listening = False
        self.is_processing = False
        self.audio_queue = queue.Queue()
        self.wake_word_callback: Optional[Callable] = None
        self.audio_thread: Optional[threading.Thread] = None
        self.wake_word_thread: Optional[threading.Thread] = None
        
        # Audio configuration
        self.sample_rate = config.get("sample_rate", 16000)
        self.chunk_size = config.get("chunk_size", 1024)
        self.channels = config.get("channels", 1)
        self.format = pyaudio.paInt16
        
        # Initialize audio
        self.audio = pyaudio.PyAudio()
        self._setup_audio_devices()
        
        # Initialize STT
        self._setup_stt()
        
        # Initialize TTS
        self._setup_tts()
        
        # Initialize wake word detection
        self._setup_wake_word_detection()
    
    def _setup_audio_devices(self) -> None:
        """Setup audio input and output devices"""
        try:
            # Find input device
            input_device = None
            output_device = None
            
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                if "USB Audio" in info["name"] and info["maxInputChannels"] > 0:
                    input_device = i
                if "USB Audio" in info["name"] and info["maxOutputChannels"] > 0:
                    output_device = i
            
            if input_device is None:
                input_device = self.audio.get_default_input_device_info()["index"]
            if output_device is None:
                output_device = self.audio.get_default_output_device_info()["index"]
            
            self.input_device = input_device
            self.output_device = output_device
            
            logger.info(f"Audio devices - Input: {input_device}, Output: {output_device}")
            
        except Exception as e:
            logger.error(f"Error setting up audio devices: {e}")
            raise
    
    def _setup_stt(self) -> None:
        """Setup speech-to-text model"""
        if WHISPER_AVAILABLE:
            try:
                model_name = self.config.get("stt_model", "base")
                self.stt_model = whisper.load_model(model_name)
                logger.info(f"STT model loaded: {model_name}")
            except Exception as e:
                logger.error(f"Error loading STT model: {e}")
                self.stt_model = None
        else:
            self.stt_model = None
            logger.warning("STT not available - install whisper")
    
    def _setup_tts(self) -> None:
        """Setup text-to-speech"""
        self.tts_voice = self.config.get("tts_voice", "en_US-lessac-medium")
        self.tts_model_path = self.config.get("tts_model_path", "piper")
        logger.info(f"TTS configured with voice: {self.tts_voice}")
    
    def _setup_wake_word_detection(self) -> None:
        """Setup wake word detection"""
        if PORCUPINE_AVAILABLE:
            try:
                self.wake_word = self.config.get("wake_word", "hey assistant")
                # Note: You'll need to get a Porcupine access key and create a custom wake word
                # For now, we'll use a simple audio level detection as fallback
                self.porcupine = None
                logger.info("Wake word detection configured (fallback mode)")
            except Exception as e:
                logger.error(f"Error setting up wake word detection: {e}")
                self.porcupine = None
        else:
            self.porcupine = None
            logger.warning("Wake word detection not available - install pvporcupine")
    
    def start_listening(self, wake_word_callback: Callable) -> None:
        """Start listening for wake words and voice input"""
        if self.is_listening:
            logger.warning("Already listening")
            return
        
        self.wake_word_callback = wake_word_callback
        self.is_listening = True
        
        # Start audio capture thread
        self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.audio_thread.start()
        
        # Start wake word detection thread
        self.wake_word_thread = threading.Thread(target=self._wake_word_loop, daemon=True)
        self.wake_word_thread.start()
        
        logger.info("Voice processing started")
    
    def stop_listening(self) -> None:
        """Stop listening for voice input"""
        self.is_listening = False
        
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1)
        
        if self.wake_word_thread and self.wake_word_thread.is_alive():
            self.wake_word_thread.join(timeout=1)
        
        logger.info("Voice processing stopped")
    
    def _audio_capture_loop(self) -> None:
        """Continuously capture audio and add to queue"""
        try:
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.input_device,
                frames_per_buffer=self.chunk_size
            )
            
            while self.is_listening:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    self.audio_queue.put(data)
                except Exception as e:
                    logger.error(f"Error reading audio: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            logger.error(f"Error in audio capture loop: {e}")
    
    def _wake_word_loop(self) -> None:
        """Detect wake words in audio stream"""
        audio_buffer = b""
        buffer_size = self.sample_rate * 3  # 3 seconds of audio
        
        while self.is_listening:
            try:
                if not self.audio_queue.empty():
                    data = self.audio_queue.get_nowait()
                    audio_buffer += data
                    
                    # Keep buffer size manageable
                    if len(audio_buffer) > buffer_size:
                        audio_buffer = audio_buffer[-buffer_size:]
                    
                    # Simple wake word detection based on audio level
                    if self._detect_wake_word_simple(audio_buffer):
                        logger.info("Wake word detected!")
                        if self.wake_word_callback:
                            self.wake_word_callback()
                
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage
                
            except queue.Empty:
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"Error in wake word detection: {e}")
                break
    
    def _detect_wake_word_simple(self, audio_data: bytes) -> bool:
        """Simple wake word detection based on audio level"""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate RMS (Root Mean Square) for volume detection
            rms = np.sqrt(np.mean(audio_array**2))
            
            # Simple threshold-based detection
            threshold = 1000  # Adjust based on your microphone sensitivity
            return rms > threshold
            
        except Exception as e:
            logger.error(f"Error in wake word detection: {e}")
            return False
    
    def process_audio(self, audio_data: bytes) -> Optional[str]:
        """Process audio data and return transcribed text"""
        if not self.stt_model:
            logger.warning("STT model not available")
            return None
        
        try:
            self.is_processing = True
            
            # Save audio to temporary file
            temp_file = Path("/tmp/temp_audio.wav")
            self._save_audio_to_file(audio_data, temp_file)
            
            # Transcribe using Whisper
            result = self.stt_model.transcribe(str(temp_file))
            text = result["text"].strip()
            
            # Clean up temp file
            temp_file.unlink(missing_ok=True)
            
            logger.info(f"Transcribed: {text}")
            return text if text else None
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return None
        finally:
            self.is_processing = False
    
    def _save_audio_to_file(self, audio_data: bytes, file_path: Path) -> None:
        """Save audio data to WAV file"""
        try:
            with wave.open(str(file_path), 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.audio.get_sample_size(self.format))
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_data)
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            raise
    
    def speak(self, text: str) -> bool:
        """Convert text to speech and play it"""
        try:
            # Use Piper TTS (external process)
            piper_path = self.config.get("piper_path", "piper")
            model_path = self.config.get("tts_model_path", "en_US-lessac-medium.onnx")
            
            # Create command for Piper
            cmd = f'echo "{text}" | {piper_path} --model {model_path} --output-raw | aplay -r 22050 -f S16_LE -t raw -'
            
            import subprocess
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Spoke: {text}")
                return True
            else:
                logger.error(f"TTS error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error in TTS: {e}")
            return False
    
    def get_audio_level(self) -> float:
        """Get current audio input level for visualization"""
        try:
            if not self.audio_queue.empty():
                data = self.audio_queue.get_nowait()
                audio_array = np.frombuffer(data, dtype=np.int16)
                return float(np.sqrt(np.mean(audio_array**2)))
        except:
            pass
        return 0.0
    
    def cleanup(self) -> None:
        """Clean up resources"""
        self.stop_listening()
        if hasattr(self, 'audio'):
            self.audio.terminate()
        logger.info("Voice processor cleaned up")
