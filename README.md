# HailoHome - AI-Powered Smart Home Assistant

A comprehensive, AI-powered smart home assistant built for Raspberry Pi 5 with Hailo 8 AI accelerator, featuring voice recognition, computer vision, device control, and learning capabilities.

## 🚀 Features

- **Voice Processing**: Wake word detection, speech-to-text, and text-to-speech
- **Computer Vision**: Object detection, face recognition, and person tracking using Hailo AI
- **Device Control**: Home Assistant integration for smart home automation
- **Memory System**: Persistent conversation history and learning capabilities
- **Context Awareness**: Maintains conversation context and user preferences
- **Modular Architecture**: Easy to extend and customize

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Voice Input   │    │  Vision System  │    │ Device Control  │
│   (Wake Word)   │    │   (Hailo AI)    │    │ (Home Assistant)│
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │    Smart Assistant Core   │
                    │   (AI Agent + Memory)     │
                    └─────────────┬─────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      MQTT Broker         │
                    │    (Message Bus)         │
                    └───────────────────────────┘
```

## 📋 Prerequisites

### Hardware
- Raspberry Pi 5 (16GB recommended)
- Hailo 8 AI Kit
- Camera (CSI port 0)
- USB microphone and speaker
- ZBT-1 dongle (USB)
- MicroSD card (64GB+ recommended)

### Software
- Raspberry Pi OS (64-bit)
- Python 3.9+
- Docker (for Home Assistant)

## 🛠️ Installation

### Option 1: Automated Setup (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd HailoHome
   ```

2. **Run the setup script**:
   ```bash
   chmod +x setup_pi.sh
   ./setup_pi.sh
   ```

3. **Reboot your Raspberry Pi**:
   ```bash
   sudo reboot
   ```

### Option 2: Manual Setup

1. **Update system**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install dependencies**:
   ```bash
   sudo apt install -y git build-essential python3-dev python3-pip python3-venv
   sudo apt install -y python3-pyaudio portaudio19-dev libopenjp2-7 libtiff6
   sudo apt install -y python3-opencv libcap-dev rpicam-apps mosquitto mosquitto-clients
   ```

3. **Enable hardware interfaces**:
   ```bash
   sudo raspi-config
   # Enable Camera, SSH, I2C, SPI
   ```

4. **Install Hailo AI software**:
   ```bash
   wget -O - https://hailo-csdata.s3.eu-west-2.amazonaws.com/repositories/hm-rpi.gpg | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/hailo.gpg
   echo "deb https://hailo-csdata.s3.eu-west-2.amazonaws.com/repositories/debian stable main" | sudo tee /etc/apt/sources.list.d/hailo.list
   sudo apt update
   sudo apt install -y hailo-all hailo-firmware-hailo8 hailo-online-compiler hailo-tappas
   ```

5. **Setup Python environment**:
   ```bash
   mkdir ~/smart-assistant
   cd ~/smart-assistant
   python3 -m venv --system-site-packages .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

6. **Install Home Assistant**:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   # Log out and back in
   docker run -d --name homeassistant --privileged --restart=unless-stopped -e TZ=Europe/Paris -v ~/homeassistant_config:/config --network=host ghcr.io/home-assistant/home-assistant:stable
   ```

## ⚙️ Configuration

### 1. Basic Configuration

Edit `config.yaml` to match your setup:

```yaml
system:
  name: "Smart Assistant"
  debug: true
  log_level: "INFO"

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
```

### 2. Home Assistant Integration

1. Open Home Assistant web interface: `http://<PI_IP>:8123`
2. Go to Settings > Devices & Services
3. Add MQTT integration
4. Configure device discovery

### 3. Voice Configuration

