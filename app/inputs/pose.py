"""
Chapter 18: Pose tracking stick figure on the flipdot display.

Uses MediaPipe Pose to detect body landmarks from the LifeCam HD-3000,
maps the skeleton onto the 7×30 flipdot grid, and sends frames
directly to the display at ~5 fps (mechanical pixel speed limit).

The stick figure mirrors your movements — step left, it steps left.
Raise your arms, the flipdot figure raises its arms.

Requirements: pip install mediapipe opencv-python-headless
"""

import sys
import threading
import time

# Display constants (from core.core)
TROW = 7
TCOLUMN = 105
VISIBLE_COLS = 30
BITMASK = [1, 2, 4, 8, 0x10, 0x20, 0x40]

# Stick figure connections: (landmark_a, landmark_b)
# Using MediaPipe Pose landmark indices
SKELETON = [
    # Torso
    (11, 12),  # left shoulder → right shoulder
    (11, 23),  # left shoulder → left hip
    (12, 24),  # right shoulder → right hip
    (23, 24),  # left hip → right hip
    # Left arm
    (11, 13),  # left shoulder → left elbow
    (13, 15),  # left elbow → left wrist
    # Right arm
    (12, 14),  # right shoulder → right elbow
    (14, 16),  # right elbow → right wrist
    # Left leg
    (23, 25),  # left hip → left knee
    (25, 27),  # left knee → left ankle
    # Right leg
    (24, 26),  # right hip → right knee
    (26, 28),  # right knee → right ankle
]

# Minimum visibility to use a landmark
MIN_VIS = 0.45


