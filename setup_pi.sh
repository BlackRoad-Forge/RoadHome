#!/bin/bash
# HailoHome Setup Script for Raspberry Pi
# This script sets up the complete HailoHome system on Raspberry Pi OS

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root"
   exit 1
fi

# Configuration
PROJECT_DIR="$HOME/smart-assistant"
VENV_DIR="$PROJECT_DIR/.venv"
DATA_DIR="$PROJECT_DIR/data"
LOG_DIR="$PROJECT_DIR/logs"

log "Starting HailoHome setup for Raspberry Pi..."

# Step 1: Update system
log "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Step 2: Install essential packages
log "Installing essential packages..."
sudo apt install -y \
    git \
    build-essential \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-pyaudio \
    portaudio19-dev \
    libopenjp2-7 \
    libtiff6 \
    python3-opencv \
    libcap-dev \
    rpicam-apps \
    mosquitto \
    mosquitto-clients \
    curl \
    wget \
    unzip \
    ffmpeg \
    espeak \
    espeak-data \
    libespeak1 \
    libespeak-dev

# Step 3: Enable hardware interfaces
log "Enabling hardware interfaces..."
sudo raspi-config nonint do_camera 0  # Enable camera
sudo raspi-config nonint do_ssh 0     # Enable SSH
sudo raspi-config nonint do_i2c 0     # Enable I2C
sudo raspi-config nonint do_spi 0     # Enable SPI

# Step 4: Configure MQTT
log "Configuring MQTT broker..."
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Create MQTT configuration
sudo tee /etc/mosquitto/conf.d/hailohome.conf > /dev/null <<EOF
listener 1883
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information
EOF

sudo systemctl restart mosquitto

# Step 5: Install Hailo AI software
log "Installing Hailo AI software suite..."

# Add Hailo repository
wget -O - https://hailo-csdata.s3.eu-west-2.amazonaws.com/repositories/hm-rpi.gpg | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/hailo.gpg
echo "deb https://hailo-csdata.s3.eu-west-2.amazonaws.com/repositories/debian stable main" | sudo tee /etc/apt/sources.list.d/hailo.list

# Update package lists
sudo apt update

# Install Hailo packages
sudo apt install -y \
    hailo-all \
    hailo-firmware-hailo8 \
    hailo-online-compiler \
    hailo-tappas

# Step 6: Create project directory structure
log "Creating project directory structure..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/models"
mkdir -p "$PROJECT_DIR/scripts"

# Step 7: Setup Python virtual environment
log "Setting up Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install Python packages
log "Installing Python packages..."
pip install --upgrade pip
pip install \
    paho-mqtt \
    sounddevice \
    picamera2 \
    numpy \
    opencv-python \
    PyYAML \
    requests \
    sqlite3 \
    whisper \
    pvporcupine \
    langchain \
    langchain-community \
    langchain-ollama \
    langchainhub \
    ollama

# Step 8: Download and setup Piper TTS
log "Setting up Piper TTS..."
cd "$PROJECT_DIR"
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
tar -xzf piper_linux_aarch64.tar.gz
rm piper_linux_aarch64.tar.gz

# Download voice model
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# Step 9: Download AI models
log "Downloading AI models..."
cd "$PROJECT_DIR/models"

# Download YOLO model for object detection
wget https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4.weights
wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg

# Download Whisper model
cd "$PROJECT_DIR"
python3 -c "import whisper; whisper.load_model('base')"

# Step 10: Create systemd service
log "Creating systemd service..."
sudo tee /etc/systemd/system/hailohome.service > /dev/null <<EOF
[Unit]
Description=HailoHome - AI Smart Home Assistant
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$VENV_DIR/bin
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 11: Create configuration file
log "Creating configuration file..."
cat > "$PROJECT_DIR/config.yaml" <<EOF
# HailoHome Configuration for Raspberry Pi
system:
  name: "HailoHome"
  version: "2.0.0"
  debug: true
  log_level: "INFO"
  data_dir: "$DATA_DIR"

