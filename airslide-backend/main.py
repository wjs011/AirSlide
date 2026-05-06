import asyncio
import base64
import json
import platform
import re
import shutil
import textwrap
import time
import uuid
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Tuple
from xml.etree import ElementTree

import socketio
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
PRESENTATIONS_DIR = STORAGE_DIR / "presentations"
ALLOWED_EXTENSIONS = {".ppt", ".pptx"}
EXPORT_WIDTH = 1920
EXPORT_HEIGHT = 1080
PAGE_TURN_COOLDOWN_SECONDS = 5.0
PAGE_TURN_HOLD_SECONDS = 1.0

STORAGE_DIR.mkdir(exist_ok=True)
PRESENTATIONS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class VisionResult:
    face: Optional[Dict[str, Any]] = None
    hand: Optional[Dict[str, Any]] = None
    gesture: Optional[Dict[str, Any]] = None
    debug: Optional[Dict[str, Any]] = None
    status: str = "no-signal"
    latency_ms: int = 0


class VisionFramePayload(BaseModel):
    data: str
    clientId: str = "default"


class ControlCommandPayload(BaseModel):
    action: str


class VisionSettingsPayload(BaseModel):
    cooldownSeconds: Optional[float] = None
    swipeThreshold: Optional[float] = None
    confidenceThreshold: Optional[float] = None


class VisionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._histories: Dict[str, Deque[Tuple[float, float, float]]] = defaultdict(
            lambda: deque(maxlen=12)
        )
        self._previous_frames: Dict[str, Any] = {}
        self._last_action_at: Dict[str, float] = defaultdict(float)
        self._activation_started_at: Dict[str, float] = defaultdict(float)
        self._page_turn_armed: Dict[str, bool] = defaultdict(bool)
        self._opencv_error: Optional[str] = None
        self._mediapipe_error: Optional[str] = None
        self.cooldown_seconds = PAGE_TURN_COOLDOWN_SECONDS
        self.swipe_threshold = 0.14
        self.confidence_threshold = 0.45

        try:
            import cv2
            import numpy as np

            self.cv2 = cv2
            self.np = np
            cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            self.face_cascade = cv2.CascadeClassifier(str(cascade_path))
        except Exception as exc:
            self.cv2 = None
            self.np = None
            self.face_cascade = None
            self._opencv_error = str(exc)

        try:
            import mediapipe as mp

            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=0,
                min_detection_confidence=0.55,
                min_tracking_confidence=0.5,
            )
        except Exception as exc:
            self.mp_hands = None
            self.hands = None
            self._mediapipe_error = str(exc)

    def _empty_result(self, started_at: float, status: str = "no-signal") -> VisionResult:
        return VisionResult(status=status, latency_ms=int((time.perf_counter() - started_at) * 1000))

    def _decode_image(self, frame: bytes) -> Optional[Any]:
        if self.cv2 is None or self.np is None:
            return None

        buffer = self.np.frombuffer(frame, dtype=self.np.uint8)
        image = self.cv2.imdecode(buffer, self.cv2.IMREAD_COLOR)
        return image

    def _detect_face(self, image: Any) -> Optional[Dict[str, Any]]:
        if self.cv2 is None or self.face_cascade is None or self.face_cascade.empty():
            return None

        height, width = image.shape[:2]
        gray = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=4)
        if len(faces) == 0:
            return None

        x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
        face_width_ratio = max(w / width, 0.01)
        distance_meters = max(0.7, min(4.8, 0.55 / face_width_ratio))

        return {
            "box": {
                "x": round(x / width, 4),
                "y": round(y / height, 4),
                "width": round(w / width, 4),
                "height": round(h / height, 4),
            },
            "center": {
                "x": round((x + w / 2) / width, 4),
                "y": round((y + h / 2) / height, 4),
            },
            "confidence": 0.86,
            "distanceMeters": round(distance_meters, 1),
        }

    def _detect_hand(self, image: Any, face: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if self.cv2 is None or self.np is None:
            return None

        height, width = image.shape[:2]
        blurred = self.cv2.GaussianBlur(image, (5, 5), 0)
        ycrcb = self.cv2.cvtColor(blurred, self.cv2.COLOR_BGR2YCrCb)
        lower = self.np.array([0, 133, 77], dtype=self.np.uint8)
        upper = self.np.array([255, 173, 127], dtype=self.np.uint8)
        mask = self.cv2.inRange(ycrcb, lower, upper)

        if face is not None:
            box = face["box"]
            x1 = max(int((box["x"] - 0.04) * width), 0)
            y1 = max(int((box["y"] - 0.08) * height), 0)
            x2 = min(int((box["x"] + box["width"] + 0.04) * width), width)
            y2 = min(int((box["y"] + box["height"] + 0.08) * height), height)
            mask[y1:y2, x1:x2] = 0

        kernel = self.np.ones((5, 5), self.np.uint8)
        mask = self.cv2.morphologyEx(mask, self.cv2.MORPH_OPEN, kernel, iterations=1)
        mask = self.cv2.morphologyEx(mask, self.cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = self.cv2.findContours(mask, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)
        min_area = width * height * max(0.003, self.confidence_threshold * 0.012)
        candidates = [contour for contour in contours if self.cv2.contourArea(contour) > min_area]
        if not candidates:
            return None

        contour = max(candidates, key=self.cv2.contourArea)
        x, y, w, h = self.cv2.boundingRect(contour)
        moments = self.cv2.moments(contour)
        if moments["m00"] == 0:
            center_x = x + w / 2
            center_y = y + h / 2
        else:
            center_x = moments["m10"] / moments["m00"]
            center_y = moments["m01"] / moments["m00"]

        hull = self.cv2.convexHull(contour)
        hull_area = max(self.cv2.contourArea(hull), 1)
        contour_area = self.cv2.contourArea(contour)
        fill_ratio = contour_area / hull_area
        pose = "open_hand" if fill_ratio < 0.82 or w > h * 0.75 else "pointing"

        return {
            "center": {"x": round(center_x / width, 4), "y": round(center_y / height, 4)},
            "box": {
                "x": round(x / width, 4),
                "y": round(y / height, 4),
                "width": round(w / width, 4),
                "height": round(h / height, 4),
            },
            "pose": pose,
            "source": "opencv-skin",
            "confidence": round(min(0.96, max(0.45, contour_area / (width * height * 0.05))), 2),
        }

    def _detect_motion_hand(
        self,
        client_id: str,
        image: Any,
        face: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if self.cv2 is None or self.np is None:
            return None

        height, width = image.shape[:2]
        gray = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2GRAY)
        gray = self.cv2.GaussianBlur(gray, (15, 15), 0)
        previous = self._previous_frames.get(client_id)
        self._previous_frames[client_id] = gray
        if previous is None:
            return None

        diff = self.cv2.absdiff(previous, gray)
        _, mask = self.cv2.threshold(diff, 18, 255, self.cv2.THRESH_BINARY)
        kernel = self.np.ones((9, 9), self.np.uint8)
        mask = self.cv2.dilate(mask, kernel, iterations=2)
        mask = self.cv2.morphologyEx(mask, self.cv2.MORPH_CLOSE, kernel, iterations=1)

        if face is not None:
            box = face["box"]
            x1 = max(int((box["x"] - 0.08) * width), 0)
            y1 = max(int((box["y"] - 0.12) * height), 0)
            x2 = min(int((box["x"] + box["width"] + 0.08) * width), width)
            y2 = min(int((box["y"] + box["height"] + 0.12) * height), height)
            mask[y1:y2, x1:x2] = 0

        contours, _ = self.cv2.findContours(mask, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)
        min_area = width * height * 0.01
        candidates = [contour for contour in contours if self.cv2.contourArea(contour) > min_area]
        if not candidates:
            return None

        contour = max(candidates, key=self.cv2.contourArea)
        x, y, w, h = self.cv2.boundingRect(contour)
        moments = self.cv2.moments(contour)
        if moments["m00"] == 0:
            center_x = x + w / 2
            center_y = y + h / 2
        else:
            center_x = moments["m10"] / moments["m00"]
            center_y = moments["m01"] / moments["m00"]

        contour_area = self.cv2.contourArea(contour)
        return {
            "center": {"x": round(center_x / width, 4), "y": round(center_y / height, 4)},
            "box": {
                "x": round(x / width, 4),
                "y": round(y / height, 4),
                "width": round(w / width, 4),
                "height": round(h / height, 4),
            },
            "pose": "motion",
            "source": "opencv-motion",
            "confidence": round(min(0.92, max(0.5, contour_area / (width * height * 0.08))), 2),
        }

    def _detect_landmark_hand(self, image: Any) -> Optional[Dict[str, Any]]:
        if self.cv2 is None or self.hands is None:
            return None

        rgb = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self.hands.process(rgb)
        if not result.multi_hand_landmarks:
            return None

        landmarks = result.multi_hand_landmarks[0].landmark
        xs = [point.x for point in landmarks]
        ys = [point.y for point in landmarks]
        x1 = max(0.0, min(xs))
        y1 = max(0.0, min(ys))
        x2 = min(1.0, max(xs))
        y2 = min(1.0, max(ys))
        confidence = result.multi_handedness[0].classification[0].score if result.multi_handedness else 0.72

        fingers = {
            "index": self._is_finger_extended(landmarks, 8, 6),
            "middle": self._is_finger_extended(landmarks, 12, 10),
            "ring": self._is_finger_extended(landmarks, 16, 14),
            "pinky": self._is_finger_extended(landmarks, 20, 18),
            "thumb": self._is_thumb_extended(landmarks),
        }
        page_turn_ready = (
            fingers["index"]
            and fingers["middle"]
            and not fingers["pinky"]
            and not fingers["ring"]
        )

        return {
            "center": {
                "x": round((landmarks[0].x + landmarks[9].x) / 2, 4),
                "y": round((landmarks[0].y + landmarks[9].y) / 2, 4),
            },
            "box": {
                "x": round(x1, 4),
                "y": round(y1, 4),
                "width": round(max(0.01, x2 - x1), 4),
                "height": round(max(0.01, y2 - y1), 4),
            },
            "pose": "page_turn_ready" if page_turn_ready else "landmark_hand",
            "source": "mediapipe-hands",
            "confidence": round(max(0.55, min(0.98, confidence)), 2),
            "fingers": fingers,
        }

    def _is_finger_extended(self, landmarks: Any, tip_index: int, pip_index: int) -> bool:
        return landmarks[tip_index].y < landmarks[pip_index].y - 0.025

    def _is_thumb_extended(self, landmarks: Any) -> bool:
        tip = landmarks[4]
        ip = landmarks[3]
        mcp = landmarks[2]
        lateral_extension = abs(tip.x - mcp.x) > abs(ip.x - mcp.x) + 0.035
        upward_extension = tip.y < mcp.y - 0.035
        return lateral_extension or upward_extension

    def _classify_motion(
        self,
        client_id: str,
        hand: Optional[Dict[str, Any]],
        landmark_hand: Optional[Dict[str, Any]],
        motion_hand: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        now = time.perf_counter()
        pose_matched = landmark_hand is not None and landmark_hand["pose"] == "page_turn_ready"
        cooldown_remaining = max(0.0, self.cooldown_seconds - (now - self._last_action_at[client_id]))

        if pose_matched:
            if self._activation_started_at[client_id] == 0.0:
                self._activation_started_at[client_id] = now
            hold_elapsed = now - self._activation_started_at[client_id]
            if hold_elapsed >= PAGE_TURN_HOLD_SECONDS and cooldown_remaining <= 0:
                self._page_turn_armed[client_id] = True
        else:
            self._activation_started_at[client_id] = 0.0

        hold_progress = 0.0
        if self._activation_started_at[client_id] > 0.0:
            hold_progress = min(1.0, (now - self._activation_started_at[client_id]) / PAGE_TURN_HOLD_SECONDS)

        if hand is None:
            self._histories[client_id].clear()
            self._page_turn_armed[client_id] = False
            return None, {
                "pageTurnPoseMatched": False,
                "pageTurnHoldProgress": 0.0,
                "pageTurnHoldSeconds": PAGE_TURN_HOLD_SECONDS,
                "pageTurnArmed": False,
                "pageTurnCooldownRemaining": round(cooldown_remaining, 2),
            }

        if not self._page_turn_armed[client_id]:
            self._histories[client_id].clear()
            return {
                "name": "page-turn-hold" if pose_matched else hand["pose"],
                "action": "pointer" if hand["pose"] in {"pointing", "motion", "landmark_hand"} else "open_hand",
                "confidence": hand["confidence"],
            }, {
                "pageTurnPoseMatched": pose_matched,
                "pageTurnHoldProgress": round(hold_progress, 2),
                "pageTurnHoldSeconds": PAGE_TURN_HOLD_SECONDS,
                "pageTurnArmed": False,
                "pageTurnCooldownRemaining": round(cooldown_remaining, 2),
            }

        tracking_hand = motion_hand or landmark_hand or hand
        center = tracking_hand["center"]
        history = self._histories[client_id]
        history.append((now, center["x"], center["y"]))

        action: Optional[str] = None
        if len(history) >= 4 and cooldown_remaining <= 0:
            first_time, first_x, first_y = history[0]
            last_time, last_x, last_y = history[-1]
            dx = last_x - first_x
            dy = abs(last_y - first_y)
            duration = max(last_time - first_time, 0.001)

            if 0.12 <= duration <= 2.4 and abs(dx) > self.swipe_threshold and dy < 0.32:
                action = "next"
                self._last_action_at[client_id] = now
                self._page_turn_armed[client_id] = False
                self._activation_started_at[client_id] = 0.0
                history.clear()

        return {
            "name": "page-turn-next" if action == "next" else "page-turn-armed",
            "action": action or "open_hand",
            "confidence": tracking_hand["confidence"],
        }, {
            "pageTurnPoseMatched": pose_matched,
            "pageTurnHoldProgress": round(hold_progress, 2),
            "pageTurnHoldSeconds": PAGE_TURN_HOLD_SECONDS,
            "pageTurnArmed": self._page_turn_armed[client_id],
            "pageTurnCooldownRemaining": round(
                max(0.0, self.cooldown_seconds - (time.perf_counter() - self._last_action_at[client_id])),
                2,
            ),
        }

    async def process_frame(self, frame: bytes, client_id: str = "default") -> VisionResult:
        started_at = time.perf_counter()
        async with self._lock:
            image = self._decode_image(frame)
            if image is None:
                return self._empty_result(started_at, "opencv-unavailable")

            face = self._detect_face(image)
            landmark_hand = self._detect_landmark_hand(image)
            skin_hand = self._detect_hand(image, face)
            motion_hand = self._detect_motion_hand(client_id, image, face)
            if landmark_hand is not None:
                hand = landmark_hand
            elif skin_hand is not None and motion_hand is not None:
                hand = skin_hand if skin_hand["confidence"] >= motion_hand["confidence"] + 0.12 else motion_hand
            else:
                hand = skin_hand or motion_hand
            gesture, gesture_debug = self._classify_motion(client_id, hand, landmark_hand, motion_hand)
            status = "detected" if face or hand else "no-signal"
            debug = {
                "mediapipeAvailable": self.hands is not None,
                "mediapipeError": self._mediapipe_error,
                "opencvAvailable": self.cv2 is not None,
                "opencvError": self._opencv_error,
                "handSource": hand.get("source") if hand else None,
                "pageTurnCooldownSeconds": self.cooldown_seconds,
                **gesture_debug,
            }
            return VisionResult(
                face=face,
                hand=hand,
                gesture=gesture,
                debug=debug,
                status=status,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )

    def update_settings(self, settings: VisionSettingsPayload) -> Dict[str, float]:
        if settings.cooldownSeconds is not None:
            self.cooldown_seconds = PAGE_TURN_COOLDOWN_SECONDS
        if settings.swipeThreshold is not None:
            self.swipe_threshold = min(0.5, max(0.08, settings.swipeThreshold))
        if settings.confidenceThreshold is not None:
            self.confidence_threshold = min(0.95, max(0.2, settings.confidenceThreshold))
        return self.settings()

    def settings(self) -> Dict[str, float]:
        return {
            "cooldownSeconds": self.cooldown_seconds,
            "swipeThreshold": self.swipe_threshold,
            "confidenceThreshold": self.confidence_threshold,
        }


app = FastAPI(title="AirSlide Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=STORAGE_DIR), name="media")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
vision_manager = VisionManager()


class PresentationController:
    def __init__(self) -> None:
        self._powerpoint = None

    def _connect_powerpoint(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            self._powerpoint = win32com.client.GetActiveObject("PowerPoint.Application")
            return True
        except Exception:
            self._powerpoint = None
            return False

    def _send_key(self, key: str) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys(key)
            return True
        except Exception:
            return False

    def execute(self, action: str) -> Dict[str, Any]:
        action = action.lower().strip()
        if action not in {"next", "previous", "start", "end", "pause"}:
            raise ValueError("Unsupported presentation action")

        method = "keyboard"
        powerpoint_ok = self._connect_powerpoint()
        if powerpoint_ok and self._powerpoint is not None:
            try:
                if action == "next":
                    self._powerpoint.ActivePresentation.SlideShowWindow.View.Next()
                elif action == "previous":
                    self._powerpoint.ActivePresentation.SlideShowWindow.View.Previous()
                elif action == "start":
                    self._powerpoint.ActivePresentation.SlideShowSettings.Run()
                elif action == "end":
                    self._powerpoint.ActivePresentation.SlideShowWindow.View.Exit()
                elif action == "pause":
                    self._send_key(" ")
                return {"action": action, "executed": True, "method": "powerpoint-com"}
            except Exception:
                method = "keyboard-fallback"

        key_map = {
            "next": "{RIGHT}",
            "previous": "{LEFT}",
            "start": "{F5}",
            "end": "{ESC}",
            "pause": " ",
        }
        executed = self._send_key(key_map[action])
        return {"action": action, "executed": executed, "method": method}


presentation_controller = PresentationController()


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    return name or "presentation.pptx"


def _natural_slide_key(path: Path) -> Tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    if match:
        return int(match.group(1)), path.name
    return 10**9, path.name


def _normalise_exported_images(slides_dir: Path) -> list[Path]:
    images = sorted(
        [item for item in slides_dir.iterdir() if item.suffix.lower() in {".png", ".jpg", ".jpeg"}],
        key=_natural_slide_key,
    )
    normalised: list[Path] = []

    for index, image in enumerate(images, start=1):
        extension = ".jpg" if image.suffix.lower() in {".jpg", ".jpeg"} else ".png"
        target = slides_dir / f"slide-{index:03d}{extension}"
        if image.resolve() != target.resolve():
            if target.exists():
                target.unlink()
            image.replace(target)
        normalised.append(target)

    return normalised


def _export_with_powerpoint(source: Path, slides_dir: Path) -> list[Path]:
    if platform.system() != "Windows":
        raise RuntimeError("PowerPoint export is only available on Windows.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("pywin32 is not installed.") from exc

    pythoncom.CoInitialize()
    powerpoint = None
    presentation = None
    try:
        powerpoint = win32com.client.DispatchEx("PowerPoint.Application")
        powerpoint.DisplayAlerts = 0
        presentation = powerpoint.Presentations.Open(
            str(source),
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )
        presentation.Export(str(slides_dir), "PNG", EXPORT_WIDTH, EXPORT_HEIGHT)
    finally:
        if presentation is not None:
            presentation.Close()
        if powerpoint is not None:
            powerpoint.Quit()
        pythoncom.CoUninitialize()

    slides = _normalise_exported_images(slides_dir)
    if not slides:
        raise RuntimeError("PowerPoint did not export any slide image.")
    return slides


def _extract_pptx_text(source: Path) -> list[list[str]]:
    slide_name_pattern = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
    text_namespace = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"

    with zipfile.ZipFile(source) as archive:
        slide_names = sorted(
            [name for name in archive.namelist() if slide_name_pattern.match(name)],
            key=lambda name: int(slide_name_pattern.match(name).group(1)),  # type: ignore[union-attr]
        )
        slides: list[list[str]] = []
        for slide_name in slide_names:
            root = ElementTree.fromstring(archive.read(slide_name))
            texts = [
                node.text.strip()
                for node in root.iter(text_namespace)
                if node.text and node.text.strip()
            ]
            slides.append(texts or ["空白页"])

    if not slides:
        raise RuntimeError("No slides were found in the PPTX file.")
    return slides


def _svg_text_lines(lines: list[str], start_y: int, font_size: int, max_lines: int) -> str:
    rendered: list[str] = []
    y = start_y
    for raw_line in lines:
        for line in textwrap.wrap(raw_line, width=34, break_long_words=True) or [""]:
            if len(rendered) >= max_lines:
                rendered.append(
                    f'<text x="190" y="{y}" fill="#61708a" font-size="{font_size}">...</text>'
                )
                return "\n".join(rendered)
            rendered.append(
                f'<text x="190" y="{y}" fill="#34445c" font-size="{font_size}">{escape(line)}</text>'
            )
            y += int(font_size * 1.55)
    return "\n".join(rendered)


def _render_text_slides_as_svg(source: Path, slides_dir: Path) -> list[Path]:
    if source.suffix.lower() != ".pptx":
        raise RuntimeError("Text fallback only supports .pptx files.")

    slide_texts = _extract_pptx_text(source)
    generated: list[Path] = []

    for index, texts in enumerate(slide_texts, start=1):
        title = texts[0] if texts else f"第 {index} 页"
        body = texts[1:] if len(texts) > 1 else ["该页未提取到正文内容。"]
        body_markup = _svg_text_lines(body, start_y=345, font_size=42, max_lines=11)
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{EXPORT_WIDTH}" height="{EXPORT_HEIGHT}" viewBox="0 0 {EXPORT_WIDTH} {EXPORT_HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#f8fbff"/>
      <stop offset="100%" stop-color="#e8f0fb"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="#1666e8"/>
      <stop offset="100%" stop-color="#19b7a2"/>
    </linearGradient>
  </defs>
  <rect width="1920" height="1080" fill="url(#bg)"/>
  <circle cx="1670" cy="160" r="290" fill="#dcecff" opacity="0.7"/>
  <circle cx="160" cy="920" r="360" fill="#d9f4ee" opacity="0.55"/>
  <rect x="110" y="86" width="1700" height="908" rx="28" fill="white" opacity="0.82"/>
  <rect x="110" y="86" width="1700" height="908" rx="28" fill="none" stroke="#d8e3f2" stroke-width="2"/>
  <text x="190" y="220" fill="#10213d" font-family="Microsoft YaHei, Arial, sans-serif" font-size="72" font-weight="700">{escape(title)}</text>
  <rect x="190" y="265" width="160" height="8" rx="4" fill="url(#accent)"/>
  <g font-family="Microsoft YaHei, Arial, sans-serif">
{body_markup}
  </g>
  <text x="1660" y="925" fill="#73829a" font-family="Microsoft YaHei, Arial, sans-serif" font-size="34">第 {index} 页</text>
  <text x="190" y="925" fill="#8a96aa" font-family="Microsoft YaHei, Arial, sans-serif" font-size="30">AirSlide 文本预览模式</text>
</svg>
"""
        target = slides_dir / f"slide-{index:03d}.svg"
        target.write_text(svg, encoding="utf-8")
        generated.append(target)

    return generated


def _convert_presentation(source: Path, slides_dir: Path) -> tuple[list[Path], str]:
    slides_dir.mkdir(parents=True, exist_ok=True)

    try:
        return _export_with_powerpoint(source, slides_dir), "powerpoint"
    except Exception:
        shutil.rmtree(slides_dir, ignore_errors=True)
        slides_dir.mkdir(parents=True, exist_ok=True)
        return _render_text_slides_as_svg(source, slides_dir), "text-fallback"


def _write_manifest(
    presentation_id: str,
    original_name: str,
    slide_paths: list[Path],
    conversion_mode: str,
    presentation_dir: Path,
) -> dict[str, Any]:
    manifest = {
        "id": presentation_id,
        "filename": original_name,
        "slideCount": len(slide_paths),
        "conversionMode": conversion_mode,
        "slides": [
            {
                "index": index,
                "url": f"/media/presentations/{presentation_id}/slides/{slide_path.name}",
                "width": EXPORT_WIDTH,
                "height": EXPORT_HEIGHT,
            }
            for index, slide_path in enumerate(slide_paths, start=1)
        ],
    }
    (presentation_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/presentations")
async def upload_presentation(file: UploadFile = File(...)) -> dict[str, Any]:
    original_name = _safe_filename(file.filename or "")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="只支持上传 .ppt 或 .pptx 文件")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    presentation_id = uuid.uuid4().hex
    presentation_dir = PRESENTATIONS_DIR / presentation_id
    slides_dir = presentation_dir / "slides"
    source_path = presentation_dir / f"source{extension}"
    presentation_dir.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)

    try:
        slide_paths, conversion_mode = await run_in_threadpool(
            _convert_presentation,
            source_path,
            slides_dir,
        )
    except Exception as exc:
        shutil.rmtree(presentation_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"PPT 转换失败：{exc}") from exc

    if not slide_paths:
        shutil.rmtree(presentation_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="PPT 中没有可放映的页面")

    return _write_manifest(
        presentation_id,
        original_name,
        slide_paths,
        conversion_mode,
        presentation_dir,
    )


@app.get("/api/presentations/{presentation_id}")
async def get_presentation(presentation_id: str) -> dict[str, Any]:
    manifest_path = PRESENTATIONS_DIR / presentation_id / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="未找到该演示文稿")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@app.post("/api/vision/frame")
async def process_vision_frame(payload: VisionFramePayload) -> dict[str, Any]:
    frame = _decode_frame(payload.data)
    if frame is None:
        raise HTTPException(status_code=400, detail="视频帧格式无效")

    result = await vision_manager.process_frame(frame, payload.clientId)
    return {
        "status": result.status,
        "face": result.face,
        "hand": result.hand,
        "gesture": result.gesture,
        "debug": result.debug,
        "latencyMs": result.latency_ms,
    }


@app.get("/api/vision/settings")
async def get_vision_settings() -> Dict[str, float]:
    return vision_manager.settings()


@app.post("/api/vision/settings")
async def update_vision_settings(payload: VisionSettingsPayload) -> Dict[str, float]:
    return vision_manager.update_settings(payload)


@app.post("/api/presentation/control")
async def control_presentation(payload: ControlCommandPayload) -> Dict[str, Any]:
    try:
        return presentation_controller.execute(payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    return await vision_manager.process_frame(frame)


@sio.event
async def video_frame(sid: str, data: Any) -> None:
    frame = _decode_frame(data)
    if frame is None:
        await sio.emit("result", {"event": "error", "message": "Invalid frame"}, to=sid)
        return

    result = await _run_vision_pipeline(frame)
    payload: Dict[str, Any] = {}

    if result.face is not None:
        payload["face"] = {"event": "face", **result.face}

    if result.hand is not None:
        payload["hand"] = {"event": "hand", **result.hand}

    if result.gesture is not None:
        payload["gesture"] = {"event": "gesture", **result.gesture}

    if not payload:
        payload = {"event": "status", "message": result.status}

    await sio.emit("result", payload, to=sid)


socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")
