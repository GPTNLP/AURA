#!/bin/bash

# Setup script for ECEN 214 Lab Assistant on Jetson Orin Nano

set -e

echo "ECEN 214 Lab Assistant Setup"
echo "============================"
echo ""

# Check if running on Jetson
if [ -f /etc/nv_tegra_release ]; then
    echo "Detected Jetson platform"
    echo "Setting max performance mode..."
    sudo nvpmodel -m 0
    sudo jetson_clocks
    echo ""
fi

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "Dependencies installed"
echo ""

# Check if Ollama is installed
echo "Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "Ollama not found. Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "Ollama installed"
else
    echo "Ollama is already installed"
fi
echo ""

# Start Ollama service
echo "Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!
sleep 5
echo ""

# Pull required models
echo "Pulling required models..."
echo "This may take 5-10 minutes depending on your connection"
echo ""

if ollama list | grep -q "llama3.2:1b"; then
    echo "llama3.2:1b already available"
else
    echo "Pulling llama3.2:1b..."
    ollama pull llama3.2:1b
fi

if ollama list | grep -q "nomic-embed-text"; then
    echo "nomic-embed-text already available"
else
    echo "Pulling nomic-embed-text..."
    ollama pull nomic-embed-text
fi

echo ""
echo "Models installed"
echo ""

# Create Docs directory
if [ ! -d "Docs" ]; then
    echo "Creating Docs directory..."
    mkdir Docs
    echo "Please add your lab documents to the Docs/ folder"
else
    echo "Docs directory already exists"
    DOC_COUNT=$(find Docs -type f \( -name "*.pdf" -o -name "*.txt" -o -name "*.md" -o -name "*.docx" \) | wc -l)
    echo "Found $DOC_COUNT documents in Docs/"
fi
echo ""

# Create storage directory
mkdir -p storage/chroma

echo "============================"
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Add your lab documents to Docs/"
echo "2. Run: python app.py"
echo ""
echo "Ollama is running in the background (PID: $OLLAMA_PID)"
echo "To stop Ollama: kill $OLLAMA_PID"
echo ""
echo "For Jetson optimization, the system is now in max performance mode"