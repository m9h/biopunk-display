"""
DisplayManager — thin wrapper around the legacy WorkingFlipdotCore.

Provides Flask-friendly access without modifying the proven core code.
"""

import sys
import os
import threading

# Add project root so we can import the legacy core module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class DisplayManager:
    """Wraps WorkingFlipdotCore for use inside Flask."""

    def __init__(self, app=None):
        self._core = None
        self._transitions = None
        self._lock = threading.Lock()
        self._last_frame = bytes(105)  # last buffer sent to display
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        self._port = app.config.get('FLIPDOT_PORT')
        self._baud = app.config.get('FLIPDOT_BAUD', 38400)

    @property
    def core(self):
        """Lazy-init the hardware connection on first use."""
        if self._core is None:
            from core.core import WorkingFlipdotCore
            self._core = WorkingFlipdotCore(
                port=self._port, baud=self._baud
            )
        return self._core

    @property
    def transitions(self):
        """Lazy-import transitions module."""
        if self._transitions is None:
            from transition import transition as t
            self._transitions = t
        return self._transitions

    # -- double-height transitions (use both halves of display) --

    DOUBLE_HEIGHT_TRANSITIONS = {
        'double_scroll', 'double_static', 'double_flash',
        'double_typewriter', 'wide_scroll', 'wide_static',
    }

    # -- convenience methods (thread-safe) --

    def send_message(self, text, transition='righttoleft'):
        """Send a text message to the display with a named transition."""
        if transition in self.DOUBLE_HEIGHT_TRANSITIONS:
            self._send_double(text.upper(), transition)
        else:
            func = getattr(self.transitions, transition, None)
            if func is None:
                func = self.transitions.righttoleft
            with self._lock:
                func(text.upper())

    def _send_double(self, text, transition):
        """Dispatch to double-height font functions."""
        from app.display.fonts import (
            scroll_double, display_double_static,
            flash_double, typewriter_double,
        )
        with self._lock:
            if transition == 'double_scroll':
                scroll_double(self.core, text)
            elif transition == 'double_static':
                display_double_static(self.core, text)
            elif transition == 'double_flash':
                flash_double(self.core, text)
            elif transition == 'double_typewriter':
                typewriter_double(self.core, text)
            elif transition == 'wide_scroll':
                scroll_double(self.core, text, double_wide=True)
            elif transition == 'wide_static':
                display_double_static(self.core, text, double_wide=True)

    def show_static(self, text, justify='center'):
        """Show static text on the display."""
        with self._lock:
            self.core.display_text(text.upper(), justify=justify)

    def set_frame(self, frame_bytes):
        """Store a raw 105-byte frame (for monitor endpoint)."""
        self._last_frame = bytes(frame_bytes[:105])

    @property
    def last_frame(self):
        """Return the last known display frame as a list of ints."""
        return list(self._last_frame)

    def clear(self):
        with self._lock:
            self._last_frame = bytes(105)
            self.core.clear()

    def available_transitions(self):
        """Return list of transition names."""
        return [
            'righttoleft', 'magichat', 'pop', 'dissolve', 'typewriter',
            'matrix_effect', 'bounce', 'plain', 'upnext', 'adventurelook',
            'slide_in_left', 'amdissolve',
            'double_scroll', 'double_static', 'double_flash',
            'double_typewriter', 'wide_scroll', 'wide_static',
        ]
