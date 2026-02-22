#!/bin/bash
set -e
echo "AURA Setup for Jetson Orin Nano"

sudo apt-get update && sudo apt-get install -y python3-pip python3-venv curl

if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable ollama && sudo systemctl start ollama

ollama pull llama3.2
ollama pull nomic-embed-text

if [ ! -d "aura_env" ]; then
    python3 -m venv aura_env
fi
source aura_env/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Setup Complete. Run: python3 nano_api.py"