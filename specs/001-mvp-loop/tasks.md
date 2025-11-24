# Tasks — LLM Monitor MVP Loop

## Phase 2 Breakdown

1. **Bootstrap runtime**
   - Create project layout under `src/` and `tests/`.
   - Provide reusable logging + configuration helpers.
2. **Implement loop services**
   - Camera abstraction + mock source for development.
   - Ollama adapter, inference engine, prompt persistence, QA tester, readiness checks.
3. **Ship UI + tests**
   - Gradio Blocks interface with monitoring states, prompt sidebar, QA panel.
   - pytest coverage for prompts, camera, inference, and UI status helpers.
4. **Verification**
   - Run `ruff check .` (when available) and `pytest` before release.