- **Wake Word**: Change in `config.yaml` under `ai.voice.wake_word`
- **TTS Voice**: Download different voices from [Piper Voices](https://huggingface.co/rhasspy/piper-voices)
- **STT Model**: Configure Whisper model size based on your needs

## 🚀 Usage

### Starting the Assistant

```bash
# Test mode
python main.py --test

# Normal mode
python main.py

# As system service
sudo systemctl start smart-assistant
sudo systemctl status smart-assistant
```

### Voice Commands

- **Wake Word**: "Hey Assistant" (configurable)
- **Device Control**: "Turn on the living room lights"
- **Information**: "What's the temperature?"
- **General Chat**: "Tell me about the weather"

### Vision Features

- **Object Detection**: Automatically detects objects in camera view
- **Face Recognition**: Recognizes familiar faces
- **Person Tracking**: Tracks movement in the room

## 🔧 Troubleshooting

### Common Issues

1. **Camera not detected**:
   ```bash
   sudo raspi-config  # Enable camera
   rpicam-hello --timeout 1000  # Test camera
   ```

2. **Audio issues**:
   ```bash
   arecord -l  # List audio devices
   aplay -l   # List playback devices
   ```

3. **Hailo not detected**:
   ```bash
   hailo scan  # Check Hailo devices
   sudo reboot  # Reboot if needed
   ```

4. **MQTT connection issues**:
   ```bash
   sudo systemctl status mosquitto
   mosquitto_pub -h localhost -t test -m "hello"
   ```

### Logs

- **Application logs**: `smart_assistant.log`
- **System logs**: `journalctl -u smart-assistant`
- **MQTT logs**: `/var/log/mosquitto/mosquitto.log`

## 📁 Project Structure

```
HailoHome/
├── core/                    # Core modules
│   ├── assistant.py        # Main assistant class
│   ├── config_manager.py   # Configuration management
│   ├── memory.py          # Memory and learning system
│   ├── voice.py           # Voice processing
│   ├── vision.py          # Computer vision
│   └── device_controller.py # Device control
├── config.yaml            # Configuration file
├── main.py               # Application entry point
├── requirements.txt      # Python dependencies
├── setup_pi.sh          # Raspberry Pi setup script
└── README.md            # This file
```

## 🔄 Development

### Adding New Features

1. **Create new module** in `core/` directory
2. **Add to assistant** in `core/assistant.py`
3. **Update configuration** in `config.yaml`
4. **Add tests** and documentation

### Extending Voice Commands

1. **Add new tools** in `core/assistant.py`
2. **Update agent** with new capabilities
3. **Test with voice** input

### Custom Vision Models

1. **Convert models** to Hailo format (.hef)
2. **Place in models/** directory
3. **Update vision.py** to load new models

## 📊 Performance Optimization

### Raspberry Pi 5 Optimization

- **GPU Memory Split**: Increase to 128MB in `raspi-config`
- **CPU Governor**: Set to `performance` mode
- **Thermal Management**: Ensure adequate cooling
- **Power Supply**: Use official 27W power supply

### Memory Management

- **Cleanup old data**: Configure in `memory.cleanup_interval`
- **Limit conversation history**: Set `memory.max_conversations`
- **Optimize models**: Use smaller models for better performance

## 🔒 Security

### Network Security

- **MQTT Authentication**: Enable in production
- **API Keys**: Secure Home Assistant tokens
- **Firewall**: Configure appropriate rules

### Data Privacy

- **Local Processing**: All AI processing happens locally
- **No Cloud Dependencies**: No data sent to external services
- **Encrypted Storage**: Optional database encryption

## 📈 Monitoring

### System Monitoring

- **Resource Usage**: CPU, memory, GPU utilization
- **Service Health**: Component status monitoring
- **Error Tracking**: Comprehensive logging

### Performance Metrics

- **Response Time**: Voice command processing time
- **Accuracy**: STT and vision detection accuracy
- **Uptime**: System availability

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Hailo Technologies** for AI acceleration
- **OpenAI** for Whisper STT
- **Mozilla** for Piper TTS
- **Home Assistant** for smart home integration
- **LangChain** for AI agent framework

## 📞 Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Documentation**: Wiki pages

---

**Happy Building! 🏠🤖**
