#!/bin/bash
set -e

# Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Ollama is not running. Please start Ollama first."
    exit 1
fi

# Check if model exists
MODEL="llava:13b-v1.6-vicuna-q4_0"
if ! ollama list | grep -q "$MODEL"; then
    echo "Model $MODEL not found. Pulling it now..."
    ollama pull "$MODEL"
fi

echo "Starting LLM Monitor..."
export SERVER_NAME="127.0.0.1"
python3 -m src.app
