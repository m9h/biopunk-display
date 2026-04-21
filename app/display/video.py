"""
Video clip player — animates PNG sequences on the flipdot display.

A clip is a directory under ``VIDEO_FRAMES_DIR`` containing numbered image
files (``00001.png``, ``00002.png``, ...). Frames are loaded lazily on first
play, converted to the display's column-byte format, cached in memory, and
streamed to the display at a configurable FPS.

Dimensions
----------
The physical display is 14 rows × 30 columns (two stacked 7-row panels).
Images are resized to fit and auto-binarised. The resulting 105-byte buffer
matches the CA convention: ``buf[0:30]`` = top panel, ``buf[30:60]`` = bottom
panel — ``core.fill()`` handles the serial-protocol reordering.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DISPLAY_ROWS = 14
DISPLAY_COLS = 30
FRAME_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')


class VideoPlayer:
    """Plays PNG-sequence clips on the flipdot display."""

    def __init__(self, app=None):
        self._app = None
        self._frames_dir: Optional[Path] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._clip: Optional[str] = None
        self._fps = 12.0
        self._loop = True
        self._cache: dict[str, list[bytes]] = {}
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._frames_dir = Path(app.config.get(
            'VIDEO_FRAMES_DIR',
            os.path.join(os.path.dirname(__file__), '..', '..', 'video', 'frames')
        )).resolve()
        self._frames_dir.mkdir(parents=True, exist_ok=True)
        app.video = self

    # ---- public API ----------------------------------------------------

    def list_clips(self) -> list[dict]:
        """Return metadata for every clip subdirectory."""
        if not self._frames_dir or not self._frames_dir.is_dir():
            return []
        clips = []
        for entry in sorted(self._frames_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith('.'):
                continue
            frames = _list_frame_files(entry)
            clips.append({
                'name': entry.name,
                'frames': len(frames),
            })
        return clips

    def play(self, clip: str, fps: float = 12.0, loop: bool = True) -> bool:
        """Start playing a clip. Stops any currently running clip first."""
        if not clip or not self._frames_dir:
            return False
        clip_dir = (self._frames_dir / clip).resolve()
        # Prevent directory traversal outside the frames root
        if self._frames_dir not in clip_dir.parents and clip_dir != self._frames_dir:
            return False
        if not clip_dir.is_dir():
            return False

        frames = self._load_frames(clip_dir)
        if not frames:
            return False

        self.stop()
        self._clip = clip
        self._fps = max(1.0, min(60.0, float(fps)))
        self._loop = bool(loop)
        self._running = True
        self._thread = threading.Thread(
            target=self._run, args=(frames,), daemon=True, name=f'video-{clip}'
        )
        self._thread.start()
        return True

    def stop(self):
        was_running = self.is_running
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self._clip = None
        if was_running and self._app is not None:
            try:
                self._app.display.clear()
            except Exception:
                log.exception('video clear failed')

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> dict:
        running = self.is_running
        return {
            'running': running,
            'clip': self._clip if running else None,
            'fps': self._fps if running else None,
            'loop': self._loop if running else None,
        }

    # ---- worker --------------------------------------------------------

    def _run(self, frames: list[bytes]):
        frame_interval = 1.0 / self._fps
        try:
            while self._running:
                for buf in frames:
                    if not self._running:
                        return
                    self._render(buf)
                    self._sleep(frame_interval)
                if not self._loop:
                    return
        except Exception:
            log.exception('video thread crashed')
        finally:
            self._running = False

    def _render(self, buf: bytes):
        display = self._app.display
        try:
            with display._lock:
                display.set_frame(buf)
                display.core.fill(buf)
        except Exception:
            log.exception('video render failed')

    def _sleep(self, duration: float):
        end = time.monotonic() + duration
        while self._running:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.05, remaining))

    # ---- frame loading -------------------------------------------------

    def _load_frames(self, clip_dir: Path) -> list[bytes]:
        """Return cached 105-byte buffers for every frame of the clip."""
        cache_key = str(clip_dir)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from PIL import Image
        except ImportError:
            log.warning('Pillow not installed; cannot load video frames')
            return []

        buffers: list[bytes] = []
        for path in _list_frame_files(clip_dir):
            try:
                img = Image.open(path)
                buffers.append(_image_to_buffer(img))
            except Exception:
                log.exception('failed to load frame: %s', path)

        self._cache[cache_key] = buffers
        return buffers

    def invalidate_cache(self, clip: Optional[str] = None):
        """Drop cached frames so next play() reloads from disk."""
        if clip is None:
            self._cache.clear()
        else:
            self._cache.pop(str((self._frames_dir or Path()) / clip), None)


# ---------------------------------------------------------------------------
# Image → 105-byte display buffer
# ---------------------------------------------------------------------------

def _list_frame_files(clip_dir: Path) -> list[Path]:
    return sorted(
        p for p in clip_dir.iterdir()
        if p.is_file() and p.suffix.lower() in FRAME_EXTENSIONS
    )


def _image_to_buffer(img) -> bytes:
    """Convert a PIL image into a 105-byte dual-panel display buffer.

    Images larger than 30×14 are resized (preserving aspect ratio) with
    nearest-neighbour sampling to keep pixel art crisp, then binarised.
    """
    from PIL import Image

    img = img.convert('L')  # grayscale

    w, h = img.size
    if w > DISPLAY_COLS or h > DISPLAY_ROWS:
        scale = min(DISPLAY_COLS / w, DISPLAY_ROWS / h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        img = img.resize((new_w, new_h), Image.NEAREST)
        w, h = img.size

    # Binarise at midpoint; treat >= 128 as "on".
    pixels = img.load()
    buf = bytearray(105)
    for col in range(min(w, DISPLAY_COLS)):
        top_byte = 0
        bottom_byte = 0
        for row in range(min(h, DISPLAY_ROWS)):
            if pixels[col, row] >= 128:
                if row < 7:
                    top_byte |= (1 << (6 - row))
                else:
                    bottom_byte |= (1 << (13 - row))
        buf[col] = top_byte
        if h > 7:
            buf[30 + col] = bottom_byte
    return bytes(buf)
