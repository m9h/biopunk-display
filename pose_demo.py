#!/usr/bin/env python3
"""
Pose Tracker Demo — standalone script to test stick figure rendering.

Runs without the Flask server. Uses the FallbackSerial terminal simulator
when no flipdot hardware is connected, so you can see the stick figure
in your terminal.

Usage:
    python pose_demo.py              # webcam device 0
    python pose_demo.py --device 1   # webcam device 1
    python pose_demo.py --no-preview # skip the OpenCV preview window
"""

import argparse
import os
import sys
import time

import cv2
import mediapipe as mp

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from core.core import WorkingFlipdotCore, TCOLUMN, BITMASK

COLS = 30
ROWS = 14
PANEL_ROWS = 7
BOTTOM_PANEL_OFFSET = 75
MIN_VIS = 0.45

SKELETON = [
    (11, 13), (13, 15),  # left arm
    (12, 14), (14, 16),  # right arm
    (23, 25), (25, 27),  # left leg
    (24, 26), (26, 28),  # right leg
]


def set_pixel(frame, col, row):
    """Set pixel at (col, row) where row 0=bottom, row 13=top."""
    if 0 <= col < COLS and 0 <= row < ROWS:
        if row >= PANEL_ROWS:
            frame[col] |= BITMASK[row - PANEL_ROWS]
        else:
            frame[BOTTOM_PANEL_OFFSET + col] |= BITMASK[row]


def draw_line(frame, c0, r0, c1, r1):
    dc = abs(c1 - c0)
    dr = abs(r1 - r0)
    sc = 1 if c0 < c1 else -1
    sr = 1 if r0 < r1 else -1
    err = dc - dr
    while True:
        set_pixel(frame, c0, r0)
        if c0 == c1 and r0 == r1:
            break
        e2 = 2 * err
        if e2 > -dr:
            err -= dr
            c0 += sc
        if e2 < dc:
            err += dc
            r0 += sr


KEY_INDICES = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


def render_stick_figure(landmarks):
    """Adaptive bounding box: stretches visible landmarks to fill the 14x30 grid."""
    frame = bytearray(TCOLUMN)

    vis_x = [landmarks[i].x for i in KEY_INDICES if landmarks[i].visibility > MIN_VIS]
    vis_y = [landmarks[i].y for i in KEY_INDICES if landmarks[i].visibility > MIN_VIS]
    if not vis_x:
        return bytes(frame)

    x_min, x_max = min(vis_x), max(vis_x)
    y_min, y_max = min(vis_y), max(vis_y)
    x_span = max(x_max - x_min, 0.05)
    y_span = max(y_max - y_min, 0.05)
    pad_x = max(x_span * 0.15, 0.03)
    pad_y = max(y_span * 0.10, 0.02)
    x_min = max(0.0, x_min - pad_x)
    x_max = min(1.0, x_max + pad_x)
    y_min = max(0.0, y_min - pad_y)
    y_max = min(1.0, y_max + pad_y)
    x_range = max(x_max - x_min, 0.01)
    y_range = max(y_max - y_min, 0.01)

    def lm_to_grid(lm):
        x = max(0.0, min(1.0, (lm.x - x_min) / x_range))
        y = max(0.0, min(1.0, (lm.y - y_min) / y_range))
        return int(x * (COLS - 1)), int((1.0 - y) * (ROWS - 1))

    # Head
    nose = landmarks[0]
    if nose.visibility > MIN_VIS:
        nc, nr = lm_to_grid(nose)
        set_pixel(frame, nc, nr)
        set_pixel(frame, nc - 1, nr)
        set_pixel(frame, nc + 1, nr)
        set_pixel(frame, nc, min(nr + 1, ROWS - 1))

    ls, rs = landmarks[11], landmarks[12]
    lh, rh = landmarks[23], landmarks[24]
    has_s = ls.visibility > MIN_VIS and rs.visibility > MIN_VIS
    has_h = lh.visibility > MIN_VIS and rh.visibility > MIN_VIS

    if has_s:
        lsc, lsr = lm_to_grid(ls)
        rsc, rsr = lm_to_grid(rs)
        msc, msr = (lsc + rsc) // 2, (lsr + rsr) // 2
    if has_h:
        lhc, lhr = lm_to_grid(lh)
        rhc, rhr = lm_to_grid(rh)
        mhc, mhr = (lhc + rhc) // 2, (lhr + rhr) // 2

    # Neck
    if nose.visibility > MIN_VIS and has_s:
        nc, nr = lm_to_grid(nose)
        draw_line(frame, nc, nr, msc, msr)
    # Spine (single pixel wide)
    if has_s and has_h:
        draw_line(frame, msc, msr, mhc, mhr)
    # Shoulder branches
    if has_s:
        draw_line(frame, msc, msr, lsc, lsr)
        draw_line(frame, msc, msr, rsc, rsr)
    # Hip branches
    if has_h:
        draw_line(frame, mhc, mhr, lhc, lhr)
        draw_line(frame, mhc, mhr, rhc, rhr)

    # Arm and leg bones
    for a_idx, b_idx in SKELETON:
        a, b = landmarks[a_idx], landmarks[b_idx]
        if a.visibility > MIN_VIS and b.visibility > MIN_VIS:
            ac, ar = lm_to_grid(a)
            bc, br = lm_to_grid(b)
            draw_line(frame, ac, ar, bc, br)

    return bytes(frame)


