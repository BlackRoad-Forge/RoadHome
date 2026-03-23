#!/bin/bash
# RoadHome — BlackRoad OS Quick Setup
# Run on any Pi 5 with Hailo-8: curl -sL https://raw.githubusercontent.com/BlackRoad-Forge/RoadHome/main/setup-blackroad.sh | bash

set -e
echo "🏠 RoadHome — BlackRoad OS Smart Home Setup"
echo "============================================"

# Check for Pi 5
if ! grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
  echo "⚠️  Not a Raspberry Pi 5 — continuing anyway"
fi

# Check for Hailo
if [ -e /dev/hailo0 ]; then
  echo "✅ Hailo-8 detected at /dev/hailo0"
else
  echo "⚠️  No Hailo-8 detected — vision features will be limited"
fi

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv mosquitto mosquitto-clients portaudio19-dev

# Create venv
python3 -m venv ~/roadhome-env
source ~/roadhome-env/bin/activate

# Install Python packages
pip install -q paho-mqtt langchain langchain-ollama ollama opencv-python-headless numpy sounddevice webrtcvad

# Check Ollama
if command -v ollama &>/dev/null; then
  echo "✅ Ollama available"
  ollama pull qwen2.5:1.5b 2>/dev/null &
else
  echo "📥 Installing Ollama..."
  curl -fsSL https://ollama.ai/install.sh | sh
  ollama pull qwen2.5:1.5b &
fi

# Start MQTT broker
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
echo "✅ MQTT broker running"

# Copy config
cp config.blackroad.yaml config.yaml
echo "✅ BlackRoad config applied"

echo ""
echo "🏠 RoadHome ready!"
echo "   Start: python3 main.py"
echo "   Config: config.yaml"
echo "   MQTT: localhost:1883"
echo "   Ollama: localhost:11434"
echo ""
echo "   Pave Tomorrow. 🛣️"
