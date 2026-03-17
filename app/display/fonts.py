"""
Double-height font system for the flipdot display.

Uses both halves of the 7×105 display to render 14-pixel-tall characters
via the proven quadrant mapping from simple_working_double_height.py.
"""

import time

# 14-row patterns: rows 0-6 = top half, rows 7-13 = bottom half
DOUBLE_HEIGHT = {
    'A': [
        '  ##  ', ' #  # ', '#    #', '#    #', '#    #', '######', '#    #',
        '#    #', '#    #', '#    #', '#    #', '#    #', '      ', '      '
    ],
    'B': [
        '##### ', '#    #', '#    #', '#    #', '##### ', '##### ',
        '#    #', '#    #', '#    #', '#    #', '#    #', '##### ',
        '      ', '      '
    ],
    'C': [
        ' #### ', '#    #', '#     ', '#     ', '#     ', '#     ',
        '#     ', '#     ', '#     ', '#     ', '#    #', ' #### ',
        '      ', '      '
    ],
    'D': [
        '##### ', '#    #', '#    #', '#    #', '#    #', '#    #',
        '#    #', '#    #', '#    #', '#    #', '#    #', '##### ',
        '      ', '      '
    ],
    'E': [
        '######', '#     ', '#     ', '#     ', '##### ', '##### ',
        '#     ', '#     ', '#     ', '#     ', '#     ', '######',
        '      ', '      '
    ],
    'F': [
        '######', '#     ', '#     ', '#     ', '##### ', '##### ',
        '#     ', '#     ', '#     ', '#     ', '#     ', '#     ',
        '      ', '      '
    ],
    'G': [
        ' #### ', '#    #', '#     ', '#     ', '#     ', '# ####',
        '#    #', '#    #', '#    #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    'H': [
        '#    #', '#    #', '#    #', '#    #', '######', '######',
        '#    #', '#    #', '#    #', '#    #', '#    #', '#    #',
        '      ', '      '
    ],
    'I': [
        '######', '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ', '######',
        '      ', '      '
    ],
    'J': [
        '######', '    ##', '    ##', '    ##', '    ##', '    ##',
        '    ##', '    ##', '    ##', '#   ##', '#   ##', ' #### ',
        '      ', '      '
    ],
    'K': [
        '#    #', '#   # ', '#  #  ', '# #   ', '##    ', '##    ',
        '# #   ', '#  #  ', '#   # ', '#    #', '#    #', '#    #',
        '      ', '      '
    ],
    'L': [
        '#     ', '#     ', '#     ', '#     ', '#     ', '#     ',
        '#     ', '#     ', '#     ', '#     ', '#     ', '######',
        '      ', '      '
    ],
    'M': [
        '#    #', '##  ##', '# ## #', '#    #', '#    #', '#    #',
        '#    #', '#    #', '#    #', '#    #', '#    #', '#    #',
        '      ', '      '
    ],
    'N': [
        '#    #', '##   #', '# #  #', '#  # #', '#   ##', '#    #',
        '#    #', '#    #', '#    #', '#    #', '#    #', '#    #',
        '      ', '      '
    ],
    'O': [
        ' #### ', '#    #', '#    #', '#    #', '#    #', '#    #',
        '#    #', '#    #', '#    #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    'P': [
        '##### ', '#    #', '#    #', '#    #', '##### ', '#     ',
        '#     ', '#     ', '#     ', '#     ', '#     ', '#     ',
        '      ', '      '
    ],
    'Q': [
        ' #### ', '#    #', '#    #', '#    #', '#    #', '#    #',
        '#    #', '#    #', '#  # #', '#   ##', '#    #', ' #### ',
        '      ', '      '
    ],
    'R': [
        '##### ', '#    #', '#    #', '#    #', '##### ', '# #   ',
        '#  #  ', '#   # ', '#    #', '#    #', '#    #', '#    #',
        '      ', '      '
    ],
    'S': [
        ' #### ', '#    #', '#     ', ' #    ', '  ##  ', '   ## ',
        '    # ', '     #', '     #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    'T': [
        '######', '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '      ', '      '
    ],
    'U': [
        '#    #', '#    #', '#    #', '#    #', '#    #', '#    #',
        '#    #', '#    #', '#    #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    'V': [
        '#    #', '#    #', '#    #', '#    #', '#    #', '#    #',
        '#    #', ' #  # ', ' #  # ', '  ##  ', '  ##  ', '  ##  ',
        '      ', '      '
    ],
    'W': [
        '#    #', '#    #', '#    #', '#    #', '#    #', '#    #',
        '#    #', '# ## #', '# ## #', '##  ##', '#    #', '#    #',
        '      ', '      '
    ],
    'X': [
        '#    #', ' #  # ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '  ##  ', '  ##  ', '  ##  ', ' #  # ', '#    #', '#    #',
        '      ', '      '
    ],
    'Y': [
        '#    #', ' #  # ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '      ', '      '
    ],
    'Z': [
        '######', '    # ', '   #  ', '  #   ', ' #    ', '#     ',
        '#     ', ' #    ', '  #   ', '   #  ', '    # ', '######',
        '      ', '      '
    ],
    '0': [
        ' #### ', '#    #', '#   ##', '#  # #', '# #  #', '##   #',
        '#    #', '#    #', '#    #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    '1': [
        '  ##  ', ' ###  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ', '######',
        '      ', '      '
    ],
    '2': [
        ' #### ', '#    #', '     #', '    ##', '   ## ', '  ##  ',
        ' ##   ', '##    ', '#     ', '#     ', '#     ', '######',
        '      ', '      '
    ],
    '3': [
        ' #### ', '#    #', '     #', '     #', ' #### ', ' #### ',
        '     #', '     #', '     #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    '4': [
        '#    #', '#    #', '#    #', '#    #', '######', '     #',
        '     #', '     #', '     #', '     #', '     #', '     #',
        '      ', '      '
    ],
    '5': [
        '######', '#     ', '#     ', '#     ', '##### ', '     #',
        '     #', '     #', '     #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    '6': [
        ' #### ', '#    #', '#     ', '#     ', '##### ', '#    #',
        '#    #', '#    #', '#    #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    '7': [
        '######', '     #', '    # ', '   #  ', '  #   ', ' #    ',
        '#     ', '#     ', '#     ', '#     ', '#     ', '#     ',
        '      ', '      '
    ],
    '8': [
        ' #### ', '#    #', '#    #', '#    #', ' #### ', ' #### ',
        '#    #', '#    #', '#    #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    '9': [
        ' #### ', '#    #', '#    #', '#    #', '#    #', ' #####',
        '     #', '     #', '     #', '#    #', '#    #', ' #### ',
        '      ', '      '
    ],
    ' ': [
        '      ', '      ', '      ', '      ', '      ', '      ',
        '      ', '      ', '      ', '      ', '      ', '      ',
        '      ', '      '
    ],
    '!': [
        '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ', '  ##  ',
        '  ##  ', '      ', '      ', '  ##  ', '  ##  ', '  ##  ',
        '      ', '      '
    ],
    '?': [
        ' #### ', '#    #', '     #', '    ##', '   ## ', '  ##  ',
        '  ##  ', '      ', '      ', '  ##  ', '  ##  ', '  ##  ',
        '      ', '      '
    ],
    '.': [
        '      ', '      ', '      ', '      ', '      ', '      ',
        '      ', '      ', '      ', '  ##  ', '  ##  ', '  ##  ',
        '      ', '      '
    ],
    '-': [
        '      ', '      ', '      ', '      ', '######', '######',
        '      ', '      ', '      ', '      ', '      ', '      ',
        '      ', '      '
    ],
    ':': [
        '      ', '  ##  ', '  ##  ', '      ', '      ', '      ',
        '      ', '  ##  ', '  ##  ', '      ', '      ', '      ',
        '      ', '      '
    ],
}


