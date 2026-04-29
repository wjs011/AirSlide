import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import socketio
from fastapi import FastAPI


@dataclass
class VisionResult:
    face_center: Optional[Tuple[int, int]] = None
    gesture: Optional[str] = None


class VisionManager:
    def __init__(self) -> None:
        # TODO: initialize OpenCV/MediaPipe resources here.
        self._lock = asyncio.Lock()

    async def detect_face(self, frame: bytes) -> Optional[Tuple[int, int]]:
        # TODO: replace with real face detection.
        await asyncio.sleep(0)
        return None

    async def recognize_gesture(self, frame: bytes) -> Optional[str]:
        # TODO: replace with real gesture recognition.
        await asyncio.sleep(0)
        return None

    async def process_frame(self, frame: bytes) -> VisionResult:
        # Serialize access to shared resources if needed.
        async with self._lock:
            face_center = await self.detect_face(frame)
            gesture = await self.recognize_gesture(frame)
            return VisionResult(face_center=face_center, gesture=gesture)


app = FastAPI(title="AirSlide Backend")
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
vision_manager = VisionManager()


@sio.event
async def connect(sid: str, environ: Dict[str, Any]) -> None:
    await sio.emit("status", {"event": "connection", "status": "connected"}, to=sid)


@sio.event
async def disconnect(sid: str) -> None:
    return None


def _decode_frame(payload: Any) -> Optional[bytes]:
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)

    if isinstance(payload, str):
        data = payload.split(",")[-1]
        try:
            return base64.b64decode(data)
        except (ValueError, base64.binascii.Error):
            return None

    if isinstance(payload, dict):
        raw = payload.get("data")
        if isinstance(raw, str):
            data = raw.split(",")[-1]
            try:
                return base64.b64decode(data)
            except (ValueError, base64.binascii.Error):
                return None
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)

    return None


async def _run_vision_pipeline(frame: bytes) -> VisionResult:
    # Offload heavy CPU work to avoid blocking the event loop.
    return await vision_manager.process_frame(frame)


@sio.event
async def video_frame(sid: str, data: Any) -> None:
    frame = _decode_frame(data)
    if frame is None:
        await sio.emit("result", {"event": "error", "message": "Invalid frame"}, to=sid)
        return

    result = await _run_vision_pipeline(frame)
    payload: Dict[str, Any] = {}

    if result.face_center is not None:
        payload["face"] = {"event": "face", "center": {"x": result.face_center[0], "y": result.face_center[1]}}

    if result.gesture is not None:
        payload["gesture"] = {"event": "gesture", "action": result.gesture}

    if not payload:
        payload = {"event": "status", "message": "no-signal"}

    await sio.emit("result", payload, to=sid)


socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