def read_pixel(frame, col, row):
    """Read pixel at (col, row) where row 0=bottom, row 13=top."""
    if row >= PANEL_ROWS:
        return bool(frame[col] & BITMASK[row - PANEL_ROWS])
    else:
        return bool(frame[BOTTOM_PANEL_OFFSET + col] & BITMASK[row])


def print_frame_ascii(frame):
    """Print the 14x30 display as ASCII art."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print('+' + '-' * COLS + '+')
    for row in range(ROWS - 1, -1, -1):  # top to bottom
        line = ''
        for col in range(COLS):
            line += 'O' if read_pixel(frame, col, row) else '.'
        print('|' + line + '|')
    print('+' + '-' * COLS + '+')
    print('  Pose Tracker Demo -- press Q in camera window / Ctrl-C to quit')


def find_model():
    """Locate the pose_landmarker model file."""
    candidates = [
        os.path.expanduser('~/.mediapipe/pose_landmarker_lite.task'),
        os.path.join(os.path.dirname(__file__), 'models', 'pose_landmarker_lite.task'),
        'pose_landmarker_lite.task',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def download_model():
    """Download the pose model if missing."""
    import urllib.request
    dest = os.path.expanduser('~/.mediapipe/pose_landmarker_lite.task')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    url = ('https://storage.googleapis.com/mediapipe-models/pose_landmarker/'
           'pose_landmarker_lite/float16/latest/pose_landmarker_lite.task')
    print(f'Downloading pose model...')
    urllib.request.urlretrieve(url, dest)
    print(f'Saved to {dest}')
    return dest


def main():
    parser = argparse.ArgumentParser(description='Flipdot Pose Tracker Demo')
    parser.add_argument('--device', type=int, default=0, help='Webcam device index')
    parser.add_argument('--no-preview', action='store_true', help='Skip OpenCV preview')
    parser.add_argument('--fps', type=int, default=5, help='Target frame rate')
    parser.add_argument('--serial', action='store_true',
                        help='Send to flipdot via serial (auto-detect port)')
    args = parser.parse_args()

    # Find or download model
    model_path = find_model()
    if not model_path:
        model_path = download_model()

    # Initialize display (FallbackSerial if no hardware)
    core = None
    if args.serial:
        core = WorkingFlipdotCore()

    cap = cv2.VideoCapture(args.device)
    if not cap.isOpened():
        print(f'ERROR: Cannot open webcam device {args.device}')
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    print(f'Camera opened: device {args.device}')
    print(f'Target FPS: {args.fps}')
    if core:
        print('Flipdot: connected via serial')
    else:
        print('Flipdot: ASCII terminal mode (use --serial for hardware)')
    print()

    # Use the Tasks API (mediapipe >= 0.10.x)
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

    frame_interval = 1.0 / args.fps
    timestamp_ms = 0

    landmarker = PoseLandmarker.create_from_options(options)
    try:
        while True:
            t0 = time.time()

            ret, camera_frame = cap.read()
            if not ret:
                continue

            camera_frame = cv2.flip(camera_frame, 1)  # mirror
            rgb = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms += int(frame_interval * 1000)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                landmarks = result.pose_landmarks[0]
                flipdot_frame = render_stick_figure(landmarks)

                if core:
                    core.fill(flipdot_frame)
                else:
                    print_frame_ascii(flipdot_frame)

            if not args.no_preview:
                cv2.imshow('Pose Tracker (Q to quit)', camera_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            elapsed = time.time() - t0
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    except KeyboardInterrupt:
        print('\nShutting down...')
    finally:
        landmarker.close()
        cap.release()
        if not args.no_preview:
            cv2.destroyAllWindows()
        if core:
            core.clear()


if __name__ == '__main__':
    main()
