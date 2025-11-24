# Research: LLM Monitor MVP Loop

## Task Log

- Research Ollama LLaVA model pinning and readiness probing for local-only inference.
- Determine persistence format for risk prompt history that keeps MVP lightweight.
- Define `/dev/video0` fallback + health reporting when the camera is missing or stalled.
- Capture best practices for streaming Jetson camera frames into Gradio without blocking.
- Select the HTTP client strategy for Ollama requests that avoids starving the main loop.

## Findings

### Decision: Pin `llava:13b-v1.6-vicuna-q4_0` via Ollama with startup installer
- **Rationale**: Model is widely supported, runs on Jetson with quantized weights, and balances
  accuracy with latency; startup check can run `ollama show llava:13b-v1.6-vicuna-q4_0` and auto-run
  `ollama pull` if missing. A `/health/ollama` endpoint will call `GET /api/tags` before UI
  loads to confirm availability.
- **Alternatives considered**: `llava:7b` is faster but struggled with posture detection in
  reference datasets; `llava:34b` requires more VRAM than available on target Jetsons.

### Decision: Use JSON file (`data/risk_prompt.json`) with version counter for prompt storage
- **Rationale**: Single-operator workflow avoids concurrent writes; stdlib `json` keeps
  dependencies minimal. Each update increments `version`, stores timestamp, and persists before
  broadcasting to the inference loop. Also easy to back up or sync if needed.
- **Alternatives considered**: SQLite would add setup overhead; TinyDB would add third-party
  dependency without strong benefits for a single record.

### Decision: Provide `MockCamera` fallback plus explicit `/dev/video0` readiness
- **Rationale**: Implement `CameraSource` interface with `OpenCVCamera` (real device) and
  `MockCamera` (loops sample MP4 or static frame). Health checks open the device and report FPS;
  when unavailable, UI shows “Camera offline” while inference loop pauses to avoid stale frames.
- **Alternatives considered**: Defaulting to last frame risks misleading caretakers; requiring
  hardware before boot would block developer testing.

### Decision: Stream frames to Gradio via generator + shared queue
- **Rationale**: Use `queue.Queue` sized to 2 frames, background thread pushing cv2 frames,
  and Gradio `live=True` image component that consumes JPEG bytes. Prevents UI thread blocking.
- **Alternatives considered**: Direct cv2 capture inside Gradio callback caused dropped frames
  during QA tester requests.

### Decision: Use `httpx.AsyncClient` with timeout budget + circuit breaker for Ollama calls
- **Rationale**: Async client lets inference loop and QA tester share the same event loop
  without blocking; circuit breaker ensures we fail fast and show UI errors when Ollama is down.
- **Alternatives considered**: `requests` is simpler but would require threading to keep the UI
  responsive; native Ollama Python SDK is still experimental and adds implicit dependencies.

### Decision: Skip `uvloop` for now
- **Rationale**: Added complexity on Jetson environments; async workloads are limited and
  offloading inference to Ollama is the main latency. Default asyncio event loop keeps setup
  simpler and aligns with MVP scope.
- **Alternatives considered**: `uvloop` might offer marginal gains but increases debugging
  overhead on ARM64.
