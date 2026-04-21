"""Tests for the video clip player (app/display/video.py).

Uses a temporary frames directory and a mock display — no hardware.
"""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.display.video import VideoPlayer, _image_to_buffer


def _fake_app(frames_dir: Path):
    app = MagicMock()
    app.config = {'VIDEO_FRAMES_DIR': str(frames_dir)}
    app.display._lock = threading.Lock()
    app.display.set_frame = MagicMock()
    app.display.core.fill = MagicMock()
    app.display.clear = MagicMock()
    return app


def _make_clip(root: Path, name: str, frames=3, size=(30, 14)) -> Path:
    clip = root / name
    clip.mkdir(parents=True, exist_ok=True)
    for i in range(frames):
        img = Image.new('1', size, color=0)
        # Put one lit pixel per frame at different X so frames differ.
        img.putpixel((i, 0), 1)
        img.save(clip / f'{i:05d}.png')
    return clip


class TestImageToBuffer:

    def test_single_row_top_pixel(self):
        img = Image.new('L', (30, 14), color=0)
        img.putpixel((0, 0), 255)
        buf = _image_to_buffer(img)
        assert len(buf) == 105
        # Row 0, col 0 → top panel, bit 6
        assert buf[0] == 0b1000000
        assert buf[30] == 0  # bottom untouched

    def test_bottom_panel_pixel(self):
        img = Image.new('L', (30, 14), color=0)
        img.putpixel((5, 7), 255)  # first row of bottom panel
        buf = _image_to_buffer(img)
        assert buf[5] == 0  # top panel untouched
        # Row 7 → bottom panel bit (13-7) = bit 6
        assert buf[30 + 5] == 0b1000000

    def test_bottom_last_row(self):
        img = Image.new('L', (30, 14), color=0)
        img.putpixel((0, 13), 255)  # bottom-most pixel
        buf = _image_to_buffer(img)
        # Row 13 → bottom bit 0
        assert buf[30] == 0b0000001

    def test_oversized_image_is_scaled(self):
        img = Image.new('L', (60, 28), color=255)
        buf = _image_to_buffer(img)
        assert len(buf) == 105
        # Every visible column should be fully lit on both panels
        for c in range(30):
            assert buf[c] == 0b1111111
            assert buf[30 + c] == 0b1111111

    def test_all_off(self):
        img = Image.new('L', (30, 14), color=0)
        buf = _image_to_buffer(img)
        assert buf == b'\x00' * 105

    def test_threshold_at_128(self):
        img = Image.new('L', (30, 14), color=127)  # just below threshold
        buf = _image_to_buffer(img)
        assert buf == b'\x00' * 105


class TestClipDiscovery:

    def test_empty_dir(self, tmp_path):
        vp = VideoPlayer(_fake_app(tmp_path))
        assert vp.list_clips() == []

    def test_lists_clips_with_frame_counts(self, tmp_path):
        _make_clip(tmp_path, 'alpha', frames=4)
        _make_clip(tmp_path, 'beta', frames=2)
        vp = VideoPlayer(_fake_app(tmp_path))
        clips = vp.list_clips()
        assert {c['name'] for c in clips} == {'alpha', 'beta'}
        by_name = {c['name']: c['frames'] for c in clips}
        assert by_name == {'alpha': 4, 'beta': 2}

    def test_ignores_hidden_dirs(self, tmp_path):
        (tmp_path / '.hidden').mkdir()
        _make_clip(tmp_path, 'visible')
        vp = VideoPlayer(_fake_app(tmp_path))
        names = {c['name'] for c in vp.list_clips()}
        assert names == {'visible'}


class TestPlayback:

    def test_play_missing_clip_returns_false(self, tmp_path):
        vp = VideoPlayer(_fake_app(tmp_path))
        assert vp.play('nope') is False

    def test_play_empty_clip_returns_false(self, tmp_path):
        (tmp_path / 'empty').mkdir()
        vp = VideoPlayer(_fake_app(tmp_path))
        assert vp.play('empty') is False

    def test_play_spawns_thread_and_renders(self, tmp_path):
        _make_clip(tmp_path, 'run', frames=3)
        app = _fake_app(tmp_path)
        vp = VideoPlayer(app)
        assert vp.play('run', fps=60.0, loop=True) is True
        assert vp.is_running
        time.sleep(0.15)
        vp.stop()
        assert app.display.core.fill.call_count > 0

    def test_non_loop_stops_after_one_pass(self, tmp_path):
        _make_clip(tmp_path, 'once', frames=2)
        app = _fake_app(tmp_path)
        vp = VideoPlayer(app)
        vp.play('once', fps=60.0, loop=False)
        # Wait enough for 2 frames plus join
        for _ in range(30):
            if not vp.is_running:
                break
            time.sleep(0.05)
        assert not vp.is_running

    def test_stop_clears_display(self, tmp_path):
        _make_clip(tmp_path, 'clip', frames=2)
        app = _fake_app(tmp_path)
        vp = VideoPlayer(app)
        vp.play('clip', fps=30.0)
        vp.stop()
        app.display.clear.assert_called()

    def test_status_reflects_state(self, tmp_path):
        _make_clip(tmp_path, 'show', frames=2)
        app = _fake_app(tmp_path)
        vp = VideoPlayer(app)
        vp.play('show', fps=10.0)
        status = vp.status
        assert status['running']
        assert status['clip'] == 'show'
        assert status['fps'] == 10.0
        assert status['loop'] is True
        vp.stop()
        assert vp.status['running'] is False

    def test_directory_traversal_rejected(self, tmp_path):
        _make_clip(tmp_path, 'real')
        vp = VideoPlayer(_fake_app(tmp_path))
        assert vp.play('../outside') is False
        assert vp.play('') is False

    def test_frames_cached_across_plays(self, tmp_path):
        _make_clip(tmp_path, 'cache', frames=2)
        vp = VideoPlayer(_fake_app(tmp_path))
        vp.play('cache')
        vp.stop()
        cache_size_first = len(vp._cache)
        vp.play('cache')
        vp.stop()
        # Same clip path key, so cache size should be unchanged.
        assert len(vp._cache) == cache_size_first

    def test_invalidate_cache(self, tmp_path):
        _make_clip(tmp_path, 'x', frames=1)
        vp = VideoPlayer(_fake_app(tmp_path))
        vp.play('x')
        vp.stop()
        assert vp._cache
        vp.invalidate_cache()
        assert vp._cache == {}
