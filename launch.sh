#!/bin/bash
set -e

# Check if Ollama is running (check host API endpoint)
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
if ! curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "Ollama is not running at $OLLAMA_HOST. Please start Ollama first."
    exit 1
fi

echo "Ollama detected at $OLLAMA_HOST"

# Start RTSP Server (MediaMTX)
echo "Starting RTSP Server..."
mediamtx > /tmp/mediamtx.log 2>&1 &
MEDIAMTX_PID=$!
sleep 2

# Verify mediamtx started
if ! kill -0 $MEDIAMTX_PID 2>/dev/null; then
    echo "Failed to start mediamtx. Check /tmp/mediamtx.log"
    cat /tmp/mediamtx.log
    exit 1
fi
echo "MediaMTX started (PID: $MEDIAMTX_PID)"

# Start FFmpeg Stream (Camera -> RTSP)
echo "Starting Camera Stream..."
ffmpeg -f v4l2 -framerate 30 -video_size 640x480 -i /dev/video0 \
    -c:v libx264 -preset ultrafast -tune zerolatency \
    -f rtsp rtsp://localhost:8554/live/stream \
    > /tmp/ffmpeg.log 2>&1 &
FFMPEG_PID=$!
sleep 3

# Verify ffmpeg started
if ! kill -0 $FFMPEG_PID 2>/dev/null; then
    echo "Failed to start ffmpeg. Check /tmp/ffmpeg.log"
    cat /tmp/ffmpeg.log
    exit 1
fi
echo "FFmpeg started (PID: $FFMPEG_PID)"

# Set Camera URL for App
export CAMERA_URL="rtsp://localhost:8554/live/stream"

echo "RTSP Stream URL: $CAMERA_URL"
echo "Starting LLM Monitor..."
export SERVER_NAME="127.0.0.1"

# Cleanup function
cleanup() {
    echo "Stopping services..."
    kill $FFMPEG_PID $MEDIAMTX_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

python3 -m src.app
