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

# Start RTSP Server (MediaMTX)
echo "Starting RTSP Server..."
nohup mediamtx > /dev/null 2>&1 &
sleep 2

# Start FFmpeg Stream (Camera -> RTSP)
echo "Starting Camera Stream..."
nohup ffmpeg -f v4l2 -framerate 30 -video_size 640x480 -i /dev/video0 -c:v libx264 -preset ultrafast -tune zerolatency -f rtsp rtsp://localhost:8554/live/stream > /dev/null 2>&1 &
sleep 2

# Set Camera URL for App
export CAMERA_URL="rtsp://localhost:8554/live/stream"

echo "Starting LLM Monitor..."
export SERVER_NAME="127.0.0.1"
python3 -m src.app
