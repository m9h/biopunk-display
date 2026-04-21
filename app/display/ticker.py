"""
Ticker — looping scrolling-text mode for the flipdot display.

While a ticker is running it owns the display: the message queue pauses
(mirroring the automata-player pattern) and any previously-sent frame is
overwritten each tick.

Modes
-----
  single  — 7-row content rendered in the top panel (legacy column font)
  double  — 14-row content across both panels (double-height font)
  wide    — 14-row with every column doubled (chunky marquee look)

A ticker can also be given a list of *segments*, each with its own mode,
so a single banner can mix single-, double-, and wide-height words.

Each tick slides the text one column left; the text repeats with a gap of
blank columns for visual breathing room. `stop()` clears the display.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

log = logging.getLogger(__name__)

GAP_COLS = 10       # blank columns between loop repetitions
SEGMENT_GAP = 3     # blank columns between mixed-mode segments
VIEW_COLS = 30      # visible width of each panel


class TickerManager:
    """Runs a looping scrolling-text banner in a background thread."""

    def __init__(self, app=None):
        self._app = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._text = ''
        self._mode = 'single'
        self._speed = 0.12
        self._segments: Optional[List[dict]] = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        app.ticker = self

    # ---- control ---------------------------------------------------------

    def start(self, text: str, speed: float = 0.12, mode: str = 'single') -> bool:
        """Start or replace the running ticker. Returns True if accepted."""
        text = (text or '').strip()
        if not text:
            return False
        self.stop()
        self._text = text
        self._speed = max(0.03, min(1.0, float(speed)))
        self._mode = mode if mode in ('single', 'double', 'wide') else 'single'
        self._segments = None
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name='ticker'
        )
        self._thread.start()
        return True

    def start_segments(self, segments: List[dict], speed: float = 0.12) -> bool:
        """Start a mixed-mode ticker made of typed segments.

        Each segment is a dict with keys:
          text: string (required)
          mode: 'single' | 'double' | 'wide' (default 'single')

        Returns True if accepted (at least one non-empty segment).
        """
        cleaned: List[dict] = []
        for seg in segments or []:
            body = (seg.get('text') or '').strip()
            if not body:
                continue
            m = seg.get('mode', 'single')
            if m not in ('single', 'double', 'wide'):
                m = 'single'
            cleaned.append({'text': body, 'mode': m})
        if not cleaned:
            return False

        self.stop()
        self._segments = cleaned
        self._text = ' '.join(s['text'] for s in cleaned)
        self._mode = 'mixed' if len({s['mode'] for s in cleaned}) > 1 else cleaned[0]['mode']
        self._speed = max(0.03, min(1.0, float(speed)))
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name='ticker'
        )
        self._thread.start()
        return True

    def stop(self):
        """Stop the ticker and clear the display."""
        was_running = self.is_running
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        if was_running and self._app is not None:
            try:
                self._app.display.clear()
            except Exception:
                log.exception('ticker clear failed')

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> dict:
        running = self.is_running
        return {
            'running': running,
            'text': self._text if running else None,
            'speed': self._speed if running else None,
            'mode': self._mode if running else None,
            'segments': self._segments if running else None,
        }

    # ---- worker ---------------------------------------------------------

    def _run(self):
        try:
            if self._segments:
                self._run_segments()
            elif self._mode == 'single':
                self._run_single()
            else:
                self._run_double(double_wide=(self._mode == 'wide'))
        except Exception:
            log.exception('ticker thread crashed')

    def _run_segments(self):
        top, bottom = self._render_segments(self._segments)
        # Trailing loop gap so repeats don't run into themselves.
        top = top + b'\x00' * GAP_COLS
        bottom = bottom + b'\x00' * GAP_COLS
        n = len(top)
        if n == 0:
            return

        from app.display.fonts import _build_quadrant_buffer
        offset = 0
        while self._running:
            tw = self._slice(top, offset, VIEW_COLS, n)
            bw = self._slice(bottom, offset, VIEW_COLS, n)
            self._render(_build_quadrant_buffer(tw, bw))
            offset = (offset + 1) % n
            self._sleep(self._speed)

    def _render_segments(self, segments: List[dict]) -> tuple:
        """Render a list of segments to a unified (top, bottom) column stream.

        Single-height segments are placed in the top panel with a blank
        bottom panel beneath them; double/wide segments fill both panels.
        """
        from app.display.fonts import text_to_bytes

        core = self._app.display.core
        gap = b'\x00' * SEGMENT_GAP

        top_parts: List[bytes] = []
        bottom_parts: List[bytes] = []

        for i, seg in enumerate(segments):
            body = seg['text'].upper()
            mode = seg['mode']
            if mode == 'single':
                top = bytes(core.getbytes(body))
                bottom = b'\x00' * len(top)
            elif mode == 'double':
                top, bottom = text_to_bytes(body, double_wide=False)
            else:  # wide
                top, bottom = text_to_bytes(body, double_wide=True)

            if i > 0:
                top_parts.append(gap)
                bottom_parts.append(gap)
            top_parts.append(top)
            bottom_parts.append(bottom)

        return b''.join(top_parts), b''.join(bottom_parts)

    def _run_single(self):
        core = self._app.display.core
        text_bytes = core.getbytes(self._text.upper())
        loop = bytes(text_bytes) + b'\x00' * GAP_COLS
        n = len(loop)
        if n == 0:
            return

        offset = 0
        while self._running:
            window = self._slice(loop, offset, VIEW_COLS, n)
            buf = window + b'\x00' * (105 - VIEW_COLS)
            self._render(buf)
            offset = (offset + 1) % n
            self._sleep(self._speed)

    def _run_double(self, double_wide: bool):
        from app.display.fonts import text_to_bytes, _build_quadrant_buffer

        top, bottom = text_to_bytes(self._text, double_wide=double_wide)
        # text_to_bytes returns equal-length top/bottom; pad just in case.
        width = max(len(top), len(bottom))
        top = top + b'\x00' * (width - len(top)) + b'\x00' * GAP_COLS
        bottom = bottom + b'\x00' * (width - len(bottom)) + b'\x00' * GAP_COLS
        n = len(top)
        if n == 0:
            return

        offset = 0
        while self._running:
            tw = self._slice(top, offset, VIEW_COLS, n)
            bw = self._slice(bottom, offset, VIEW_COLS, n)
            self._render(_build_quadrant_buffer(tw, bw))
            offset = (offset + 1) % n
            self._sleep(self._speed)

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _slice(buf: bytes, offset: int, width: int, n: int) -> bytes:
        """Wrap-around slice: `width` bytes starting at `offset` modulo `n`.

        Handles the case where the window is wider than the source buffer by
        repeating it as many times as needed.
        """
        offset %= n
        if offset + width <= n:
            return bytes(buf[offset:offset + width])
        parts = [buf[offset:]]
        remaining = width - (n - offset)
        while remaining >= n:
            parts.append(buf)
            remaining -= n
        if remaining:
            parts.append(buf[:remaining])
        return b''.join(parts)

    def _render(self, buf: bytes):
        display = self._app.display
        try:
            with display._lock:
                display.set_frame(buf)
                display.core.fill(buf)
        except Exception:
            log.exception('ticker render failed')

    def _sleep(self, duration: float):
        """Interruptible sleep so stop() returns promptly."""
        end = time.monotonic() + duration
        while self._running:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.05, remaining))
