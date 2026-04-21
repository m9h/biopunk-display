"""Tests for the ticker manager (app/display/ticker.py).

Uses a mock display so no hardware or Flask app is required.
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from app.display.ticker import TickerManager, GAP_COLS, VIEW_COLS


def _fake_app():
    """Minimal app stub with a display that captures the frames sent to it."""
    app = MagicMock()
    app.display._lock = threading.Lock()
    app.display.set_frame = MagicMock()
    app.display.core.fill = MagicMock()
    # getbytes returns a deterministic byte per char so we can inspect output
    app.display.core.getbytes = lambda text: bytes(range(1, len(text) + 1))
    app.display.clear = MagicMock()
    return app


class TestSliceHelper:

    def test_no_wrap(self):
        buf = b'abcdefghij'
        assert TickerManager._slice(buf, 2, 4, len(buf)) == b'cdef'

    def test_wraps_around_end(self):
        buf = b'abcdefghij'
        assert TickerManager._slice(buf, 8, 4, len(buf)) == b'ijab'

    def test_exactly_fills_to_end(self):
        buf = b'abcdefghij'
        assert TickerManager._slice(buf, 6, 4, len(buf)) == b'ghij'


class TestTickerLifecycle:

    def test_empty_text_rejected(self):
        t = TickerManager(_fake_app())
        assert t.start('') is False
        assert t.start('   ') is False
        assert not t.is_running

    def test_start_spawns_thread(self):
        t = TickerManager(_fake_app())
        assert t.start('HELLO') is True
        assert t.is_running
        t.stop()
        assert not t.is_running

    def test_status_reports_fields_while_running(self):
        t = TickerManager(_fake_app())
        t.start('ABC', speed=0.5, mode='double')
        status = t.status
        assert status['running']
        assert status['text'] == 'ABC'
        assert status['mode'] == 'double'
        assert status['speed'] == 0.5
        t.stop()
        assert t.status['running'] is False

    def test_invalid_mode_falls_back_to_single(self):
        t = TickerManager(_fake_app())
        t.start('X', mode='quadruple')
        assert t._mode == 'single'
        t.stop()

    def test_speed_clamped(self):
        t = TickerManager(_fake_app())
        t.start('X', speed=0.0001)
        assert t._speed == 0.03
        t.stop()
        t.start('X', speed=10.0)
        assert t._speed == 1.0
        t.stop()

    def test_stop_clears_display(self):
        app = _fake_app()
        t = TickerManager(app)
        t.start('HELLO')
        t.stop()
        app.display.clear.assert_called()

    def test_stop_without_start_does_nothing(self):
        app = _fake_app()
        t = TickerManager(app)
        t.stop()
        app.display.clear.assert_not_called()


class TestTickerRendering:

    def test_single_mode_writes_105_byte_frames(self):
        app = _fake_app()
        t = TickerManager(app)
        t.start('HI', speed=0.03)
        time.sleep(0.15)
        t.stop()

        assert app.display.core.fill.call_count > 0
        # Every buffer must be 105 bytes so fill() sees a full frame.
        for call in app.display.core.fill.call_args_list:
            buf = call.args[0]
            assert len(buf) == 105
            # Single mode leaves bottom panel (bytes 30..60) blank.
            assert buf[30:60] == b'\x00' * 30

    def test_double_mode_fills_both_panels(self):
        app = _fake_app()
        t = TickerManager(app)
        t.start('OK', speed=0.03, mode='double')
        time.sleep(0.15)
        t.stop()

        # At least one frame must contain data in both panels.
        any_top = False
        any_bottom = False
        for call in app.display.core.fill.call_args_list:
            buf = call.args[0]
            assert len(buf) == 105
            if any(buf[:30]):
                any_top = True
            if any(buf[30:60]):
                any_bottom = True
        assert any_top, 'expected top panel pixels'
        assert any_bottom, 'expected bottom panel pixels'

    def test_starting_twice_replaces_first_ticker(self):
        app = _fake_app()
        t = TickerManager(app)
        t.start('FIRST')
        first_thread = t._thread
        t.start('SECOND')
        second_thread = t._thread
        assert first_thread is not second_thread
        assert t._text == 'SECOND'
        t.stop()
