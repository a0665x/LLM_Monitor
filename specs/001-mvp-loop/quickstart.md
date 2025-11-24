# Quickstart — LLM Monitor MVP Loop

## Prerequisites

1. **Hardware**: Linux machine (Jetson strongly recommended) with webcam exposed as `/dev/video0`.
2. **Python**: 3.11 + `venv`.
3. **Ollama**: Installed locally with access to the `llava:13b-v1.6-vicuna-q4_0` model.

```bash
# Install Ollama if missing (see https://ollama.ai)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required LLaVA model (first run only)
ollama pull llava:13b-v1.6-vicuna-q4_0

# Optional: sanity-check chat template
ollama run llava:13b-v1.6-vicuna-q4_0 <<'EOF'
{{ .System }}
USER: {{ .Prompt }}
ASSISTANT:
EOF
```

## Environment Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt  # will include gradio, opencv-python, httpx, pydantic, pytest
```

Create the data directory used for prompt persistence:

```bash
mkdir -p data
echo '{"version":1,"text":"Watch for baby climbing out of crib","updated_at":"2025-11-18T00:00:00Z"}' \
  > data/risk_prompt.json
```

## Running the MVP

```bash
# Ensure Ollama is online
ollama serve &

# Launch the monitoring UI
python -m src.app
```

The Gradio UI will display:
- Live video feed (left)
- Risk prompt editor + version info (right)
- LLaVA Q&A tester pane below the prompt

## Manual Validation Steps

1. Confirm the status banner shows both `Camera: OK` and `Ollama: OK`. If not, click “Retry
   Health Check” and follow CLI instructions to fix hardware/model issues.
2. Trigger a safe scenario: stand in front of the camera. UI should remain in “Monitoring”
   with occasional “Analyzing…” flash.
3. Trigger a risky scenario (or hold up sample photo). Expect full-screen red overlay with
   timestamp, prompt snippet, and “Acknowledge” button.
4. Edit the prompt text and press “Apply Prompt”. The UI should show the incremented version
   and the next analysis should respect the new wording.
5. Use the LLaVA tester to ask “What is happening?” and verify textual response plus model +
   latency labels. Disconnect Ollama to observe the fallback error message.

## Troubleshooting

- **Camera Offline**: Run `v4l2-ctl --list-devices` to confirm `/dev/video0`, then restart the
  app. Use `python tools/mock_camera.py` for development without hardware.
- **Model Missing**: Re-run `ollama pull llava:13b-v1.6-vicuna-q4_0`. The app surfaces instructions in
  the UI and logs the exact command.
- **Slow Inference**: Lower the capture FPS via `MONITOR_FPS` env var or switch to `MockCamera`
  to validate logic without real-time load.
