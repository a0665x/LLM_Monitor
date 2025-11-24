# Data Model — LLM Monitor MVP Loop

## FrameCapture
- **id**: UUID (generated per frame)
- **timestamp**: ISO 8601 string (captured at acquisition)
- **source**: enum (`/dev/video0`, `mock-file`)
- **raw_path**: filesystem path for full-resolution frame (optional, for debugging)
- **preview_bytes**: base64-encoded JPEG for UI streaming
- **prompt_version**: integer referencing RiskPrompt.version used during inference
- **status**: enum (`pending`, `analyzed`, `error`)
- **error**: optional string with cv2 error description

**Relationships**: One-to-one with `InferenceResult` (if analysis succeeded).  
**Validation**: FPS governor ensures timestamps differ by ≥100 ms; preview bytes limited to
≤200 KB to keep UI responsive.

## RiskPrompt
- **version**: monotonically increasing integer
- **text**: caregiver-defined description of risky behavior (1–1000 chars)
- **updated_at**: ISO timestamp
- **updated_by**: optional identifier (operator nickname)
- **default_flag**: bool indicating whether this is the shipped default

**Relationships**: Referenced by FrameCapture, InferenceResult, QARequest for traceability.  
**Validation**: Reject empty strings; persist file to `data/risk_prompt.json` atomically via
temp file rename.

## PromptHistory
- **entries**: array of `{version, text, updated_at, updated_by}`

**Purpose**: Allows UI to display last few prompts and roll back quickly.  
**Storage**: Same JSON document to avoid new persistence tech.

## InferenceResult
- **frame_id**: FK → FrameCapture.id
- **model**: string (e.g., `llava:13b-v1.6-vicuna-q4_0`)
- **model_digest**: sha hash from `ollama show`
- **latency_ms**: integer
- **risk**: bool (true triggers alert)
- **confidence**: float 0-1
- **explanation**: short text summary for UI (first sentence of LLaVA response)
- **raw_response**: JSON payload stored to disk/logs (optional path)
- **error**: optional string

**Validation**: `latency_ms` must be <5000 for healthy responses; risk requires `confidence`
threshold set by configuration (default 0.5).

## AlertState
- **state**: enum (`monitoring`, `analyzing`, `risk`)
- **active_frame_id**: optional FK to FrameCapture
- **acknowledged_at**: optional timestamp when caregiver cleared alert
- **message**: string displayed in UI (prompt snippet / last error)

**State transitions**:
1. `monitoring` → `analyzing` when new frame dispatched to Ollama.
2. `analyzing` → `risk` when InferenceResult.risk is true; persists until user click “Acknowledge”.
3. `risk` → `monitoring` once acknowledged AND next analyzed frame is safe.
4. Any state → `monitoring` when `/dev/video0` offline; message shows fault reason.

## QARequest
- **id**: UUID
- **question**: text up to 500 chars
- **frame_id**: FK to the latest available FrameCapture (nullable when using uploaded image)
- **response**: string (model answer)
- **latency_ms**: integer
- **model**: string
- **error**: optional string
- **created_at**: timestamp

**Validation**: throttle to 1 request per second using in-memory timestamp; rejects if Ollama
health degraded to protect main inference loop.
