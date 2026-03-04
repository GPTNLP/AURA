#!/bin/bash
set -e
echo "AURA Setup for Jetson Orin Nano"

# Update apt and install required system dependencies, including audio libraries for the USB mic
sudo apt-get update && sudo apt-get install -y \
    python3-pip python3-venv curl python3-pyaudio \
    portaudio19-dev flac

if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable ollama && sudo systemctl start ollama

ollama pull llama3.2
ollama pull nomic-embed-text

if [ ! -d "aura_env" ]; then
    python3 -m venv aura_env --system-site-packages
fi
source aura_env/bin/activate

pip install --upgrade pip

# Install the standard project requirements
pip install -r requirements.txt

# Install specific hardware libraries for Jetson and peripheral features
pip install jetson-stats pyserial SpeechRecognition faster-whisper

# Ensure connection to the University WiFi is established at OS level
echo "To ensure TAMU_WiFi is connected, run: nmcli d wifi connect TAMU_WiFi password <YOUR_PASSWORD>"

echo "Setup Complete. Run: python3 nano_main.py"