hardware:
  hailo:
    enabled: true
    device_id: 0
    model_path: "$PROJECT_DIR/models"
  camera:
    enabled: true
    device: 0
    resolution: [1920, 1080]
    fps: 30
  audio:
    input_device: "USB Audio Device"
    output_device: "USB Audio Device"
    sample_rate: 16000
    channels: 1
  zbt_dongle:
    enabled: true
    device_path: "/dev/ttyUSB0"

mqtt:
  broker: "localhost"
  port: 1883
  username: ""
  password: ""
  topics:
    voice_input: "assistant/voice/input"
    voice_output: "assistant/voice/output"
    vision_events: "assistant/vision/events"
    device_control: "assistant/devices/control"
    device_status: "assistant/devices/status"
    memory_events: "assistant/memory/events"
    system_status: "assistant/system/status"

ai:
  llm:
    model: "qwen2.5:3b-instruct-q4_K_M"
    temperature: 0.7
    max_tokens: 512
    context_window: 4096
  
  voice:
    wake_word: "hey assistant"
    stt_model: "whisper"
    tts_model: "piper"
    tts_voice: "en_US-lessac-medium"
    piper_path: "$PROJECT_DIR/piper/piper"
    tts_model_path: "$PROJECT_DIR/en_US-lessac-medium.onnx"
  
  vision:
    object_detection: true
    face_recognition: true
    person_tracking: true
    scene_understanding: true

memory:
  enabled: true
  storage_type: "sqlite"
  database_path: "$DATA_DIR/memory.db"
  max_conversations: 1000
  context_window: 10
  learning_enabled: true

home_assistant:
  enabled: true
  url: "http://localhost:8123"
  token: ""
  auto_discovery: true
  update_interval: 30

security:
  enable_encryption: true
  api_key_required: false
  max_request_rate: 100
  allowed_ips: ["127.0.0.1", "192.168.1.0/24"]

performance:
  max_concurrent_requests: 5
  request_timeout: 30
  memory_limit: "2GB"
  cpu_limit: "80%"
  gpu_enabled: true
EOF

# Step 12: Create startup script
log "Creating startup script..."
cat > "$PROJECT_DIR/start.sh" <<EOF
#!/bin/bash
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"
python main.py
EOF

chmod +x "$PROJECT_DIR/start.sh"

# Step 13: Create test script
log "Creating test script..."
cat > "$PROJECT_DIR/test.sh" <<EOF
#!/bin/bash
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"
python main.py --test
EOF

chmod +x "$PROJECT_DIR/test.sh"

# Step 14: Setup permissions
log "Setting up permissions..."
sudo usermod -a -G audio "$USER"
sudo usermod -a -G video "$USER"
sudo usermod -a -G dialout "$USER"

# Step 15: Enable services
log "Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable hailohome

# Step 16: Verify Hailo installation
log "Verifying Hailo installation..."
if command -v hailo &> /dev/null; then
    log "Hailo scan:"
    hailo scan
else
    warn "Hailo command not found, please check installation"
fi

# Step 17: Test camera
log "Testing camera..."
if command -v rpicam-hello &> /dev/null; then
    timeout 5s rpicam-hello --timeout 1000 || warn "Camera test failed"
else
    warn "rpicam-hello not found, camera test skipped"
fi

# Step 18: Final setup
log "Finalizing setup..."
sudo systemctl restart mosquitto

log "Setup completed successfully!"
log "Project directory: $PROJECT_DIR"
log "Virtual environment: $VENV_DIR"
log "Data directory: $DATA_DIR"
log "Logs directory: $LOG_DIR"

echo ""
log "Next steps:"
echo "1. Copy the HailoHome code to $PROJECT_DIR"
echo "2. Configure Home Assistant if needed"
echo "3. Test the system: $PROJECT_DIR/test.sh"
echo "4. Start HailoHome: $PROJECT_DIR/start.sh"
echo "5. Or start as service: sudo systemctl start hailohome"

echo ""
warn "Please reboot your Raspberry Pi to ensure all hardware interfaces are properly enabled:"
echo "sudo reboot"

log "Setup script completed!"