class PoseInput:
    """Real-time pose tracking → flipdot stick figure display."""

    def __init__(self, app=None):
        self._thread = None
        self._running = False
        self._app = None
        self._tracking = False
        self._fps = 0
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._device = app.config.get('POSE_DEVICE', 0)
        self._target_fps = app.config.get('POSE_FPS', 5)
        self._mirror = app.config.get('POSE_MIRROR', True)
        self._model_complexity = app.config.get('POSE_MODEL_COMPLEXITY', 0)
        app.pose_input = self

    @property
    def is_tracking(self):
        return self._tracking

    @property
    def fps(self):
        return self._fps

    def start(self):
        """Start pose tracking."""
        if self._thread is not None and self._thread.is_alive():
            return

        try:
            import mediapipe  # noqa: F401
            import cv2  # noqa: F401
        except ImportError:
            print('[pose] mediapipe or opencv not installed — pose input disabled',
                  file=sys.stderr)
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._tracking_loop, daemon=True, name='pose-input'
        )
        self._thread.start()
        print(f'[pose] Tracking started on /dev/video{self._device}',
              file=sys.stderr)

    def stop(self):
        self._running = False
        self._tracking = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        print('[pose] Tracking stopped', file=sys.stderr)

    def _find_model(self):
        """Locate the pose_landmarker model file."""
        import os
        candidates = [
            os.path.expanduser('~/.mediapipe/pose_landmarker_lite.task'),
            os.path.join(os.path.dirname(__file__), '..', '..',
                         'models', 'pose_landmarker_lite.task'),
            'pose_landmarker_lite.task',
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _tracking_loop(self):
        """Capture frames → MediaPipe → stick figure → flipdot."""
        import cv2
        import mediapipe as mp

        model_path = self._find_model()
        if not model_path:
            print('[pose] Model not found. Download with:', file=sys.stderr)
            print('  python -c "import urllib.request, os; '
                  'os.makedirs(os.path.expanduser(\'~/.mediapipe\'), exist_ok=True); '
                  'urllib.request.urlretrieve('
                  '\'https://storage.googleapis.com/mediapipe-models/pose_landmarker/'
                  'pose_landmarker_lite/float16/latest/pose_landmarker_lite.task\', '
                  'os.path.expanduser(\'~/.mediapipe/pose_landmarker_lite.task\'))"',
                  file=sys.stderr)
            return

        cap = cv2.VideoCapture(self._device)
        if not cap.isOpened():
            print(f'[pose] Cannot open /dev/video{self._device}',
                  file=sys.stderr)
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

        # Use the new Tasks API (mediapipe >= 0.10.x)
        BaseOptions = mp.tasks.BaseOptions
        PoseLandmarker = mp.tasks.vision.PoseLandmarker
        PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        frame_interval = 1.0 / self._target_fps
        frame_count = 0
        fps_time = time.time()
        timestamp_ms = 0

        landmarker = PoseLandmarker.create_from_options(options)
        try:
            while self._running:
                t0 = time.time()

                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                if self._mirror:
                    frame = cv2.flip(frame, 1)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=rgb
                )
                timestamp_ms += int(frame_interval * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    self._tracking = True
                    landmarks = result.pose_landmarks[0]
                    flipdot_frame = self._render_stick_figure(landmarks)
                    self._send_frame(flipdot_frame)
                else:
                    if self._tracking:
                        self._tracking = False
                        self._clear_display()

                # FPS counter
                frame_count += 1
                now = time.time()
                if now - fps_time >= 1.0:
                    self._fps = frame_count
                    frame_count = 0
                    fps_time = now

                # Throttle to target fps
                elapsed = time.time() - t0
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)

        finally:
            landmarker.close()
            cap.release()
            self._tracking = False

    def _render_stick_figure(self, landmarks):
        """Map MediaPipe landmarks to a 7x30 flipdot frame.

        Uses adaptive bounding box: measures the actual extent of visible
        landmarks and stretches the figure to fill the full 7x30 grid.
        This way, upper-body-only (sitting at desk) still fills the display
        instead of clustering in the middle rows.

        Returns a 105-byte buffer where bytes 0-29 are the visible columns.
        Each byte has 7 bits: bit 0 = row 0 (bottom), bit 6 = row 6 (top).
        """
        frame = bytearray(TCOLUMN)

        # Key landmark indices used for the stick figure
        key_indices = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

        # Compute adaptive bounding box from visible landmarks
        vis_x = []
        vis_y = []
        for idx in key_indices:
            lm = landmarks[idx]
            if lm.visibility > MIN_VIS:
                vis_x.append(lm.x)
                vis_y.append(lm.y)

        if not vis_x:
            return bytes(frame)  # nothing visible

        # Add padding (10% of span on each side, min 0.05)
        x_min, x_max = min(vis_x), max(vis_x)
        y_min, y_max = min(vis_y), max(vis_y)
        x_span = max(x_max - x_min, 0.05)
        y_span = max(y_max - y_min, 0.05)
        pad_x = max(x_span * 0.15, 0.03)
        pad_y = max(y_span * 0.15, 0.03)
        x_min = max(0.0, x_min - pad_x)
        x_max = min(1.0, x_max + pad_x)
        y_min = max(0.0, y_min - pad_y)
        y_max = min(1.0, y_max + pad_y)
        x_range = max(x_max - x_min, 0.01)
        y_range = max(y_max - y_min, 0.01)

        def set_pixel(col, row):
            if 0 <= col < VISIBLE_COLS and 0 <= row < TROW:
                frame[col] |= BITMASK[row]

        def lm_to_grid(lm):
            x = max(0.0, min(1.0, (lm.x - x_min) / x_range))
            col = int(x * (VISIBLE_COLS - 1))
            y = max(0.0, min(1.0, (lm.y - y_min) / y_range))
            row = int((1.0 - y) * (TROW - 1))
            return col, row

        def draw_line(c0, r0, c1, r1):
            dc = abs(c1 - c0)
            dr = abs(r1 - r0)
            sc = 1 if c0 < c1 else -1
            sr = 1 if r0 < r1 else -1
            err = dc - dr
            while True:
                set_pixel(c0, r0)
                if c0 == c1 and r0 == r1:
                    break
                e2 = 2 * err
                if e2 > -dr:
                    err -= dr
                    c0 += sc
                if e2 < dc:
                    err += dc
                    r0 += sr

        # Head: 3 pixels wide, 1 row (no top-of-head pixel — saves a row)
        nose = landmarks[0]
        if nose.visibility > MIN_VIS:
            nc, nr = lm_to_grid(nose)
            set_pixel(nc, nr)
            set_pixel(nc - 1, nr)
            set_pixel(nc + 1, nr)

        # Neck: nose to midpoint of shoulders
        ls = landmarks[11]
        rs = landmarks[12]
        if nose.visibility > MIN_VIS and ls.visibility > MIN_VIS and rs.visibility > MIN_VIS:
            nc, nr = lm_to_grid(nose)
            lsc, lsr = lm_to_grid(ls)
            rsc, rsr = lm_to_grid(rs)
            draw_line(nc, nr, (lsc + rsc) // 2, (lsr + rsr) // 2)

        # Skeleton connections
        for a_idx, b_idx in SKELETON:
            a = landmarks[a_idx]
            b = landmarks[b_idx]
            if a.visibility > MIN_VIS and b.visibility > MIN_VIS:
                ac, ar = lm_to_grid(a)
                bc, br = lm_to_grid(b)
                draw_line(ac, ar, bc, br)

        return bytes(frame)

    def _send_frame(self, frame):
        """Send a frame to the flipdot display via DisplayManager."""
        with self._app.app_context():
            display = self._app.display
            display.set_frame(frame)
            with display._lock:
                display.core.fill(frame)

    def _clear_display(self):
        """Clear the display when person leaves frame."""
        with self._app.app_context():
            self._app.display.clear()
