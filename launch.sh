#!/bin/bash
set -e

# Check if Ollama is running (check host API endpoint)
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
if ! curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "Ollama is not running at $OLLAMA_HOST. Please start Ollama first."
    exit 1
fi

echo "Ollama detected at $OLLAMA_HOST"

# Check if model exists (skip in Docker, assume model is available)
# Models are managed on the host, not in the container

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
