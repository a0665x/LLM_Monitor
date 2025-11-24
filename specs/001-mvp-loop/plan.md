# Implementation Plan: LLM Monitor MVP Loop

**Branch**: `001-mvp-loop` | **Date**: 2025-11-18 | **Spec**: [specs/001-mvp-loop/spec.md](specs/001-mvp-loop/spec.md)
**Input**: Feature specification from `/specs/001-mvp-loop/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Deliver a Python-based MVP that captures frames from `/dev/video0`, runs them through a local
Ollama LLaVA model, and surfaces risk alerts plus a lightweight Q&A tester inside a Gradio UI.
The loop stores a configurable risk prompt, keeps all compute on-device, and exposes readiness
checks for both the webcam and Ollama to prevent silent failures.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11 (Jetson-friendly)  
**Primary Dependencies**: Gradio 4.x, OpenCV (cv2) for camera capture, `httpx` for Ollama API,
`pydantic` for config validation  
**Storage**: Lightweight JSON file persisted on disk for prompt history (`data/risk_prompt.json`)  
**Testing**: pytest + pytest-asyncio for service/unit tests  
**Target Platform**: Linux (Jetson Orin/Nano) with local Ollama server  
**Project Type**: single repo with `src/` application + `tests/`  
**Performance Goals**: Maintain ≥10 FPS capture, ≤2s alert latency, tester answers ≤5s for 95%  
**Constraints**: Local-only execution, GPU/CPU limited (~8GB RAM), no cloud dependencies  
**Scale/Scope**: Single camera feed, one caregiver session at a time (no multi-tenant)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **MVP-First Vision Loop** – Status: PASS. Plan only covers webcam capture → Ollama inference
   → UI alert + tester (diagnostic slice still uses same loop).
2. **Local Ollama Reliability** – Status: PASS. Model pinned to `llava:13b-v1.6-vicuna-q4_0`; readiness
   probe + auto-pull defined in research doc.
3. **Configurable Risk Prompts** – Status: PASS. Sidebar prompt stored in JSON + watchers; need
   to confirm persistence format in research.
4. **Real-Time /dev/video0 Monitoring** – Status: PASS. Plan adopts CameraSource interface +
   `MockCamera` fallback with explicit health reporting.
5. **Transparent Web UI Alerts** – Status: PASS. UI states (monitoring/analyzing/risk) mapped to
   Gradio blocks; still need styling tokens but concept covered.

### Constitution Re-check (Post Phase 1)

Research + design artifacts confirm all gates remain satisfied: model pin + readiness scripts,
JSON prompt store + hot reload, CameraSource fallback, and Gradio UI states documented in the
data model and contracts.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
src/
├── app.py                  # Gradio entrypoint + UI states
├── pipelines/
│   ├── camera.py           # /dev/video0 capture + cadence control
│   └── inference.py        # Ollama request orchestration + alert evaluation
├── services/
│   ├── prompts.py          # prompt storage/versioning
│   ├── readiness.py        # Ollama + camera health checks
│   └── qa.py               # LLaVA Q&A tester
├── adapters/
│   └── ollama_client.py    # HTTP client wrapper
└── utils/
    └── logging.py

tests/
├── unit/
│   ├── test_prompts.py
│   ├── test_camera.py
│   └── test_inference.py
└── integration/
    └── test_ui_states.py
```

**Structure Decision**: Single-project layout rooted at `src/` with logical modules matching
pipeline + service boundaries; tests mirror the same directories for clarity.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
