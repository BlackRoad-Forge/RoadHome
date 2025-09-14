# HailoHome Deployment Guide

This guide provides step-by-step instructions for deploying HailoHome on your Raspberry Pi 5 with Hailo 8 AI kit.

## 🎯 Quick Start (5 minutes)

### 1. Download and Setup
```bash
# Download the code
git clone <repository-url>
cd HailoHome

# Make setup script executable
chmod +x setup_pi.sh

# Run automated setup
./setup_pi.sh
```

### 2. Reboot and Test
```bash
# Reboot to enable all hardware
sudo reboot

# After reboot, test the system
cd ~/smart-assistant
./test.sh
```

### 3. Start the Assistant
```bash
# Start manually
./start.sh

# Or start as system service
sudo systemctl start smart-assistant
```

## 🔧 Detailed Setup

### Prerequisites Check

Before starting, ensure you have:

- [ ] Raspberry Pi 5 (16GB RAM recommended)
- [ ] Hailo 8 AI Kit properly connected
- [ ] Camera connected to CSI port 0
- [ ] USB microphone and speaker
- [ ] ZBT-1 dongle connected via USB
- [ ] MicroSD card (64GB+ recommended)
- [ ] Raspberry Pi OS (64-bit) installed
- [ ] Internet connection

### Step 1: System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y git curl wget unzip

# Enable hardware interfaces
sudo raspi-config
# Navigate to: 3 Interface Options
# Enable: Camera, SSH, I2C, SPI
# Save and reboot
```

### Step 2: Hailo AI Installation

```bash
# Add Hailo repository
wget -O - https://hailo-csdata.s3.eu-west-2.amazonaws.com/repositories/hm-rpi.gpg | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/hailo.gpg

echo "deb https://hailo-csdata.s3.eu-west-2.amazonaws.com/repositories/debian stable main" | sudo tee /etc/apt/sources.list.d/hailo.list

# Update package lists
sudo apt update

# Install Hailo packages
sudo apt install -y hailo-all hailo-firmware-hailo8 hailo-online-compiler hailo-tappas

# Verify installation
hailo scan
```

### Step 3: Audio Setup

```bash
# Install audio packages
sudo apt install -y python3-pyaudio portaudio19-dev espeak espeak-data libespeak1 libespeak-dev

# Test audio devices
arecord -l  # List input devices
aplay -l   # List output devices

# Test microphone
arecord -d 5 -f cd test.wav
aplay test.wav
```

### Step 4: Camera Setup

```bash
# Test camera
rpicam-hello --timeout 1000

# If camera not detected, check connections and enable in raspi-config
sudo raspi-config
# 3 Interface Options > I1 Legacy Camera > Enable
```

### Step 5: MQTT Broker Setup

```bash
# Install Mosquitto
sudo apt install -y mosquitto mosquitto-clients

# Configure MQTT
sudo tee /etc/mosquitto/conf.d/smart-assistant.conf > /dev/null <<EOF
listener 1883
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log
EOF

# Start and enable MQTT
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Test MQTT
mosquitto_pub -h localhost -t test -m "hello"
mosquitto_sub -h localhost -t test
```

### Step 6: Python Environment Setup

```bash
# Create project directory
mkdir -p ~/smart-assistant
cd ~/smart-assistant

# Create virtual environment
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 7: Download AI Models

```bash
# Download Piper TTS
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
tar -xzf piper_linux_aarch64.tar.gz
rm piper_linux_aarch64.tar.gz

# Download voice model
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# Download Whisper model
python3 -c "import whisper; whisper.load_model('base')"

# Download YOLO model for object detection
mkdir -p models
cd models
wget https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4.weights
wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg
cd ..
```

### Step 8: Home Assistant Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Log out and back in for group changes
logout

