"""Gradio entrypoint for the LLM Monitor MVP loop."""
from __future__ import annotations

import asyncio
import math
import os
import textwrap
import time
from typing import AsyncGenerator, Optional, Tuple

import numpy as np

try:  # pragma: no cover - import guard for docs
    import gradio as gr  # type: ignore
except ImportError:  # pragma: no cover
    gr = None  # type: ignore

try:  # pragma: no cover - import guard for docs
    import cv2  # type: ignore
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore

from .adapters.ollama_client import OllamaClient
from .pipelines.camera import MockCamera, OpenCVCamera, FrameCapture
from .pipelines.inference import AlertState, InferenceEngine, InferenceResult
from .services.prompts import PromptStore, RiskPrompt
from .services.qa import QATester
from .services.readiness import check_camera, check_ollama
from .utils.logging import configure_logging
import logging

logger = logging.getLogger(__name__)


class MonitoringApp:
    def __init__(
        self,
        camera=None,
        prompt_store: Optional[PromptStore] = None,
        ollama_client: Optional[OllamaClient] = None,
        use_mock_camera: bool = False,
    ) -> None:
        self.prompt_store = prompt_store or PromptStore()
        self.camera = camera or self._select_camera(use_mock_camera=use_mock_camera)
        self.ollama_client = ollama_client or OllamaClient()
        self.engine = InferenceEngine(self.camera, self.prompt_store, self.ollama_client)
        self.qa_tester = QATester(self.ollama_client)
        
        # Auto-analysis state
        self.auto_analyze = False
        self.analysis_interval = 5.0
        self.risk_threshold = 0.5
        self.last_analysis_time = 0.0
        self.current_risk_score = 0.0
        self.current_explanation = ""
        self.current_risk_binary = False
        self.is_analyzing = False
        self.scoring_model = "minicpm-v:8b"

    def _select_camera(self, use_mock_camera: bool):
        if use_mock_camera:
            return MockCamera()
        try:
            return OpenCVCamera()
        except Exception:
            return MockCamera()

    async def stream_camera(self) -> AsyncGenerator[np.ndarray, None]:
        """Continuously yield frames for the live view with visual alerts."""
        while True:
            try:
                t0 = time.perf_counter()
                now = time.time()
                prompt = self.prompt_store.load()
                frame = self.camera.capture_frame(prompt_version=prompt.version)
                t1 = time.perf_counter()
                # Offload decoding and rendering to thread to avoid blocking event loop
                img = await asyncio.to_thread(self._process_frame_sync, frame, now)
                t2 = time.perf_counter()

                if img is not None:
                    # Auto-Analysis Trigger
                    if self.auto_analyze:
                        time_since_last = now - self.last_analysis_time
                        if not self.is_analyzing and time_since_last > self.analysis_interval:
                            logger.info(f"Triggering auto-analysis (Interval: {time_since_last:.2f}s)")
                            # Start analysis in background task
                            asyncio.create_task(self._run_background_analysis(frame))
                        elif self.is_analyzing:
                            logger.debug("Skipping auto-analysis: Already analyzing")
                        else:
                            logger.debug(f"Skipping auto-analysis: Too soon ({time_since_last:.2f}s < {self.analysis_interval}s)")
                    
                    yield img
                    
                    # Log performance metrics (warnings for slow frames)
                    t3 = time.perf_counter()
                    total_loop = t3 - t0
                    if total_loop > 0.25:  # Warn if total loop > 250ms (adjusted for slower cameras)
                        logger.warning(
                            f"Slow frame loop: Total={total_loop:.3f}s, "
                            f"Capture={t1-t0:.3f}s, Decode={t2-t1:.3f}s, Logic={t3-t2:.3f}s"
                        )
                
                await asyncio.sleep(0.01)  # Yield control frequently
            except Exception as e:
                logger.error(f"Stream loop error: {e}")
                await asyncio.sleep(0.1)

    async def _run_background_analysis(self, frame: FrameCapture) -> None:
        """Helper to run analysis without blocking the stream."""
        t_start = time.perf_counter()
        logger.info("Starting background analysis task")
        self.is_analyzing = True
        try:
            # Reuse the frame captured in the stream loop to avoid camera contention
            _, result, alert = await self.engine.process_next_frame(
                scoring_model=self.scoring_model,
                frame=frame
            )
            self.current_risk_binary = result.risk
            self.current_risk_score = result.confidence
            self.current_explanation = result.explanation
            self.last_analysis_time = time.time()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Background analysis failed: {e!r}")
        finally:
            self.is_analyzing = False
            t_end = time.perf_counter()
            logger.info(f"Background analysis task completed in {t_end - t_start:.3f}s")

    async def analyze_once(self) -> Tuple[Optional[np.ndarray], str, str, str]:
        frame, result, alert = await self.engine.process_next_frame(
            scoring_model=self.scoring_model
        )
        # Update state for visual alerts
        self.current_risk_binary = result.risk
        self.current_risk_score = result.confidence
        self.current_explanation = result.explanation
        self.last_analysis_time = time.time()
        
        return (
            self._preview_to_numpy(frame.preview_bytes),
            self._format_alert_state(alert),
            alert.message,
            self._format_result(result),
        )

    def apply_prompt(self, text: str) -> str:
        prompt = self.prompt_store.update(text=text)
        return self._format_prompt(prompt)

    def acknowledge_alert(self) -> Tuple[str, str]:
        alert = self.engine.acknowledge_alert()
        return self._format_alert_state(alert), alert.message

    async def run_health_checks(self) -> str:
        camera_status = check_camera(self.camera)
        ollama_status = await check_ollama(self.ollama_client)
        return (
            f"Camera: {'OK' if camera_status.ok else 'FAULT'} — {camera_status.message}\n"
            f"Ollama: {'OK' if ollama_status.ok else 'FAULT'} — {ollama_status.message}"
        )

    async def ask_question(self, question: str) -> str:
        frame = self.engine.last_frame
        result = await self.qa_tester.ask(question=question, frame=frame)
        return (
            f"Q: {result.question}\nA: {result.answer}\n"
            f"Model: {result.model} | Latency: {result.latency_ms} ms"
        )

    def _format_alert_state(self, alert: AlertState) -> str:
        if alert.state == "risk":
            return "RISK"
        if alert.state == "analyzing":
            return "Analyzing"
        return "Monitoring"

    def _format_result(self, result: InferenceResult) -> str:
        return (
            f"Frame: {result.frame_id}\nModel: {result.model}"
            f"\nRisk: {result.risk} (confidence={result.confidence:.2f})"
            f"\nLatency: {result.latency_ms} ms\nExplanation: {result.explanation}"
        )

    def _format_prompt(self, prompt: RiskPrompt | None = None) -> str:
        prompt = prompt or self.prompt_store.load()
        return f"v{prompt.version} — updated {prompt.updated_at}"

    def _process_frame_sync(self, frame: FrameCapture, now: float) -> Optional[np.ndarray]:
        """Synchronous helper for decoding and rendering."""
        if not frame.preview_bytes or cv2 is None:
            return None
        
        # Decode
        array = np.frombuffer(frame.preview_bytes, dtype=np.uint8)
        img = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if img is None:
            return None
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Visual Alert Effect (Red Flashing)
        if self.current_risk_score > self.risk_threshold:
            # Calculate opacity based on sine wave for breathing effect
            opacity = (math.sin(now * 5) + 1) / 2 * 0.5 + 0.2  # 0.2 to 0.7
            
            # Create red overlay
            overlay = np.full_like(img, (255, 0, 0))
            
            # Blend overlay with original image
            cv2.addWeighted(overlay, opacity, img, 1 - opacity, 0, img)
            
            # Add border
            cv2.rectangle(img, (0, 0), (img.shape[1], img.shape[0]), (255, 0, 0), 10)

        # On-Screen Data Overlay
        if self.auto_analyze:
            # Draw Binary Risk Status
            status_text = "RISK" if self.current_risk_binary else "SAFE"
            status_color = (0, 0, 255) if self.current_risk_binary else (0, 255, 0)
            cv2.putText(img, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 2)
            
            # Draw LLM Explanation
            if self.current_explanation:
                # Wrap text
                lines = textwrap.wrap(self.current_explanation, width=60)
                y0, dy = 70, 25
                for line in lines[:5]:  # Limit to 5 lines to avoid clutter
                    # Outline (Black)
                    cv2.putText(img, line, (10, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
                    # Text (White)
                    cv2.putText(img, line, (10, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    y0 += dy
        
        return img

    def _preview_to_numpy(self, preview: bytes | None) -> Optional[np.ndarray]:
        if not preview or cv2 is None:
            return None
        array = np.frombuffer(preview, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def build_ui(self) -> gr.Blocks:
        if gr is None:  # pragma: no cover - runtime safeguard
            raise RuntimeError("Gradio is not installed. Install requirements.txt to run the UI.")
        prompt = self.prompt_store.load()
        with gr.Blocks(title="LLM Monitor") as demo:
            status = gr.Markdown("Run health check to view status")
            with gr.Row():
                feed = gr.Image(label="Live Feed", type="numpy")
                with gr.Column():
                    state = gr.Textbox(label="State", value="Monitoring", interactive=False)
                    message = gr.Textbox(label="Message", interactive=False)
                    result_log = gr.Textbox(label="Last inference", lines=6, interactive=False)
            with gr.Row():
                prompt_box = gr.Textbox(label="Risk Criteria", value=prompt.text, lines=6)
                with gr.Column():
                    prompt_info = gr.Markdown(self._format_prompt(prompt))
                    
                    # New Controls
                    auto_toggle = gr.Checkbox(label="Enable Auto-Analysis", value=False)
                    
                    # Model Selection
                    model_dropdown = gr.Dropdown(
                        label="Scoring Model", 
                        choices=[
                            "minicpm-v:8b",
                            "llama3.2-vision:11b",
                            "llava:13b",
                            "qwen3-vl:8b",
                            "bakllava:7b",
                            "llava:7b",
                            "llava:13b-v1.6-vicuna-q4_0"
                        ], 
                        value="minicpm-v:8b"
                    )
                    
                    interval_slider = gr.Slider(
                        label="Analysis Interval (s)", 
                        minimum=1, 
                        maximum=60, 
                        value=5, 
                        step=1
                    )
            apply_btn = gr.Button("Apply Prompt")
            analyze_btn = gr.Button("Analyze Next Frame")
            # Removed acknowledge_btn and health_btn

            with gr.Row():
                qa_question = gr.Textbox(label="LLaVA QA", placeholder="What is happening?")
                qa_answer = gr.Textbox(label="QA Result", lines=4, interactive=False)
            qa_btn = gr.Button("Ask LLaVA")

            analyze_btn.click(
                self.analyze_once,
                inputs=None,
                outputs=[feed, state, message, result_log],
            )
            apply_btn.click(
                self.apply_prompt,
                inputs=[prompt_box],
                outputs=[prompt_info],
            )
            # Removed acknowledge_btn.click and health_btn.click
            
            qa_btn.click(
                self.ask_question,
                inputs=[qa_question],
                outputs=[qa_answer],
            )
            
            # Wire up new controls
            def update_settings(auto, interval, model):
                logger.info(f"Settings updated: Auto={auto}, Interval={interval}, Model={model}")
                self.auto_analyze = auto
                self.analysis_interval = interval
                self.scoring_model = model
                
            for input_elem in [auto_toggle, interval_slider, model_dropdown]:
                input_elem.change(
                    update_settings,
                    inputs=[auto_toggle, interval_slider, model_dropdown],
                    outputs=None
                )
            
            # Start streaming on load
            demo.load(self.stream_camera, outputs=[feed])
            
        return demo


def create_app(use_mock_camera: bool | None = None) -> MonitoringApp:
    if use_mock_camera is None:
        use_mock_env = os.getenv("USE_MOCK_CAMERA", "").lower()
        use_mock = use_mock_env in {"1", "true", "yes"}
    else:
        use_mock = use_mock_camera
    return MonitoringApp(use_mock_camera=use_mock)


def main() -> None:
    configure_logging()
    app = create_app()
    demo = app.build_ui()
    server_name = os.getenv("SERVER_NAME", "0.0.0.0")
    server_port = int(os.getenv("SERVER_PORT", "7860"))
    demo.queue().launch(server_name=server_name, server_port=server_port)


if __name__ == "__main__":
    main()
