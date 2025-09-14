"""
Vision Processing Module for Smart Assistant
Handles computer vision using Hailo AI accelerator
"""

import cv2
import numpy as np
import time
import logging
from typing import Dict, List, Any, Optional, Callable
import threading
from pathlib import Path
import json

# Try to import Hailo dependencies
try:
    import hailo_platform
    HAILO_AVAILABLE = True
except ImportError:
    HAILO_AVAILABLE = False
    logging.warning("Hailo platform not available, using OpenCV fallback")

logger = logging.getLogger(__name__)

class VisionProcessor:
    """Handles computer vision processing using Hailo AI accelerator"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_processing = False
        self.camera = None
        self.hailo_device = None
        self.models = {}
        self.event_callbacks = []
        
        # Vision configuration
        self.camera_id = config.get("camera_id", 0)
        self.resolution = config.get("resolution", (1920, 1080))
        self.fps = config.get("fps", 30)
        self.enable_object_detection = config.get("object_detection", True)
        self.enable_face_recognition = config.get("face_recognition", True)
        self.enable_person_tracking = config.get("person_tracking", True)
        
        # Initialize camera
        self._setup_camera()
        
        # Initialize Hailo
        self._setup_hailo()
        
        # Load models
        self._load_models()
    
    def _setup_camera(self) -> None:
        """Setup camera for video capture"""
        try:
            self.camera = cv2.VideoCapture(self.camera_id)
            if not self.camera.isOpened():
                raise Exception(f"Could not open camera {self.camera_id}")
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            logger.info(f"Camera initialized: {self.resolution[0]}x{self.resolution[1]} @ {self.fps}fps")
            
        except Exception as e:
            logger.error(f"Error setting up camera: {e}")
            self.camera = None
    
    def _setup_hailo(self) -> None:
        """Setup Hailo AI accelerator"""
        if not HAILO_AVAILABLE:
            logger.warning("Hailo not available, using OpenCV fallback")
            return
        
        try:
            # Scan for Hailo devices
            devices = hailo_platform.scan_devices()
            if not devices:
                logger.warning("No Hailo devices found")
                return
            
            self.hailo_device = devices[0]
            logger.info(f"Hailo device found: {self.hailo_device}")
            
        except Exception as e:
            logger.error(f"Error setting up Hailo: {e}")
            self.hailo_device = None
    
    def _load_models(self) -> None:
        """Load AI models for different tasks"""
        model_path = self.config.get("model_path", "/opt/hailo/models")
        
        if self.hailo_device and HAILO_AVAILABLE:
            try:
                # Load object detection model
                if self.enable_object_detection:
                    obj_det_path = Path(model_path) / "yolov5s.hef"
                    if obj_det_path.exists():
                        self.models["object_detection"] = hailo_platform.load_model(str(obj_det_path))
                        logger.info("Object detection model loaded")
                
                # Load face recognition model
                if self.enable_face_recognition:
                    face_path = Path(model_path) / "face_detection.hef"
                    if face_path.exists():
                        self.models["face_recognition"] = hailo_platform.load_model(str(face_path))
                        logger.info("Face recognition model loaded")
                
            except Exception as e:
                logger.error(f"Error loading models: {e}")
        
        # Fallback to OpenCV models
        if not self.models.get("object_detection"):
            self._load_opencv_models()
    
    def _load_opencv_models(self) -> None:
        """Load OpenCV-based models as fallback"""
        try:
            # Load OpenCV DNN models
            if self.enable_object_detection:
                # YOLO v4 model files
                yolo_config = "yolov4.cfg"
                yolo_weights = "yolov4.weights"
                
                if Path(yolo_config).exists() and Path(yolo_weights).exists():
                    self.models["object_detection"] = cv2.dnn.readNetFromDarknet(yolo_config, yolo_weights)
                    logger.info("OpenCV object detection model loaded")
            
            if self.enable_face_recognition:
                # Haar cascade for face detection
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.models["face_recognition"] = cv2.CascadeClassifier(cascade_path)
                logger.info("OpenCV face detection model loaded")
                
        except Exception as e:
            logger.error(f"Error loading OpenCV models: {e}")
    
    def add_event_callback(self, callback: Callable) -> None:
        """Add callback for vision events"""
        self.event_callbacks.append(callback)
    
    def start_processing(self) -> None:
        """Start continuous vision processing"""
        if self.is_processing:
            logger.warning("Vision processing already started")
            return
        
        if not self.camera:
            logger.error("Camera not available")
            return
        
        self.is_processing = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        logger.info("Vision processing started")
    
    def stop_processing(self) -> None:
        """Stop vision processing"""
        self.is_processing = False
        
        if hasattr(self, 'processing_thread') and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1)
        
        logger.info("Vision processing stopped")
    
    def _processing_loop(self) -> None:
        """Main vision processing loop"""
        frame_count = 0
        last_detection_time = 0
        detection_interval = 1.0  # Process every second
        
        while self.is_processing:
            try:
                ret, frame = self.camera.read()
                if not ret:
                    logger.error("Failed to read frame from camera")
                    break
                
                current_time = time.time()
                
                # Process frame for different tasks
                events = []
                
                if current_time - last_detection_time >= detection_interval:
                    # Object detection
                    if self.enable_object_detection:
                        objects = self._detect_objects(frame)
                        if objects:
                            events.extend(objects)
                    
                    # Face recognition
                    if self.enable_face_recognition:
                        faces = self._detect_faces(frame)
                        if faces:
                            events.extend(faces)
                    
                    # Person tracking
                    if self.enable_person_tracking:
                        persons = self._track_persons(frame)
                        if persons:
                            events.extend(persons)
                    
                    last_detection_time = current_time
                
                # Send events to callbacks
                for event in events:
                    self._send_event(event)
                
                frame_count += 1
                
                # Control processing rate
                time.sleep(1.0 / self.fps)
                
            except Exception as e:
                logger.error(f"Error in vision processing loop: {e}")
                break
    
    def _detect_objects(self, frame: np.ndarray) -> List[Dict]:
        """Detect objects in frame"""
        events = []
        
        try:
            if "object_detection" in self.models:
                if self.hailo_device and HAILO_AVAILABLE:
                    # Use Hailo for inference
                    detections = self._hailo_object_detection(frame)
                else:
                    # Use OpenCV DNN
                    detections = self._opencv_object_detection(frame)
                
                for detection in detections:
                    event = {
                        "type": "object_detected",
                        "object": detection["class"],
                        "confidence": detection["confidence"],
                        "bbox": detection["bbox"],
                        "timestamp": time.time()
                    }
                    events.append(event)
            
        except Exception as e:
            logger.error(f"Error in object detection: {e}")
        
        return events
    
    def _hailo_object_detection(self, frame: np.ndarray) -> List[Dict]:
        """Object detection using Hailo"""
        # Placeholder for Hailo inference
        # This would use the actual Hailo API
        return []
    
    def _opencv_object_detection(self, frame: np.ndarray) -> List[Dict]:
        """Object detection using OpenCV DNN"""
        detections = []
        
        try:
            net = self.models["object_detection"]
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
            net.setInput(blob)
            outputs = net.forward()
            
            # Process outputs (simplified)
            # This is a basic implementation - you'd need to add proper NMS and class mapping
            
        except Exception as e:
            logger.error(f"Error in OpenCV object detection: {e}")
        
        return detections
    
    def _detect_faces(self, frame: np.ndarray) -> List[Dict]:
        """Detect faces in frame"""
        events = []
        
        try:
            if "face_recognition" in self.models:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.models["face_recognition"].detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                )
                
                for (x, y, w, h) in faces:
                    event = {
                        "type": "face_detected",
                        "bbox": [int(x), int(y), int(w), int(h)],
                        "timestamp": time.time()
                    }
                    events.append(event)
        
        except Exception as e:
            logger.error(f"Error in face detection: {e}")
        
        return events
    
    def _track_persons(self, frame: np.ndarray) -> List[Dict]:
        """Track persons in frame"""
        events = []
        
        try:
            # Simple person detection using HOG descriptor
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            
            # Detect people
            (rects, weights) = hog.detectMultiScale(frame, winStride=(4, 4), padding=(8, 8), scale=1.05)
            
            for i, (x, y, w, h) in enumerate(rects):
                if weights[i] > 0.5:  # Confidence threshold
                    event = {
                        "type": "person_detected",
                        "bbox": [int(x), int(y), int(w), int(h)],
                        "confidence": float(weights[i]),
                        "timestamp": time.time()
                    }
                    events.append(event)
        
        except Exception as e:
            logger.error(f"Error in person tracking: {e}")
        
        return events
    
    def _send_event(self, event: Dict) -> None:
        """Send vision event to all callbacks"""
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in vision event callback: {e}")
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame"""
        if not self.camera:
            return None
        
        try:
            ret, frame = self.camera.read()
            return frame if ret else None
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None
    
    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        if not self.camera:
            return {}
        
        return {
            "width": int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": self.camera.get(cv2.CAP_PROP_FPS),
            "is_opened": self.camera.isOpened()
        }
    
    def cleanup(self) -> None:
        """Clean up resources"""
        self.stop_processing()
        
        if self.camera:
            self.camera.release()
        
        logger.info("Vision processor cleaned up")
