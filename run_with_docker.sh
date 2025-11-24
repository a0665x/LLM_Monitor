#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting LLM Monitor Docker Setup...${NC}"

# 1. Check for Docker
if ! command -v docker > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not installed or not in PATH.${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# 2. Check for Ollama (Host)
echo "Checking Ollama status on host..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${RED}Error: Ollama is not running on localhost:11434${NC}"
    echo "Please start Ollama on your host machine first."
    exit 1
fi
echo -e "${GREEN}Ollama is running.${NC}"

# 3. Build Docker Image
echo "Building Docker image (this may take a few minutes)..."
docker build -t llm-monitor .

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker build failed.${NC}"
    exit 1
fi

# 4. Run Container
# We use --network="host" to allow the container to easily access the host's Ollama service at localhost:11434
# Add camera device access and volume mount for temp directory
echo -e "${GREEN}Starting container...${NC}"

# Clean up any existing container with the same name
if docker ps -a --format '{{.Names}}' | grep -q "^llm_monitor_app$"; then
    echo "Removing existing container..."
    docker rm -f llm_monitor_app > /dev/null 2>&1
fi

echo "The app will be available at http://localhost:7860"
echo "Press Ctrl+C to stop."

# Create temp directory if it doesn't exist
mkdir -p temp

docker run --rm -it \
    --network="host" \
    --device=/dev/video0:/dev/video0 \
    -v "$(pwd)/temp:/app/temp" \
    --name llm_monitor_app \
    llm-monitor
