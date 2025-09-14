#!/usr/bin/env python3
"""
HailoHome Main Application
Entry point for the HailoHome system
"""

import sys
import logging
import signal
import argparse
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.assistant import SmartAssistant
from core.config_manager import ConfigManager

# Configure logging
def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('smart_assistant.log')
        ]
    )

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}, shutting down...")
    if hasattr(signal_handler, 'assistant'):
        signal_handler.assistant.cleanup()
    sys.exit(0)

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description='HailoHome - AI Smart Home Assistant')
    parser.add_argument('--config', '-c', default='config.yaml', 
                       help='Configuration file path')
    parser.add_argument('--log-level', '-l', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--daemon', '-d', action='store_true',
                       help='Run as daemon')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Run in test mode')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        
        if not config_manager.validate():
            logger.error("Configuration validation failed")
            sys.exit(1)
        
        # Create assistant instance
        assistant = SmartAssistant(args.config)
        
        # Store assistant reference for signal handler
        signal_handler.assistant = assistant
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if args.test:
            # Test mode - run basic functionality test
            logger.info("Running in test mode")
            test_assistant(assistant)
        else:
            # Normal mode - start the assistant
            logger.info("Starting HailoHome...")
            assistant.start()
            
            try:
                # Keep running until interrupted
                while assistant.is_running:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
            finally:
                assistant.stop()
                assistant.cleanup()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

def test_assistant(assistant):
    """Test basic assistant functionality"""
    logger = logging.getLogger(__name__)
    
    try:
        # Test configuration
        logger.info("Testing configuration...")
        config = assistant.config_manager
        logger.info(f"System name: {config.get('system.name')}")
        logger.info(f"MQTT broker: {config.get('mqtt.broker')}")
        
        # Test memory
        logger.info("Testing memory system...")
        assistant.memory.store_conversation(
            "Test input", 
            "Test response", 
            session_id="test_session"
        )
        conversations = assistant.memory.get_recent_conversations(limit=1)
        logger.info(f"Memory test: {len(conversations)} conversations stored")
        
        # Test device controller
        logger.info("Testing device controller...")
        devices = assistant.device_controller.get_all_devices()
        logger.info(f"Device controller test: {len(devices)} devices found")
        
        # Test voice processor
        logger.info("Testing voice processor...")
        voice_config = assistant.voice.config
        logger.info(f"Voice processor test: {voice_config}")
        
        # Test vision processor
        logger.info("Testing vision processor...")
        camera_info = assistant.vision.get_camera_info()
        logger.info(f"Vision processor test: {camera_info}")
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    main()
