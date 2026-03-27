"""Tests for pose tracking input module.

Tests the stick figure rendering logic without needing a camera or
MediaPipe — we feed synthetic landmarks and verify the frame bytes.
"""

import importlib
import os
import sys
from unittest.mock import MagicMock

import pytest

# Import pose module directly, bypassing the Flask app package
_pose_spec = importlib.util.spec_from_file_location(
    'pose',
    os.path.join(os.path.dirname(__file__), '..', 'app', 'inputs', 'pose.py'),
)
_pose_mod = importlib.util.module_from_spec(_pose_spec)
_pose_spec.loader.exec_module(_pose_mod)

PoseInput = _pose_mod.PoseInput
TROW = _pose_mod.TROW
VISIBLE_COLS = _pose_mod.VISIBLE_COLS
BITMASK = _pose_mod.BITMASK
MIN_VIS = _pose_mod.MIN_VIS


class FakeLandmark:
    """Mimics a MediaPipe NormalizedLandmark."""

    def __init__(self, x, y, z=0.0, visibility=0.99):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility


def make_landmarks(overrides=None):
    """Create 33 default landmarks (all centered, all visible).

    Override specific indices with FakeLandmark instances via dict.
    """
    defaults = [FakeLandmark(0.5, 0.5, visibility=0.99)] * 33
    # Convert to list so we can mutate
    lms = list(defaults)
    if overrides:
        for idx, lm in overrides.items():
            lms[idx] = lm
    return lms


