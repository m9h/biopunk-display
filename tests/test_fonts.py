"""Tests for double-height font system (app/display/fonts.py).

Validates character patterns, byte conversion, and quadrant buffer mapping
without requiring any display hardware.
"""

import pytest

from app.display.fonts import (
    DOUBLE_HEIGHT,
    pattern_to_bytes,
    text_to_bytes,
    _build_quadrant_buffer,
)


# ---------------------------------------------------------------------------
# 1. Character pattern validation
# ---------------------------------------------------------------------------

class TestDoubleHeightPatterns:

    def test_all_characters_have_14_rows(self):
        for char, pattern in DOUBLE_HEIGHT.items():
            assert len(pattern) == 14, f"Character '{char}' has {len(pattern)} rows, expected 14"

    def test_all_rows_consistent_width(self):
        for char, pattern in DOUBLE_HEIGHT.items():
            widths = {len(row) for row in pattern}
            assert len(widths) == 1, (
                f"Character '{char}' has inconsistent row widths: {widths}"
            )

    def test_all_rows_use_valid_chars(self):
        for char, pattern in DOUBLE_HEIGHT.items():
            for i, row in enumerate(pattern):
                assert set(row) <= {'#', ' '}, (
                    f"Character '{char}' row {i} has invalid chars: {set(row) - {'#', ' '}}"
                )

    def test_space_is_all_blank(self):
        for row in DOUBLE_HEIGHT[' ']:
            assert '#' not in row

    def test_expected_characters_present(self):
        # A-Z
        for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            assert c in DOUBLE_HEIGHT, f"Missing character '{c}'"
        # 0-9
        for c in '0123456789':
            assert c in DOUBLE_HEIGHT, f"Missing character '{c}'"
        # Punctuation
        for c in ' !?.-:':
            assert c in DOUBLE_HEIGHT, f"Missing character '{c}'"

    def test_bottom_two_rows_are_blank_padding(self):
        """Rows 12 and 13 are blank padding for all characters."""
        for char, pattern in DOUBLE_HEIGHT.items():
            assert pattern[12].strip() == '', f"Character '{char}' row 12 not blank"
            assert pattern[13].strip() == '', f"Character '{char}' row 13 not blank"


# ---------------------------------------------------------------------------
# 2. pattern_to_bytes
# ---------------------------------------------------------------------------

class TestPatternToBytes:

    def test_returns_two_byte_sequences(self):
        pattern = DOUBLE_HEIGHT['A']
        top, bottom = pattern_to_bytes(pattern)
        assert isinstance(top, bytes)
        assert isinstance(bottom, bytes)

    def test_output_length_matches_char_width(self):
        pattern = DOUBLE_HEIGHT['A']
        width = len(pattern[0])
        top, bottom = pattern_to_bytes(pattern)
        assert len(top) == width
        assert len(bottom) == width

    def test_space_produces_all_zeros(self):
        top, bottom = pattern_to_bytes(DOUBLE_HEIGHT[' '])
        assert all(b == 0 for b in top)
        assert all(b == 0 for b in bottom)

    def test_top_bytes_reflect_rows_0_to_6(self):
        """A column with '#' in row 0 should set bit 6 (1<<6=64) in top byte."""
        # Build a simple 1-col test pattern: '#' in row 0, rest blank
        pattern = ['#'] + [' '] * 13
        top, bottom = pattern_to_bytes(pattern)
        assert top[0] == (1 << 6)  # row 0 maps to bit 6
        assert bottom[0] == 0

    def test_bottom_bytes_reflect_rows_7_to_13(self):
        """A column with '#' in row 7 should set bit 6 (1<<(13-7)) in bottom byte."""
        pattern = [' '] * 7 + ['#'] + [' '] * 6
        top, bottom = pattern_to_bytes(pattern)
        assert top[0] == 0
        assert bottom[0] == (1 << 6)  # row 7 maps to bit (13-7)=6

    def test_all_hash_column_produces_max_values(self):
        """A column that's '#' in all 14 rows should produce 0x7F for both halves."""
        pattern = ['#'] * 14
        top, bottom = pattern_to_bytes(pattern)
        assert top[0] == 0x7F  # bits 0-6 all set
        assert bottom[0] == 0x7F


# ---------------------------------------------------------------------------
# 3. text_to_bytes
# ---------------------------------------------------------------------------

