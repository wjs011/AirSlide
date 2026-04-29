import asyncio
import base64
import json
import platform
import re
import shutil
import textwrap
import uuid
import zipfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from xml.etree import ElementTree

import socketio
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
PRESENTATIONS_DIR = STORAGE_DIR / "presentations"
ALLOWED_EXTENSIONS = {".ppt", ".pptx"}
EXPORT_WIDTH = 1920
EXPORT_HEIGHT = 1080

STORAGE_DIR.mkdir(exist_ok=True)
PRESENTATIONS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class VisionResult:
    face_center: Optional[Tuple[int, int]] = None
    gesture: Optional[str] = None


class VisionManager:
    def __init__(self) -> None:
        # Reserved for future camera/gesture work.
        self._lock = asyncio.Lock()

    async def detect_face(self, frame: bytes) -> Optional[Tuple[int, int]]:
        await asyncio.sleep(0)
        return None

    async def recognize_gesture(self, frame: bytes) -> Optional[str]:
        await asyncio.sleep(0)
        return None

    async def process_frame(self, frame: bytes) -> VisionResult:
        async with self._lock:
            face_center = await self.detect_face(frame)
            gesture = await self.recognize_gesture(frame)
            return VisionResult(face_center=face_center, gesture=gesture)


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

    if result.face_center is not None:
        payload["face"] = {
            "event": "face",
            "center": {"x": result.face_center[0], "y": result.face_center[1]},
        }

    if result.gesture is not None:
        payload["gesture"] = {"event": "gesture", "action": result.gesture}

    if not payload:
        payload = {"event": "status", "message": "no-signal"}

    await sio.emit("result", payload, to=sid)


socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")
