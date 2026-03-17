"""
Chapter 8: Gesture input via Leap Motion Controller.

Detects hand gestures (swipe, circle, tap) and maps them to display actions.

The Leap Motion SDK uses a WebSocket on port 6437, so no native SDK needed —
we can connect via the built-in web socket interface.
"""

import threading
import json
import sys


class GestureInput:
    """Leap Motion gesture-to-flipdot controller."""

    def __init__(self, app=None):
        self._thread = None
        self._running = False
        self._app = None
        self._last_gesture_time = 0
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._ws_url = app.config.get('LEAP_WS_URL', 'ws://localhost:6437/v6.json')
        self._cooldown = app.config.get('LEAP_COOLDOWN', 2.0)  # seconds between gestures
        app.gesture_input = self

    def start(self):
        """Start listening for Leap Motion gestures."""
        if self._thread is not None and self._thread.is_alive():
            return

        try:
            import websocket  # noqa: F401
        except ImportError:
            print('[gesture] websocket-client not installed — gesture input disabled',
                  file=sys.stderr)
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name='gesture-input'
        )
        self._thread.start()
        print('[gesture] Connecting to Leap Motion...', file=sys.stderr)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _listen_loop(self):
        """Connect to Leap Motion WebSocket and process frames."""
        import websocket
        import time

        while self._running:
            try:
                ws = websocket.create_connection(self._ws_url, timeout=5)
                # Enable gestures
                ws.send(json.dumps({'enableGestures': True}))

                while self._running:
                    raw = ws.recv()
                    if not raw:
                        continue
                    frame = json.loads(raw)
                    self._process_frame(frame)

            except Exception as e:
                print(f'[gesture] Connection error: {e}', file=sys.stderr)
                if self._running:
                    time.sleep(5)  # retry after delay

    def _process_frame(self, frame):
        """Extract gestures from a Leap Motion frame."""
        import time

        gestures = frame.get('gestures', [])
        if not gestures:
            return

        now = time.time()
        if now - self._last_gesture_time < self._cooldown:
            return

        for gesture in gestures:
            gtype = gesture.get('type')
            state = gesture.get('state')

            # Only act on completed gestures
            if state != 'stop':
                continue

            action = None
            if gtype == 'swipe':
                direction = gesture.get('direction', [0, 0, 0])
                if abs(direction[0]) > abs(direction[1]):
                    action = 'swipe_left' if direction[0] < 0 else 'swipe_right'
                else:
                    action = 'swipe_up' if direction[1] > 0 else 'swipe_down'
            elif gtype == 'circle':
                action = 'circle'
            elif gtype == 'keyTap':
                action = 'tap'
            elif gtype == 'screenTap':
                action = 'screen_tap'

            if action:
                self._last_gesture_time = now
                self._handle_gesture(action)
                return  # one gesture per cooldown

    def _handle_gesture(self, action):
        """Map gesture actions to display operations."""
        GESTURE_MESSAGES = {
            'swipe_left': ('SWIPE LEFT', 'righttoleft'),
            'swipe_right': ('SWIPE RIGHT', 'slide_in_left'),
            'swipe_up': ('HELLO!', 'pop'),
            'swipe_down': None,  # clear
            'circle': ('BIOPUNK', 'dissolve'),
            'tap': ('TAP', 'typewriter'),
            'screen_tap': ('SCREEN TAP', 'magichat'),
        }

        mapping = GESTURE_MESSAGES.get(action)

        if mapping is None:
            # swipe_down = clear
            self._app.display.clear()
            print(f'[gesture] {action} → clear', file=sys.stderr)
            return

        text, transition = mapping
        with self._app.app_context():
            from app.models import Message
            from app import db

            msg = Message(body=text, transition=transition, source='gesture', priority=1)
            db.session.add(msg)
            db.session.commit()

            self._app.message_queue.enqueue(
                msg.body, msg.transition, msg.priority, msg.id
            )
            print(f'[gesture] {action} → "{text}" ({transition})', file=sys.stderr)