class TestTextToBytes:

    def test_returns_two_byte_sequences(self):
        top, bottom = text_to_bytes('A')
        assert isinstance(top, bytes)
        assert isinstance(bottom, bytes)

    def test_same_length_top_and_bottom(self):
        top, bottom = text_to_bytes('HELLO')
        assert len(top) == len(bottom)

    def test_single_char_length(self):
        """Single char should be char_width + 1 (gap byte)."""
        char_width = len(DOUBLE_HEIGHT['A'][0])
        top, bottom = text_to_bytes('A')
        assert len(top) == char_width + 1  # 1-col gap after

    def test_two_chars_have_gap(self):
        """Two chars: width1 + 1 + width2 + 1."""
        w1 = len(DOUBLE_HEIGHT['A'][0])
        w2 = len(DOUBLE_HEIGHT['B'][0])
        top, _ = text_to_bytes('AB')
        assert len(top) == w1 + 1 + w2 + 1

    def test_gap_bytes_are_zero(self):
        top, bottom = text_to_bytes('A')
        # Last byte should be the gap (0)
        assert top[-1] == 0
        assert bottom[-1] == 0

    def test_space_in_text(self):
        top, _ = text_to_bytes(' ')
        space_width = len(DOUBLE_HEIGHT[' '][0])
        assert len(top) == space_width + 1

    def test_lowercase_converted_to_upper(self):
        top_lower, bottom_lower = text_to_bytes('hello')
        top_upper, bottom_upper = text_to_bytes('HELLO')
        assert top_lower == top_upper
        assert bottom_lower == bottom_upper

    def test_unknown_char_falls_back_to_space(self):
        """Characters not in DOUBLE_HEIGHT should render as spaces."""
        top_unknown, bottom_unknown = text_to_bytes('@')
        top_space, bottom_space = text_to_bytes(' ')
        assert top_unknown == top_space
        assert bottom_unknown == bottom_space


# ---------------------------------------------------------------------------
# 4. text_to_bytes with double_wide=True
# ---------------------------------------------------------------------------

class TestTextToBytesDoubleWide:

    def test_double_wide_doubles_width(self):
        top_normal, _ = text_to_bytes('A')
        top_wide, _ = text_to_bytes('A', double_wide=True)
        # Double wide: each char column is doubled, so char width * 2 + 1 gap
        char_width = len(DOUBLE_HEIGHT['A'][0])
        assert len(top_normal) == char_width + 1
        assert len(top_wide) == char_width * 2 + 1

    def test_double_wide_still_same_top_bottom_length(self):
        top, bottom = text_to_bytes('HI', double_wide=True)
        assert len(top) == len(bottom)


# ---------------------------------------------------------------------------
# 5. _build_quadrant_buffer
# ---------------------------------------------------------------------------

class TestBuildQuadrantBuffer:

    def test_output_is_105_bytes(self):
        buf = _build_quadrant_buffer(b'\x00' * 30, b'\x00' * 30)
        assert len(buf) == 105

    def test_top_chunk_in_first_30_bytes(self):
        top = bytes([0x7F] * 30)
        bottom = bytes([0x00] * 30)
        buf = _build_quadrant_buffer(top, bottom)
        assert buf[:30] == top
        assert buf[30:60] == bottom

    def test_bottom_chunk_at_offset_30(self):
        top = bytes([0x00] * 30)
        bottom = bytes([0x55] * 30)
        buf = _build_quadrant_buffer(top, bottom)
        assert buf[30:60] == bottom

    def test_remaining_bytes_are_zero(self):
        buf = _build_quadrant_buffer(b'\x7F' * 30, b'\x7F' * 30)
        assert buf[60:] == bytes(45)

    def test_truncates_oversized_chunks(self):
        """Chunks longer than 30 are truncated, not overflow."""
        top = bytes([0x7F] * 50)
        bottom = bytes([0x55] * 50)
        buf = _build_quadrant_buffer(top, bottom)
        assert len(buf) == 105
        assert buf[:30] == bytes([0x7F] * 30)
        assert buf[30:60] == bytes([0x55] * 30)

    def test_undersized_chunks_zero_padded(self):
        buf = _build_quadrant_buffer(b'\x7F' * 10, b'\x55' * 5)
        assert buf[:10] == bytes([0x7F] * 10)
        assert buf[10:30] == bytes(20)  # zero padded
        assert buf[30:35] == bytes([0x55] * 5)
        assert buf[35:60] == bytes(25)  # zero padded