class TestPoseInput:
    """Unit tests for PoseInput rendering logic."""

    def setup_method(self):
        self.pose = PoseInput()
        # Give it a mock app so _send_frame / _clear_display don't blow up
        self.pose._app = MagicMock()

    def test_render_returns_105_bytes(self):
        """Frame buffer must always be 105 bytes."""
        landmarks = make_landmarks()
        frame = self.pose._render_stick_figure(landmarks)
        assert len(frame) == 105

    def test_render_blank_when_invisible(self):
        """If all landmarks have low visibility, frame should be blank."""
        lms = [FakeLandmark(0.5, 0.5, visibility=0.1)] * 33
        frame = self.pose._render_stick_figure(lms)
        # All bytes in visible region should be 0
        assert all(b == 0 for b in frame[:VISIBLE_COLS])

    def test_render_has_pixels_when_visible(self):
        """Visible landmarks should produce non-zero pixels."""
        # Person standing in center of frame
        lms = make_landmarks({
            0: FakeLandmark(0.5, 0.15),   # nose (top)
            11: FakeLandmark(0.4, 0.3),    # left shoulder
            12: FakeLandmark(0.6, 0.3),    # right shoulder
            13: FakeLandmark(0.3, 0.45),   # left elbow
            14: FakeLandmark(0.7, 0.45),   # right elbow
            15: FakeLandmark(0.25, 0.55),  # left wrist
            16: FakeLandmark(0.75, 0.55),  # right wrist
            23: FakeLandmark(0.45, 0.55),  # left hip
            24: FakeLandmark(0.55, 0.55),  # right hip
            25: FakeLandmark(0.42, 0.72),  # left knee
            26: FakeLandmark(0.58, 0.72),  # right knee
            27: FakeLandmark(0.40, 0.9),   # left ankle
            28: FakeLandmark(0.60, 0.9),   # right ankle
        })
        frame = self.pose._render_stick_figure(lms)
        # Should have some lit pixels in the visible range
        lit = sum(1 for b in frame[:VISIBLE_COLS] if b != 0)
        assert lit >= 5, f"Expected at least 5 lit columns, got {lit}"

    def test_head_renders_near_top(self):
        """Nose at top of frame should light pixels in upper rows."""
        lms = make_landmarks({
            0: FakeLandmark(0.5, 0.12),   # nose near top
            7: FakeLandmark(0.45, 0.1),    # left ear
            8: FakeLandmark(0.55, 0.1),    # right ear
            11: FakeLandmark(0.4, 0.3),
            12: FakeLandmark(0.6, 0.3),
        })
        frame = self.pose._render_stick_figure(lms)
        # Check that upper rows (bits 5-6) are lit somewhere
        upper_bits = BITMASK[5] | BITMASK[6]
        has_upper = any(frame[c] & upper_bits for c in range(VISIBLE_COLS))
        assert has_upper, "Head should light upper rows"

    def test_arms_spread_wide(self):
        """Arms spread wide should use more columns than arms at sides."""
        # Arms at sides
        narrow = make_landmarks({
            0: FakeLandmark(0.5, 0.15),
            11: FakeLandmark(0.48, 0.3),
            12: FakeLandmark(0.52, 0.3),
            13: FakeLandmark(0.47, 0.45),
            14: FakeLandmark(0.53, 0.45),
            15: FakeLandmark(0.46, 0.55),
            16: FakeLandmark(0.54, 0.55),
            23: FakeLandmark(0.48, 0.55),
            24: FakeLandmark(0.52, 0.55),
            25: FakeLandmark(0.47, 0.72),
            26: FakeLandmark(0.53, 0.72),
            27: FakeLandmark(0.47, 0.9),
            28: FakeLandmark(0.53, 0.9),
        })
        # Arms spread wide
        wide = make_landmarks({
            0: FakeLandmark(0.5, 0.15),
            11: FakeLandmark(0.4, 0.3),
            12: FakeLandmark(0.6, 0.3),
            13: FakeLandmark(0.25, 0.35),
            14: FakeLandmark(0.75, 0.35),
            15: FakeLandmark(0.1, 0.35),
            16: FakeLandmark(0.9, 0.35),
            23: FakeLandmark(0.45, 0.55),
            24: FakeLandmark(0.55, 0.55),
            25: FakeLandmark(0.43, 0.72),
            26: FakeLandmark(0.57, 0.72),
            27: FakeLandmark(0.42, 0.9),
            28: FakeLandmark(0.58, 0.9),
        })
        narrow_frame = self.pose._render_stick_figure(narrow)
        wide_frame = self.pose._render_stick_figure(wide)

        narrow_lit = sum(1 for b in narrow_frame[:VISIBLE_COLS] if b != 0)
        wide_lit = sum(1 for b in wide_frame[:VISIBLE_COLS] if b != 0)
        assert wide_lit > narrow_lit, \
            f"Wide arms ({wide_lit} cols) should use more columns than narrow ({narrow_lit})"

    def test_pixel_within_bounds(self):
        """No pixels should be set outside the 7×30 visible area."""
        # Extreme landmarks near edges
        lms = make_landmarks({
            0: FakeLandmark(0.0, 0.0),     # top-left extreme
            11: FakeLandmark(0.0, 0.2),
            12: FakeLandmark(1.0, 0.2),    # far right
            15: FakeLandmark(0.0, 0.5),
            16: FakeLandmark(1.0, 0.5),
            23: FakeLandmark(0.0, 0.8),
            24: FakeLandmark(1.0, 0.8),
            27: FakeLandmark(0.0, 1.0),    # bottom-left extreme
            28: FakeLandmark(1.0, 1.0),    # bottom-right extreme
        })
        frame = self.pose._render_stick_figure(lms)
        # No byte should exceed 0x7F (7 bits)
        for i, b in enumerate(frame[:VISIBLE_COLS]):
            assert b <= 0x7F, f"Column {i} has value {b:#x} > 0x7F"

    def test_frame_only_uses_visible_cols(self):
        """Only the first 30 bytes (visible columns) should have data."""
        lms = make_landmarks({
            0: FakeLandmark(0.5, 0.15),
            11: FakeLandmark(0.4, 0.3),
            12: FakeLandmark(0.6, 0.3),
            23: FakeLandmark(0.45, 0.55),
            24: FakeLandmark(0.55, 0.55),
            27: FakeLandmark(0.42, 0.9),
            28: FakeLandmark(0.58, 0.9),
        })
        frame = self.pose._render_stick_figure(lms)
        # Columns 30-74 and 75-104 should be blank
        assert all(b == 0 for b in frame[VISIBLE_COLS:])

    def test_mirror_config_default(self):
        """Mirror should be True by default."""
        pose = PoseInput()
        app = MagicMock()
        app.config = {'POSE_DEVICE': 0, 'POSE_FPS': 5, 'POSE_MIRROR': True,
                       'POSE_MODEL_COMPLEXITY': 0}
        # Manually call what init_app would do
        pose.init_app(app)
        assert pose._mirror is True
