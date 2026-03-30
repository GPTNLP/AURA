#!/bin/bash
set -e

echo "===================================="
echo " AURA Setup for Jetson Orin Nano"
echo "===================================="

sudo apt-get update

sudo apt-get install -y \
python3-pip \
python3-venv \
curl \
portaudio19-dev \
python3-pyaudio \
flac \
chromium-browser \
unclutter \
x11-xserver-utils

echo "System dependencies installed"

if ! command -v ollama &> /dev/null
then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

sudo systemctl enable ollama
sudo systemctl start ollama

echo "Downloading Ollama models..."
ollama pull llama3.2
ollama pull nomic-embed-text

if [ ! -d "aura_env" ]; then
    python3 -m venv aura_env --system-site-packages
fi

source aura_env/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup Complete"
echo ""
echo "Next steps:"
echo "1. Set SERIAL_PORT=/dev/ttyACM0 in .env if that is your ESP32 port"
echo "2. source aura_env/bin/activate"
echo "3. python nano_main.py"
echo "4. open http://127.0.0.1:8000"