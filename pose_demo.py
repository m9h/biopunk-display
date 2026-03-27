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

from core.core import WorkingFlipdotCore, TCOLUMN, TROW, BITMASK

VISIBLE_COLS = 30
MIN_VIS = 0.45

SKELETON = [
    (11, 12), (11, 23), (12, 24), (23, 24),  # torso
    (11, 13), (13, 15),  # left arm
    (12, 14), (14, 16),  # right arm
    (23, 25), (25, 27),  # left leg
    (24, 26), (26, 28),  # right leg
]


def set_pixel(frame, col, row):
    if 0 <= col < VISIBLE_COLS and 0 <= row < TROW:
        frame[col] |= BITMASK[row]


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


def lm_to_grid(lm):
    x = max(0.0, min(1.0, (lm.x - 0.2) / 0.6))
    y = max(0.0, min(1.0, (lm.y - 0.1) / 0.8))
    col = int(x * (VISIBLE_COLS - 1))
    row = int((1.0 - y) * (TROW - 1))
    return col, row


def render_stick_figure(landmarks):
    frame = bytearray(TCOLUMN)

    # Head
    nose = landmarks[0]
    if nose.visibility > MIN_VIS:
        nc, nr = lm_to_grid(nose)
        set_pixel(frame, nc, nr)
        set_pixel(frame, nc - 1, nr)
        set_pixel(frame, nc + 1, nr)
        set_pixel(frame, nc, min(nr + 1, TROW - 1))

    # Neck
    ls, rs = landmarks[11], landmarks[12]
    if nose.visibility > MIN_VIS and ls.visibility > MIN_VIS and rs.visibility > MIN_VIS:
        nc, nr = lm_to_grid(nose)
        lsc, lsr = lm_to_grid(ls)
        rsc, rsr = lm_to_grid(rs)
        draw_line(frame, nc, nr, (lsc + rsc) // 2, (lsr + rsr) // 2)

    # Skeleton connections
    for a_idx, b_idx in SKELETON:
        a, b = landmarks[a_idx], landmarks[b_idx]
        if a.visibility > MIN_VIS and b.visibility > MIN_VIS:
            ac, ar = lm_to_grid(a)
            bc, br = lm_to_grid(b)
            draw_line(frame, ac, ar, bc, br)

    return bytes(frame)


def print_frame_ascii(frame):
    """Print frame as ASCII art (for terminals without FallbackSerial)."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print('+' + '-' * VISIBLE_COLS + '+')
    for row in range(TROW - 1, -1, -1):  # top to bottom
        line = ''
        for col in range(VISIBLE_COLS):
            if frame[col] & BITMASK[row]:
                line += 'O'
            else:
                line += '.'
        print('|' + line + '|')
    print('+' + '-' * VISIBLE_COLS + '+')
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