def pattern_to_bytes(pattern):
    """Convert a 14-row visual pattern into top/bottom byte arrays."""
    width = len(pattern[0]) if pattern else 0
    top_bytes = []
    bottom_bytes = []

    for col in range(width):
        top_byte = 0
        bottom_byte = 0
        for row in range(7):
            if col < len(pattern[row]) and pattern[row][col] == '#':
                top_byte |= (1 << (6 - row))
        for row in range(7, 14):
            if col < len(pattern[row]) and pattern[row][col] == '#':
                bottom_byte |= (1 << (13 - row))
        top_bytes.append(top_byte)
        bottom_bytes.append(bottom_byte)

    return bytes(top_bytes), bytes(bottom_bytes)


def text_to_bytes(text, double_wide=False):
    """Convert a string to top/bottom byte arrays using double-height font."""
    all_top = []
    all_bottom = []

    for char in text.upper():
        pattern = DOUBLE_HEIGHT.get(char)
        if pattern is None:
            pattern = DOUBLE_HEIGHT[' ']
        if double_wide:
            pattern = [''.join(c + c for c in row) for row in pattern]
        top, bottom = pattern_to_bytes(pattern)
        all_top.extend(top)
        all_bottom.extend(bottom)
        # 1-col gap between characters
        all_top.append(0)
        all_bottom.append(0)

    return bytes(all_top), bytes(all_bottom)


def _build_quadrant_buffer(top_chunk, bottom_chunk):
    """Map top/bottom byte chunks into the 105-byte quadrant buffer."""
    buf = [0] * 105
    for i in range(min(30, len(top_chunk))):
        buf[i] = top_chunk[i]
    for i in range(min(30, len(bottom_chunk))):
        buf[30 + i] = bottom_chunk[i]
    return bytes(buf)


def display_double_static(core, text, double_wide=False):
    """Show static double-height text centered on the display."""
    top, bottom = text_to_bytes(text, double_wide=double_wide)
    # Center: pad so text is in the middle of the 30-col visible area
    text_width = len(top)
    pad = max(0, (30 - text_width) // 2)
    padded_top = b'\x00' * (105 + pad) + top + b'\x00' * 105
    padded_bottom = b'\x00' * (105 + pad) + bottom + b'\x00' * 105
    top_chunk = padded_top[103:103 + 105]
    bottom_chunk = padded_bottom[103:103 + 105]
    core.fill(_build_quadrant_buffer(top_chunk, bottom_chunk))


def scroll_double(core, text, speed=0.12, double_wide=False):
    """Scroll double-height text right-to-left."""
    top, bottom = text_to_bytes(text, double_wide=double_wide)
    padded_top = b'\x00' * 105 + top + b'\x00' * 105
    padded_bottom = b'\x00' * 105 + bottom + b'\x00' * 105
    total = len(padded_top) - 105

    for offset in range(0, total, 2):
        top_chunk = padded_top[offset:offset + 105]
        bottom_chunk = padded_bottom[offset:offset + 105]
        core.fill(_build_quadrant_buffer(top_chunk, bottom_chunk))
        time.sleep(speed)


def flash_double(core, text, cycles=5, on_time=0.3, off_time=0.3):
    """Flash double-height text on and off."""
    for _ in range(cycles):
        display_double_static(core, text)
        time.sleep(on_time)
        core.clear()
        time.sleep(off_time)


def typewriter_double(core, text):
    """Reveal double-height text one character at a time."""
    for i in range(1, len(text) + 1):
        display_double_static(core, text[:i])
        time.sleep(0.3)
    time.sleep(2)
