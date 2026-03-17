"""
Chapter 9: Webcam presence detection via LifeCam HD-3000.

Detects when someone approaches (motion/presence) and triggers
a greeting or idle animation on the flipdot display.

Uses OpenCV for frame differencing — no ML model needed.
"""

import threading
import sys
import time


class WebcamInput:
    """Motion/presence detection that feeds the flipdot message queue."""

    def __init__(self, app=None):
        self._thread = None
        self._running = False
        self._app = None
        self._present = False
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._device = app.config.get('WEBCAM_DEVICE', 0)  # /dev/video0
        self._threshold = app.config.get('WEBCAM_MOTION_THRESHOLD', 5000)
        self._greeting = app.config.get('WEBCAM_GREETING', 'WELCOME')
        self._farewell = app.config.get('WEBCAM_FAREWELL', 'GOODBYE')
        self._cooldown = app.config.get('WEBCAM_COOLDOWN', 30)  # seconds
        self._check_interval = app.config.get('WEBCAM_CHECK_INTERVAL', 1.0)
        app.webcam_input = self

    @property
    def is_present(self):
        return self._present

    def start(self):
        """Start webcam monitoring."""
        if self._thread is not None and self._thread.is_alive():
            return

        try:
            import cv2  # noqa: F401
        except ImportError:
            print('[webcam] opencv not installed — webcam input disabled',
                  file=sys.stderr)
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name='webcam-input'
        )
        self._thread.start()
        print(f'[webcam] Monitoring /dev/video{self._device}...', file=sys.stderr)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _monitor_loop(self):
        """Capture frames and detect motion via frame differencing."""
        import cv2

        cap = cv2.VideoCapture(self._device)
        if not cap.isOpened():
            print(f'[webcam] Cannot open /dev/video{self._device}', file=sys.stderr)
            return

        # Read initial frame
        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            return

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)

        last_trigger = 0
        no_motion_count = 0

        try:
            while self._running:
                time.sleep(self._check_interval)

                ret, frame = cap.read()
                if not ret:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                delta = cv2.absdiff(prev_gray, gray)
                thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                motion_score = thresh.sum() // 255

                prev_gray = gray

                now = time.time()

                if motion_score > self._threshold:
                    no_motion_count = 0
                    if not self._present and (now - last_trigger) > self._cooldown:
                        self._present = True
                        last_trigger = now
                        self._trigger_greeting()
                else:
                    no_motion_count += 1
                    # After 10 frames of no motion, mark absent
                    if self._present and no_motion_count > 10:
                        self._present = False
                        self._trigger_farewell()
        finally:
            cap.release()

    def _trigger_greeting(self):
        """Someone approached — send greeting to display."""
        self._send_message(self._greeting, 'pop', priority=3)
        print(f'[webcam] Presence detected — greeting sent', file=sys.stderr)

    def _trigger_farewell(self):
        """Person left — send farewell."""
        self._send_message(self._farewell, 'dissolve', priority=1)
        print(f'[webcam] Presence lost — farewell sent', file=sys.stderr)

    def _send_message(self, text, transition, priority=0):
        with self._app.app_context():
            from app.models import Message
            from app import db

            msg = Message(body=text, transition=transition, source='webcam', priority=priority)
            db.session.add(msg)
            db.session.commit()

            self._app.message_queue.enqueue(
                msg.body, msg.transition, msg.priority, msg.id
            )
