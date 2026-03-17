"""
OpenClaw Autonomous Mode — periodic AI-driven display updates.

When enabled, this runs a background loop that periodically asks the
OpenClaw agent to check the display state and decide what to do.
This is what gives the display "a mind of its own."

The loop respects a configurable interval (default 5 minutes) and
can be started/stopped via the API.
"""

import threading
import sys
import time


class AutonomousLoop:
    """Background loop that lets OpenClaw act on its own."""

    def __init__(self, app=None):
        self._app = None
        self._thread = None
        self._running = False
        self._interval = 300  # 5 minutes default
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._interval = app.config.get('OPENCLAW_INTERVAL', 300)
        app.openclaw_auto = self

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not self._app or not self._app.openclaw:
            print('[openclaw-auto] No OpenClaw agent — autonomous mode disabled',
                  file=sys.stderr)
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name='openclaw-auto'
        )
        self._thread.start()
        print(f'[openclaw-auto] Started (interval: {self._interval}s)', file=sys.stderr)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        print('[openclaw-auto] Stopped', file=sys.stderr)

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _loop(self):
        while self._running:
            try:
                self._app.openclaw.autonomous_tick()
            except Exception as e:
                print(f'[openclaw-auto] Error: {e}', file=sys.stderr)

            # Interruptible sleep
            for _ in range(int(self._interval * 10)):
                if not self._running:
                    return
                time.sleep(0.1)