# After logging back in, install Home Assistant
docker run -d --name homeassistant --privileged --restart=unless-stopped -e TZ=Europe/Paris -v ~/homeassistant_config:/config --network=host ghcr.io/home-assistant/home-assistant:stable
```

### Step 9: Deploy Smart Assistant Code

```bash
# Copy the HailoHome code
cp -r /path/to/HailoHome/* ~/smart-assistant/

# Set permissions
chmod +x ~/smart-assistant/start.sh
chmod +x ~/smart-assistant/test.sh
```

### Step 10: Configuration

Edit `~/smart-assistant/config.yaml`:

```yaml
system:
  name: "Smart Assistant"
  debug: true
  log_level: "INFO"
  data_dir: "/home/pi/smart-assistant/data"

hardware:
  camera:
    device: 0
    resolution: [1920, 1080]
    fps: 30
  audio:
    sample_rate: 16000
    channels: 1

mqtt:
  broker: "localhost"
  port: 1883

ai:
  voice:
    wake_word: "hey assistant"
    tts_voice: "en_US-lessac-medium"
    piper_path: "/home/pi/smart-assistant/piper/piper"
    tts_model_path: "/home/pi/smart-assistant/en_US-lessac-medium.onnx"
```

### Step 11: Create System Service

```bash
# Create systemd service
sudo tee /etc/systemd/system/smart-assistant.service > /dev/null <<EOF
[Unit]
Description=Smart Assistant
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/smart-assistant
Environment=PATH=/home/pi/smart-assistant/.venv/bin
ExecStart=/home/pi/smart-assistant/.venv/bin/python /home/pi/smart-assistant/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable smart-assistant
```

## 🧪 Testing

### Basic Functionality Test

```bash
cd ~/smart-assistant
./test.sh
```

### Component Tests

```bash
# Test voice
python3 -c "
from core.voice import VoiceProcessor
voice = VoiceProcessor({'sample_rate': 16000, 'channels': 1})
print('Voice processor initialized')
"

# Test vision
python3 -c "
from core.vision import VisionProcessor
vision = VisionProcessor({'camera_id': 0})
print('Vision processor initialized')
"

# Test memory
python3 -c "
from core.memory import MemoryManager
memory = MemoryManager('test.db')
memory.store_conversation('test', 'response')
print('Memory system working')
"
```

### Integration Test

```bash
# Start the assistant
sudo systemctl start smart-assistant

# Check status
sudo systemctl status smart-assistant

# View logs
journalctl -u smart-assistant -f
```

## 🚀 Production Deployment

### Performance Optimization

```bash
# Increase GPU memory split
sudo raspi-config
# Advanced Options > Memory Split > 128

# Set CPU governor to performance
echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Optimize thermal management
echo 'arm_freq=2400' | sudo tee -a /boot/config.txt
echo 'gpu_freq=800' | sudo tee -a /boot/config.txt
```

### Security Configuration

```bash
# Enable MQTT authentication
sudo tee -a /etc/mosquitto/conf.d/smart-assistant.conf > /dev/null <<EOF
password_file /etc/mosquitto/passwd
allow_anonymous false
EOF

# Create MQTT user
sudo mosquitto_passwd -c /etc/mosquitto/passwd assistant
sudo systemctl restart mosquitto
```

### Monitoring Setup

```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Create monitoring script
cat > ~/monitor.sh <<'EOF'
#!/bin/bash
echo "=== System Resources ==="
htop -n 1
echo "=== Network Usage ==="
nethogs -d 1
echo "=== Disk Usage ==="
df -h
EOF

chmod +x ~/monitor.sh
```

## 🔧 Troubleshooting

### Common Issues

1. **Camera not detected**:
   ```bash
   sudo raspi-config  # Enable camera
   rpicam-hello --timeout 1000
   ```

2. **Audio not working**:
   ```bash
   arecord -l  # Check devices
   sudo usermod -a -G audio $USER
   ```

3. **Hailo not detected**:
   ```bash
   hailo scan
   sudo reboot
   ```

4. **MQTT connection failed**:
   ```bash
   sudo systemctl status mosquitto
   mosquitto_pub -h localhost -t test -m "hello"
   ```

5. **Python import errors**:
   ```bash
   source ~/smart-assistant/.venv/bin/activate
   pip install -r requirements.txt
   ```

### Log Analysis

```bash
# Application logs
tail -f ~/smart-assistant/smart_assistant.log

# System logs
journalctl -u smart-assistant -f

# MQTT logs
tail -f /var/log/mosquitto/mosquitto.log
```

### Performance Monitoring

```bash
# CPU and memory usage
htop

# GPU usage
vcgencmd measure_temp
vcgencmd get_mem gpu

# Network usage
nethogs

# Disk usage
df -h
```

## 📊 Maintenance

### Regular Maintenance

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean up old logs
sudo journalctl --vacuum-time=7d

# Clean up old data
cd ~/smart-assistant
python3 -c "
from core.memory import MemoryManager
memory = MemoryManager('data/memory.db')
memory.cleanup_old_data(days=30)
"
```

### Backup

```bash
# Create backup script
cat > ~/backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/home/pi/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup configuration
tar -czf $BACKUP_DIR/smart_assistant_config_$DATE.tar.gz ~/smart-assistant/config.yaml

# Backup data
tar -czf $BACKUP_DIR/smart_assistant_data_$DATE.tar.gz ~/smart-assistant/data/

# Keep only last 7 backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
EOF

chmod +x ~/backup.sh

# Add to crontab for daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * /home/pi/backup.sh") | crontab -
```

## 🎉 Success!

Your Smart Assistant is now deployed and ready to use! 

### Next Steps:
1. Configure Home Assistant devices
2. Customize voice commands
3. Train face recognition
4. Set up automation rules
5. Monitor and optimize performance

### Support:
- Check logs for issues
- Review configuration
- Test individual components
- Monitor system resources

Happy building! 🏠🤖
