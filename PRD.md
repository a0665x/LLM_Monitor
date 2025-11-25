# Product Requirements Document (PRD) - LLM Monitor

## 1. Introduction
The **LLM Monitor** is an AI-powered application designed to assist caregivers in monitoring infants. It uses a camera feed and a local Large Multimodal Model (LMM) to analyze the baby's status in real-time, detecting potential risks and providing alerts.

## 2. Goals & Objectives
- **Real-time Monitoring**: Provide a continuous live video feed of the nursery.
- **Intelligent Analysis**: Use AI to detect unsafe situations (e.g., face covered, climbing out of crib) based on a customizable "Risk Prompt".
- **Privacy First**: Run all inference locally using Ollama, ensuring no video data leaves the device.
- **Interactive QA**: Allow caregivers to ask questions about the current frame (e.g., "Is the baby sleeping?").

## 3. Features

### 3.1 Live Video Feed
- **Description**: Continuous real-time video stream from the connected camera.
- **Technology**: MJPEG streaming via Gradio.
- **User Interaction**: Viewable directly on the main dashboard.

### 3.2 AI Risk Detection
- **Description**: Periodic analysis of video frames against a user-defined "Risk Prompt".
- **Default Prompt**: "A baby crying or in distress, or face covered by blankets."
- **Alerting**: Visual "RISK" state and explanation when a threat is detected.
- **Acknowledgement**: Manual acknowledgement required to clear high-risk alerts.

### 3.3 Interactive Q&A
- **Description**: Chat interface to ask questions about the current scene.
- **Model**: LLaVA (Large Language-and-Vision Assistant) via Ollama.

### 3.4 Health Checks
- **Description**: System status check for Camera connectivity and Ollama API availability.

## 4. Technical Architecture

### 4.1 Technology Stack
- **Language**: Python 3.10+
- **UI Framework**: Gradio 4.x
- **Computer Vision**: OpenCV (cv2) consuming RTSP stream
- **Streaming**: FFmpeg + MediaMTX (RTSP Server)
- **AI Inference**: Ollama (running Vision Language Models like `minicpm-v:8b`)
- **Communication**: HTTP (Gradio), REST API (Ollama)

### 4.2 System Components
1.  **Camera Pipeline**: Captures frames from `/dev/video0` (or mock source).
2.  **Inference Engine**: Orchestrates calls to Ollama for risk assessment.
3.  **Web UI**: Gradio-based interface for visualization and control.

## 5. Hardware Requirements
- **Platform**: NVIDIA Jetson Orin Nano (or compatible Linux system).
- **Camera**: USB Webcam (`/dev/video0`).
- **Memory**: Sufficient RAM to run the 13B parameter model (approx. 8GB+ recommended).
