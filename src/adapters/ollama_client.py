"""Async Ollama HTTP client wrapper."""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:  # pragma: no cover - allow test environments without httpx installed
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Raised when the Ollama API reports a failure."""


@dataclass
class OllamaResponse:
    text: str
    model: str
    latency_ms: int
    confidence: float
    risk: bool


class OllamaClient:
    """Thin wrapper around the Ollama HTTP endpoints."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llava:13b-v1.6-vicuna-q4_0",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def ensure_model(self) -> None:
        """Verify the configured model exists on the local Ollama instance."""
        if httpx is None:  # pragma: no cover - dependency missing during certain tests
            raise OllamaError("httpx is not installed; install requirements to query Ollama.")
        url = f"{self.base_url}/api/tags"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()

        models = {item.get("name") for item in payload.get("models", [])}
        if self.model not in models:
            raise OllamaError(
                f"Model {self.model} not found. Run `ollama pull {self.model}` before launching."
            )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: Optional[bytes] = None,
        model: Optional[str] = None,
    ) -> OllamaResponse:
        """Call the chat endpoint with the provided prompts and optional image."""
        if httpx is None:  # pragma: no cover - dependency missing during certain tests
            raise OllamaError("httpx is not installed; install requirements to query Ollama.")
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }

        if image_bytes:
            # For /api/chat, images must be attached to the specific message
            # Run base64 encoding in thread to avoid blocking
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                b64_img = await loop.run_in_executor(None, lambda: base64.b64encode(image_bytes).decode("utf-8"))
            except RuntimeError:
                b64_img = base64.b64encode(image_bytes).decode("utf-8")
                
            payload["messages"][1]["images"] = [b64_img]

        url = f"{self.base_url}/api/chat"
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("Ollama HTTP error: %s", exc)
                raise OllamaError(str(exc)) from exc
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        message = data.get("message", {})
        text = message.get("content", "")
        latency_ms = int(data.get("total_duration", elapsed_ms * 1000) / 1_000_000)
        if not latency_ms:
            latency_ms = elapsed_ms

        confidence = self._extract_confidence(text)
        risk = self._detect_risk(text, confidence)
        logger.debug("Ollama response: model=%s risk=%s conf=%.2f", self.model, risk, confidence)
        return OllamaResponse(
            text=text,
            model=data.get("model", self.model),
            latency_ms=latency_ms,
            confidence=confidence,
            risk=risk,
        )

    @staticmethod
    def _extract_confidence(text: str) -> float:
        """Attempt to extract a numeric confidence score from the textual answer."""
        marker = "confidence:"
        lowered = text.lower()
        if marker in lowered:
            try:
                value = lowered.split(marker, 1)[1].split()[0]
                return max(0.0, min(1.0, float(value)))
            except (ValueError, IndexError):
                pass
        return 0.5  # neutral default

    @staticmethod
    def _detect_risk(text: str, confidence: float) -> bool:
        """Derive a coarse risk flag from the response text + confidence."""
        keywords = ["unsafe", "danger", "risk", "fall"]
        text_lower = text.lower()
        if any(word in text_lower for word in keywords):
            return confidence >= 0.4
        return confidence >= 0.8


__all__ = ["OllamaClient", "OllamaResponse", "OllamaError"]
