#!/usr/bin/env python3
"""
Service Manager for HailoHome
Handles service lifecycle, monitoring, and health checks
"""

import os
import sys
import time
import signal
import logging
import subprocess
import psutil
from typing import Dict, List, Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.assistant import SmartAssistant
from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages the HailoHome service lifecycle"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = ConfigManager(config_path)
        self.assistant = None
        self.is_running = False
        self.health_check_interval = 30  # seconds
        self.max_restart_attempts = 3
        self.restart_attempts = 0
        
        # Setup logging
        self._setup_logging()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> None:
        """Setup logging configuration"""
        log_level = self.config.get("system.log_level", "INFO")
        log_file = self.config.get("system.log_file", "service_manager.log")
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file)
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def start(self) -> bool:
        """Start the Smart Assistant service"""
        try:
            if self.is_running:
                logger.warning("Service is already running")
                return True
            
            logger.info("Starting HailoHome service...")
            
            # Create assistant instance
            self.assistant = SmartAssistant(self.config_path)
            
            # Start the assistant
            self.assistant.start()
            
            self.is_running = True
            self.restart_attempts = 0
            
            logger.info("HailoHome service started successfully")
            
            # Start health monitoring
            self._start_health_monitoring()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the Smart Assistant service"""
        try:
            if not self.is_running:
                logger.warning("Service is not running")
                return
            
            logger.info("Stopping HailoHome service...")
            
            if self.assistant:
                self.assistant.stop()
                self.assistant.cleanup()
                self.assistant = None
            
            self.is_running = False
            logger.info("HailoHome service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
    
    def restart(self) -> bool:
        """Restart the HailoHome service"""
        logger.info("Restarting HailoHome service...")
        self.stop()
        time.sleep(2)  # Wait for cleanup
        return self.start()
    
    def _start_health_monitoring(self) -> None:
        """Start health monitoring in a separate thread"""
        import threading
        
        def health_monitor():
            while self.is_running:
                try:
                    if not self._check_health():
                        logger.warning("Health check failed, attempting restart...")
                        if self.restart_attempts < self.max_restart_attempts:
                            self.restart_attempts += 1
                            self.restart()
                        else:
                            logger.error("Max restart attempts reached, stopping service")
                            self.stop()
                            break
                    else:
                        self.restart_attempts = 0  # Reset on successful health check
                    
                    time.sleep(self.health_check_interval)
                    
                except Exception as e:
                    logger.error(f"Error in health monitoring: {e}")
                    time.sleep(self.health_check_interval)
        
        health_thread = threading.Thread(target=health_monitor, daemon=True)
        health_thread.start()
    
    def _check_health(self) -> bool:
        """Check if the service is healthy"""
        try:
            if not self.assistant:
                return False
            
            # Check if assistant is running
            if not self.assistant.is_running:
                return False
            
            # Check system resources
            if not self._check_system_resources():
                return False
            
            # Check component health
            if not self._check_components():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False
    
    def _check_system_resources(self) -> bool:
        """Check system resource usage"""
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                logger.warning(f"High CPU usage: {cpu_percent}%")
                return False
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                logger.warning(f"High memory usage: {memory.percent}%")
                return False
            
            # Check disk space
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                logger.warning(f"High disk usage: {disk.percent}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return False
    
    def _check_components(self) -> bool:
        """Check individual component health"""
        try:
            if not self.assistant:
                return False
            
            status = self.assistant.get_status()
            components = status.get("components", {})
            
            # Check critical components
            critical_components = ["voice", "memory", "device_controller"]
            for component in critical_components:
                if not components.get(component, False):
                    logger.warning(f"Component {component} is not available")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking components: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get current service status"""
        try:
            status = {
                "is_running": self.is_running,
                "restart_attempts": self.restart_attempts,
                "uptime": self._get_uptime(),
                "system_resources": self._get_system_resources(),
                "assistant_status": self.assistant.get_status() if self.assistant else None
            }
            return status
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"error": str(e)}
    
    def _get_uptime(self) -> float:
        """Get service uptime in seconds"""
        if hasattr(self, '_start_time'):
            return time.time() - self._start_time
        return 0.0
    
    def _get_system_resources(self) -> Dict:
        """Get current system resource usage"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {}
    
    def run(self) -> None:
        """Run the service manager"""
        try:
            self._start_time = time.time()
            
            if not self.start():
                logger.error("Failed to start service")
                sys.exit(1)
            
            # Keep running until stopped
            while self.is_running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Service manager error: {e}")
        finally:
            self.stop()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HailoHome Service Manager')
    parser.add_argument('--config', '-c', default='config.yaml',
                       help='Configuration file path')
    parser.add_argument('--daemon', '-d', action='store_true',
                       help='Run as daemon')
    
    args = parser.parse_args()
    
    # Create service manager
    service_manager = ServiceManager(args.config)
    
    if args.daemon:
        # Run as daemon (simplified implementation)
        import daemon
        with daemon.DaemonContext():
            service_manager.run()
    else:
        # Run in foreground
        service_manager.run()

if __name__ == "__main__":
    main()
