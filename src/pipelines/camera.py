"""Camera abstractions for the monitoring pipeline."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np

try:  # pragma: no cover - import guarded for environments without OpenCV
    import cv2  # type: ignore
except Exception:  # pragma: no cover - fallback for doc builds
    cv2 = None  # type: ignore


@dataclass
class FrameCapture:
    id: str
    timestamp: str
    source: str
    preview_bytes: bytes
    prompt_version: int
    status: str = "pending"
    error: Optional[str] = None


class CameraError(RuntimeError):
    pass


class CameraSource:
    """Base class for camera implementations."""

    def capture_frame(self, prompt_version: int) -> FrameCapture:  # pragma: no cover - interface only
        raise NotImplementedError

    def health(self) -> dict:  # pragma: no cover - interface only
        raise NotImplementedError


class OpenCVCamera(CameraSource):
    def __init__(self, device: str = "/dev/video0", width: int = 640, height: int = 480, fps: int = 10) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._capture = None

    def _ensure_capture(self) -> None:
        if self._capture is not None:
            return
        if cv2 is None:
            raise CameraError("OpenCV is not available; install opencv-python")
        cap = cv2.VideoCapture(self.device)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not cap.isOpened():
            raise CameraError(f"Unable to open camera device {self.device}")
        self._capture = cap

    def capture_frame(self, prompt_version: int) -> FrameCapture:
        self._ensure_capture()
        assert self._capture is not None
        
        # Flush buffer to get the latest frame (reduced to 1 to prevent blocking)
        self._capture.grab()
            
        success, frame = self._capture.read()
        if not success:
            raise CameraError("Failed to read from camera")

        preview_bytes = _encode_jpeg(frame)
        timestamp = datetime.now(timezone.utc).isoformat()
        return FrameCapture(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            source=self.device,
            preview_bytes=preview_bytes,
            prompt_version=prompt_version,
        )

    def health(self) -> dict:
        try:
            self._ensure_capture()
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
        return {"ok": True, "detail": f"Streaming from {self.device}"}

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class MockCamera(CameraSource):
    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.width = width
        self.height = height
        self._last_frame_time = 0.0
        self._counter = 0

    def capture_frame(self, prompt_version: int) -> FrameCapture:
        now = time.time()
        if now - self._last_frame_time < 0.05:
            time.sleep(0.05)
        self._last_frame_time = now
        self._counter += 1
        frame = self._generate_mock_frame()
        preview_bytes = _encode_jpeg(frame)
        timestamp = datetime.now(timezone.utc).isoformat()
        return FrameCapture(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            source="mock-camera",
            preview_bytes=preview_bytes,
            prompt_version=prompt_version,
        )

    def _generate_mock_frame(self) -> np.ndarray:
        gradient = np.linspace(0, 255, self.width, dtype=np.uint8)
        frame = np.tile(gradient, (self.height, 1))
        frame = np.stack([frame, np.flipud(frame), gradient.reshape(1, -1).repeat(self.height, axis=0)], axis=2)
        frame = frame.astype(np.uint8)
        frame = np.roll(frame, self._counter % self.width, axis=1)
        return frame

    def health(self) -> dict:
        return {"ok": True, "detail": "Mock camera active"}


def _encode_jpeg(frame: np.ndarray) -> bytes:
    if cv2 is None:
        raise CameraError("OpenCV is required for JPEG encoding")
    success, buffer = cv2.imencode(".jpg", frame)
    if not success:
        raise CameraError("Failed to encode frame to JPEG")
    return buffer.tobytes()


__all__ = [
    "FrameCapture",
    "CameraSource",
    "OpenCVCamera",
    "MockCamera",
    "CameraError",
]
