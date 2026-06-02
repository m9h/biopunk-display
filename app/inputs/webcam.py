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
        self._thumbnail = None  # latest low-res grayscale grid (list of rows)
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
        self._thumb_w = app.config.get('WEBCAM_THUMB_W', 32)
        self._thumb_h = app.config.get('WEBCAM_THUMB_H', 12)
        app.webcam_input = self

    @property
    def is_present(self):
        return self._present

    @property
    def thumbnail(self):
        """Latest low-res grayscale frame as a list of rows (0-255), or None.

        Updated once per monitor iteration from the frame already captured
        for motion detection, so it costs only a downscale — no extra reads.
        """
        return self._thumbnail

    def _store_thumbnail(self, frame):
        """Downscale a BGR frame to a small grayscale grid for the monitor."""
        import cv2
        small = cv2.resize(
            frame, (self._thumb_w, self._thumb_h),
            interpolation=cv2.INTER_AREA,
        )
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        self._thumbnail = gray.tolist()

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

        self._store_thumbnail(prev_frame)
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)

        last_trigger = time.time()  # suppress greeting at startup
        no_motion_count = 0

        try:
            while self._running:
                time.sleep(self._check_interval)

                ret, frame = cap.read()
                if not ret:
                    continue

                self._store_thumbnail(frame)
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
            self._thumbnail = None

    def _trigger_greeting(self):
        """Someone approached — send greeting to display."""
        if self._display_busy():
            print('[webcam] Presence detected — suppressed (display busy)',
                  file=sys.stderr)
            return
        self._send_message(self._greeting, 'righttoleft', priority=3)
        print('[webcam] Presence detected — greeting sent', file=sys.stderr)

    def _trigger_farewell(self):
        """Person left — send farewell."""
        if self._display_busy():
            print('[webcam] Presence lost — suppressed (display busy)',
                  file=sys.stderr)
            return
        self._send_message(self._farewell, 'dissolve', priority=1)
        print('[webcam] Presence lost — farewell sent', file=sys.stderr)

    def _display_busy(self):
        """Check if the display is owned by any interactive mode.

        When any of these are active, we suppress greeting/farewell queueing
        entirely — otherwise the message would sit in the queue and play
        unexpectedly once the mode ends.
        """
        player = getattr(self._app, '_automata_player', None)
        if player is not None and player.is_running:
            return True
        ticker = getattr(self._app, 'ticker', None)
        if ticker is not None and ticker.is_running:
            return True
        video = getattr(self._app, 'video', None)
        if video is not None and video.is_running:
            return True
        playlists = getattr(self._app, 'playlists', None)
        if playlists is not None and playlists.now_playing:
            return True
        return False

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
