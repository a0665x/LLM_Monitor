# Feature Specification: LLM Monitor MVP Loop

**Feature Branch**: `001-mvp-loop`  
**Created**: 2025-11-18  
**Status**: Draft  
**Input**: User description: "使用gradio webui 界面,去接收即時畫面,並且右側會有risk prompt 填寫, 然後會有一個會有一個簡易的ollama llava測試 就是會去問這個畫面 讓使用者可以提問,測試, 整體專案使用python 建制,初始時會確認ollama是否有對應的vllm模型跟版本 以及使用api方式呼叫這些vllm"

## User Scenarios & Testing *(mandatory)*

> Constitution alignment: Ensure at least one P1 story covers the full webcam → Ollama LLaVA
> inference → UI alert loop, and another story covers live risk prompt editing so the MVP
> remains minimal but testable.

### User Story 1 - Live Monitoring & Alerts (Priority: P1)

As a caregiver I want the Gradio UI to stream `/dev/video0` frames, run them through the
pinned Ollama LLaVA model using my current risk prompt, and show a red overlay when unsafe
behavior is detected so I can intervene immediately.

**Why this priority**: Core MVP loop; without it the system has no value.

**Independent Test**: Launch UI with simulated risky movement, confirm Ollama inference is
called, and the UI transitions to the red alert view containing timestamp + prompt snippet.

**Acceptance Scenarios**:

1. **Given** the webcam feed is healthy, **When** nothing risky occurs, **Then** the UI stays in
   monitoring mode with neutral styling and periodic “analyzing” indicators.
2. **Given** the caregiver defined a risk prompt describing “person in danger,” **When**
   a relevant frame appears, **Then** Ollama classifies it as risky and the UI goes full-screen
   red until acknowledged.

---

### User Story 2 - Risk Prompt Management (Priority: P1)

As a caregiver I want to edit the risk prompt from the Gradio sidebar and apply it without
restarting so I can adapt the detections throughout a monitoring session.

**Why this priority**: Constitution demands configurable prompts for every session.

**Independent Test**: Update the prompt field, submit, observe that the backend uses the new
prompt on the next frame and surfaces the current value + version in the UI.

**Acceptance Scenarios**:

1. **Given** the default prompt, **When** I change the text and press “Apply,” **Then** the UI
   confirms the new prompt version and the backend stores it in an in-memory config file/db.
2. **Given** the server restarts, **When** I open the UI, **Then** the last persisted prompt
   value loads automatically.

---

### User Story 3 - LLaVA Q&A Tester (Priority: P2)

As a developer I want a simple text box to ask the LLaVA model questions about the current or
last analyzed frame so I can validate that Ollama is responding before relying on alerts.

**Why this priority**: Enables diagnosing model output while staying in the MVP UI.

**Independent Test**: Capture a frame, ask “What is happening?” and verify the response
comes back from Ollama with metadata (model/version/latency).

**Acceptance Scenarios**:

1. **Given** the Ollama server is reachable, **When** I ask a question, **Then** the app uses
   the same authenticated API path and returns the model answer plus token usage.
2. **Given** Ollama is down or missing the requested model, **When** I run the tester,
   **Then** the UI displays a clear error and encourages running the setup script.

---

### Edge Cases

- What happens when `/dev/video0` is unavailable or busy?
- How does the system handle Ollama downtime or slow responses?
- What red alert recovery flow is used after an operator acknowledges the prompt?
- How is the LLaVA tester throttled to avoid starving the main inference loop?

## Requirements *(mandatory)*

### Functional Requirements

> Include explicit FRs for (a) webcam frame acquisition defaults, (b) Ollama/LLaVA model
> configuration + readiness, (c) risk prompt storage + live propagation, and (d) UI state
> transitions (monitoring, analyzing, risk/red overlay).

- **FR-001**: System MUST capture frames from `/dev/video0` at ≥10 FPS and expose health status.
- **FR-002**: System MUST verify at startup that the required Ollama LLaVA model (name + version)
  is installed and reachable via the local API.
- **FR-003**: UI MUST display the live feed, show monitoring/analyzing/risk states, and persist
  risk alerts until acknowledgement.
- **FR-004**: Caregivers MUST be able to edit the risk prompt in the sidebar; edits apply to the
  next inference and persist between sessions.
- **FR-005**: The LLaVA tester MUST accept arbitrary questions, send them with the last frame,
  and show responses plus errors.
- **FR-006**: System MUST log every inference request with timestamp, prompt version, and camera
  status.
- **FR-007**: If `/dev/video0` or Ollama is unavailable, the UI MUST show fault status instead of
  stale data.

*Example of marking unclear requirements:*

- **FR-008**: System MUST authenticate users via [NEEDS CLARIFICATION: only local use?]

### Key Entities *(include if feature involves data)*

- **Frame**: Timestamp, raw image/bytes, downsampled preview, associated risk prompt version.
- **RiskPrompt**: Text, version id, last updated timestamp, author/session metadata.
- **InferenceResult**: Frame id, model name/version, risk classification, full response payload,
  latency metrics.
- **QARequest**: Question text, frame reference, response, error code, token usage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can see the red alert overlay triggered by a simulated risk scenario
  within 2 seconds of frame capture.
- **SC-002**: Prompt edits propagate to inference within one frame (~100 ms) without restarts.
- **SC-003**: LLaVA tester answers within 5 seconds for 95% of queries when using the pinned
  model on target hardware (Jetson).
- **SC-004**: Setup routine detects missing Ollama model and guides user to install before UI
  loads, reducing failed inference attempts by 100%.
