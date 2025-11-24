"""Inference orchestration for the monitoring loop."""
from __future__ import annotations

import re
import time
import logging
import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, Tuple

from ..adapters.ollama_client import OllamaResponse
from ..services.prompts import PromptStore, RiskPrompt
from .camera import CameraSource, FrameCapture

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    frame_id: str
    model: str
    latency_ms: int
    risk: bool
    confidence: float
    explanation: str


@dataclass
class AlertState:
    state: str
    active_frame_id: Optional[str]
    message: str
    acknowledged_at: Optional[str] = None
    timestamp: str = "" # Added for new pipeline


class OllamaClientProtocol(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str, image_bytes: Optional[bytes] = None, model: Optional[str] = None) -> OllamaResponse:  # pragma: no cover - interface definition only
        ...


class InferenceEngine:
    def __init__(
        self,
        camera: CameraSource,
        prompt_store: PromptStore,
        ollama_client: OllamaClientProtocol,
    ) -> None:
        self.camera = camera
        self.prompt_store = prompt_store
        self.ollama_client = ollama_client
        self.last_frame: Optional[FrameCapture] = None
        
        # Binary classification state
        self.current_risk = False
        
        # Frame logging setup
        self.log_dir = Path("temp")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "llm.log"

    async def process_next_frame(self, scoring_model: str = "minicpm-v:8b", frame: Optional[FrameCapture] = None) -> Tuple[FrameCapture, InferenceResult, AlertState]:
        """
        Captures a frame (if not provided) and runs the inference pipeline.
        """
        prompt = self.prompt_store.load()
        if frame is None:
            frame = self.camera.capture_frame(prompt_version=prompt.version)
        self.last_frame = frame

        start_time = time.time()
        
        # Log Session Start
        self._log_session_start()

        # 1-Stage: Direct Vision Inference
        is_risk, explanation = await self._run_1_stage_inference(frame, prompt.text, scoring_model)
        model_name = scoring_model
        
        # Update state
        self.current_risk = is_risk
        
        # Log frame if risk detected (or always, as per previous request, but let's stick to risk for now to save space, 
        # actually user asked for "logging" generally, let's keep _log_frame called always if we want strictly following "short_cut.jpg")
        # The previous code logged frame always to short_cut.jpg.
        self._log_frame(frame)
        
        latency_ms = int((time.time() - start_time) * 1000)

        result = InferenceResult(
            frame_id=frame.id,
            model=model_name,
            risk=is_risk,
            confidence=1.0 if is_risk else 0.0,
            explanation=explanation,
            latency_ms=latency_ms,
        )

        alert = AlertState(
            state="risk" if is_risk else "monitoring",
            active_frame_id=frame.id,
            message="Risk detected" if is_risk else "Safe",
            timestamp=frame.timestamp,
        )

        logger.info(
            "frame=%s risk=%s conf=%.2f latency=%sms",
            result.frame_id,
            result.risk,
            result.confidence,
            result.latency_ms,
        )

        return frame, result, alert

    async def _run_1_stage_inference(self, frame: FrameCapture, criteria: str, model: str) -> Tuple[bool, str]:
        """1-Stage: Ask VLM directly if the image matches risk criteria."""
        system_prompt = (
            "You are a risk assessment engine. "
            "Analyze the image against the Risk Criteria. "
            "Answer ONLY 'YES' if the image matches the risk criteria, or 'NO' if it does not. "
            "Then provide a brief explanation."
        )
        user_prompt = (
            f"Risk Criteria: {criteria}\n\n"
            "Does this image match the risk criteria? Start with YES or NO."
        )
        
        response = await self.ollama_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_bytes=frame.preview_bytes,
            model=model
        )
        
        self._log_interaction("1-Stage Vision", model, system_prompt, user_prompt, response.text)
        
        text_lower = response.text.lower().strip()
        # Stricter parsing: Check for explicit YES/NO at start, or "yes" word. 
        # Use regex to handle punctuation like "Yes." or "Yes,"
        import re
        
        # Check for "Yes" at the start (ignoring case/whitespace)
        if re.match(r'^\s*(yes|YES)(\b|[.,!])', text_lower):
            is_risk = True
        elif re.match(r'^\s*(no|NO)(\b|[.,!])', text_lower):
            is_risk = False
        else:
            # Fallback: look for "yes" as a whole word anywhere if start is ambiguous
            # But be careful not to match "yesterday" etc.
            is_risk = bool(re.search(r'\byes\b', text_lower))
            
        return is_risk, response.text



    def _log_frame(self, frame: FrameCapture) -> None:
        """Save current frame to temp/short_cut.jpg (non-blocking)."""
        # Run in executor to avoid blocking the event loop with disk I/O
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._save_frame_sync, frame)
        except RuntimeError:
            # Fallback if no loop (e.g. tests)
            self._save_frame_sync(frame)

    def _save_frame_sync(self, frame: FrameCapture) -> None:
        try:
            filename = self.log_dir / "short_cut.jpg"
            import cv2
            import numpy as np
            nparr = np.frombuffer(frame.preview_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            cv2.imwrite(str(filename), img)
        except Exception as e:
            logger.error(f"Failed to log frame: {e}")

    def _log_session_start(self) -> None:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._log_session_start_sync)
        except RuntimeError:
            self._log_session_start_sync()

    def _log_session_start_sync(self) -> None:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            separator = "=" * 80
            with open(self.log_file, "a") as f:
                f.write(f"\n{separator}\n[{timestamp}] SESSION START\n{separator}\n")
        except Exception:
            pass

    def _log_interaction(self, stage: str, model: str, system: str, user: str, output: str) -> None:
        """Log full interaction details (non-blocking)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._log_interaction_sync, stage, model, system, user, output)
        except RuntimeError:
            self._log_interaction_sync(stage, model, system, user, output)

    def _log_interaction_sync(self, stage: str, model: str, system: str, user: str, output: str) -> None:
        try:
            separator = "-" * 80
            log_entry = (
                f"[{stage}]\n"
                f"Model: {model}\n"
                f"System Prompt: {system}\n"
                f"User Prompt: {user}\n"
                f"Output: {output}\n"
                f"{separator}\n"
            )
            with open(self.log_file, "a") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")


__all__ = ["InferenceEngine", "InferenceResult", "AlertState"]
