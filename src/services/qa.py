"""LLaVA QA tester service."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Protocol

from ..pipelines.camera import FrameCapture
from ..adapters.ollama_client import OllamaResponse


class OllamaClientProtocol(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str, image_bytes: Optional[bytes] = None) -> OllamaResponse:  # pragma: no cover - defined elsewhere
        ...


@dataclass
class QAResult:
    question: str
    answer: str
    latency_ms: int
    model: str
    error: Optional[str] = None


class QATester:
    """Throttle and dispatch QA requests to Ollama."""

    def __init__(self, client: OllamaClientProtocol, min_interval: float = 1.0) -> None:
        self.client = client
        self.min_interval = min_interval
        self._last_request_at = 0.0

    async def ask(self, question: str, frame: Optional[FrameCapture]) -> QAResult:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty")

        now = time.monotonic()
        if now - self._last_request_at < self.min_interval:
            raise RuntimeError("QA tester throttled; try again in a moment")

        image_bytes = frame.preview_bytes if frame else None
        response = await self.client.generate(
            system_prompt="You are validating a camera feed for baby safety.",
            user_prompt=question,
            image_bytes=image_bytes,
        )
        self._last_request_at = time.monotonic()
        return QAResult(
            question=question,
            answer=response.text,
            latency_ms=response.latency_ms,
            model=response.model,
        )


__all__ = ["QATester", "QAResult"]
