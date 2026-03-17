#!/usr/bin/env python3
"""
Flipdot display simulator using curses.

Renders the 7×30 grid in the terminal with a flipdot aesthetic.
Supports all 4 cellular automata and text message preview.

Usage:
  python simulate.py                    # Game of Life (default)
  python simulate.py life               # Game of Life
  python simulate.py brain              # Brian's Brain
  python simulate.py elementary         # Rule 30
  python simulate.py elementary 90      # Rule 90
  python simulate.py elementary 110     # Rule 110
  python simulate.py cyclic             # Cyclic CA (4 states)
  python simulate.py text "HELLO"       # Preview text message
  python simulate.py monitor            # Monitor live display (localhost:5000)
  python simulate.py monitor 192.168.1.50  # Monitor remote Pi

Controls (automata mode):
  q / ESC   — quit
  SPACE     — pause/resume
  r         — randomize grid
  c         — clear grid
  n         — next automaton
  +/-       — speed up/slow down
  1-4       — switch: 1=life, 2=brain, 3=elementary, 4=cyclic

Controls (monitor mode):
  q / ESC   — quit
  +/-       — poll speed up/slow down
"""

import curses
import sys
import time

from app.display.automata import (
    Grid,
    game_of_life,
    brians_brain,
    elementary_ca,
    cyclic_ca,
    random_states_grid,
)

# Display dimensions
ROWS = 7
COLS = 30

# Characters for rendering
DOT_ON = "\u2588\u2588"   # Full block (██) — "flipped" dot
DOT_OFF = "\u2592\u2592"  # Medium shade (▒▒) — unflipped dot
DOT_DYING = "\u2593\u2593"  # Dark shade (▓▓) — dying state (Brian's Brain)

AUTOMATA_NAMES = ['life', 'brain', 'elementary', 'cyclic']


class Simulator:
    def __init__(self, automaton='life', rule=30, speed=0.15):
        self.automaton = automaton
        self.rule = rule
        self.speed = speed
        self.paused = False
        self.generation = 0

        # Grids
        self.grid = Grid(ROWS, COLS)
        self.dying_grid = Grid(ROWS, COLS)
        self.states_grid = None

        self._init_grid()

    def _init_grid(self):
        self.generation = 0
        self.dying_grid = Grid(ROWS, COLS)
        self.states_grid = None

        if self.automaton == 'elementary':
            self.grid = Grid(ROWS, COLS)
            self.grid.set(0, COLS // 2, 1)
        elif self.automaton == 'cyclic':
            self.grid = Grid(ROWS, COLS)
            self.states_grid = random_states_grid(ROWS, COLS, num_states=4)
            for r in range(ROWS):
                for c in range(COLS):
                    self.grid.set(r, c, self.states_grid[r][c] != 0)
        else:
            self.grid = Grid(ROWS, COLS)
            self.grid.randomize(0.4)

    def step(self):
        if self.automaton == 'life':
            self.grid = game_of_life(self.grid)
        elif self.automaton == 'brain':
            self.grid, self.dying_grid = brians_brain(self.grid, self.dying_grid)
        elif self.automaton == 'elementary':
            self.grid = elementary_ca(self.grid, rule=self.rule)
        elif self.automaton == 'cyclic':
            self.grid, self.states_grid = cyclic_ca(
                self.grid, self.states_grid, num_states=4, threshold=1
            )
        self.generation += 1

    def next_automaton(self):
        idx = AUTOMATA_NAMES.index(self.automaton)
        self.automaton = AUTOMATA_NAMES[(idx + 1) % len(AUTOMATA_NAMES)]
        self._init_grid()


def draw_frame(stdscr, sim):
    """Draw one frame of the display."""
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # Check terminal size
    needed_w = COLS * 2 + 4  # 2 chars per dot + border
    needed_h = ROWS + 8       # grid + chrome
    if h < needed_h or w < needed_w:
        stdscr.addstr(0, 0, f"Terminal too small ({w}x{h}). Need {needed_w}x{needed_h}.")
        stdscr.refresh()
        return

    # Center horizontally
    x_off = max(0, (w - needed_w) // 2)
    y_off = 1

    # Title
    title = " BIOPUNK FLIPDOT SIMULATOR "
    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(y_off, x_off, title.center(needed_w))
    stdscr.attroff(curses.color_pair(2))
    y_off += 1

    # Top border
    stdscr.attron(curses.color_pair(3))
    stdscr.addstr(y_off, x_off, "\u250c" + "\u2500" * (COLS * 2) + "\u2510")
    stdscr.attroff(curses.color_pair(3))
    y_off += 1

    # Grid
    for r in range(ROWS):
        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(y_off + r, x_off, "\u2502")
        stdscr.attroff(curses.color_pair(3))

        for c in range(COLS):
            alive = sim.grid.get(r, c)
            dying = sim.dying_grid.get(r, c) if sim.automaton == 'brain' else 0

            if alive:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y_off + r, x_off + 1 + c * 2, DOT_ON)
                stdscr.attroff(curses.color_pair(1))
            elif dying:
                stdscr.attron(curses.color_pair(4))
                stdscr.addstr(y_off + r, x_off + 1 + c * 2, DOT_DYING)
                stdscr.attroff(curses.color_pair(4))
            else:
                stdscr.attron(curses.color_pair(5))
                stdscr.addstr(y_off + r, x_off + 1 + c * 2, DOT_OFF)
                stdscr.attroff(curses.color_pair(5))

        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(y_off + r, x_off + 1 + COLS * 2, "\u2502")
        stdscr.attroff(curses.color_pair(3))

    y_off += ROWS

    # Bottom border
    stdscr.attron(curses.color_pair(3))
    stdscr.addstr(y_off, x_off, "\u2514" + "\u2500" * (COLS * 2) + "\u2518")
    stdscr.attroff(curses.color_pair(3))
    y_off += 1

    # Status line
    status = (
        f" {sim.automaton.upper()}"
        f"{f' (rule {sim.rule})' if sim.automaton == 'elementary' else ''}"
        f"  gen:{sim.generation}"
        f"  alive:{sim.grid.count_alive()}"
        f"  speed:{sim.speed:.2f}s"
        f"{'  [PAUSED]' if sim.paused else ''}"
    )
    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(y_off, x_off, status.ljust(needed_w))
    stdscr.attroff(curses.color_pair(2))
    y_off += 1

    # Help
    stdscr.attron(curses.color_pair(6))
    stdscr.addstr(y_off + 1, x_off,     " q:quit  SPACE:pause  r:randomize  c:clear  n:next ")
    stdscr.addstr(y_off + 2, x_off,     " 1:life  2:brain  3:elementary  4:cyclic  +/-:speed ")
    stdscr.attroff(curses.color_pair(6))

    stdscr.refresh()


def draw_text_preview(stdscr, text):
    """Preview a text message using the 7-row character dict from core."""
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # Import the core character dict
    sys.path.insert(0, '.')
    from core.core import dict as char_dict

    # Build the display buffer
    buf = b''
    for ch in text.upper():
        if ch in char_dict:
            buf += char_dict[ch]
        elif ch == ' ':
            buf += char_dict.get('space', b'\x00')
        else:
            buf += char_dict.get('?', b'\x00')
        buf += b'\x00'  # gap

    # Convert bytes to grid
    grid = Grid(ROWS, min(COLS, len(buf)))
    for col in range(min(COLS, len(buf))):
        byte_val = buf[col]
        for row in range(ROWS):
            # Core encoding: bit 0 = bottom (row 6), bit 6 = top (row 0)
            if byte_val & (1 << (6 - row)):
                grid.set(row, col, 1)

    needed_w = COLS * 2 + 4
    x_off = max(0, (w - needed_w) // 2)
    y_off = 1

    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(y_off, x_off, " TEXT PREVIEW ".center(needed_w))
    stdscr.attroff(curses.color_pair(2))
    y_off += 1

    stdscr.attron(curses.color_pair(3))
    stdscr.addstr(y_off, x_off, "\u250c" + "\u2500" * (COLS * 2) + "\u2510")
    stdscr.attroff(curses.color_pair(3))
    y_off += 1

    for r in range(ROWS):
        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(y_off + r, x_off, "\u2502")
        stdscr.attroff(curses.color_pair(3))

        for c in range(COLS):
            if grid.get(r, c):
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y_off + r, x_off + 1 + c * 2, DOT_ON)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.attron(curses.color_pair(5))
                stdscr.addstr(y_off + r, x_off + 1 + c * 2, DOT_OFF)
                stdscr.attroff(curses.color_pair(5))

        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(y_off + r, x_off + 1 + COLS * 2, "\u2502")
        stdscr.attroff(curses.color_pair(3))

    y_off += ROWS
    stdscr.attron(curses.color_pair(3))
    stdscr.addstr(y_off, x_off, "\u2514" + "\u2500" * (COLS * 2) + "\u2518")
    stdscr.attroff(curses.color_pair(3))
    y_off += 1

    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(y_off, x_off, f' "{text}" '.ljust(needed_w))
    stdscr.attroff(curses.color_pair(2))
    y_off += 2

    stdscr.attron(curses.color_pair(6))
    stdscr.addstr(y_off, x_off, " Press any key to exit ")
    stdscr.attroff(curses.color_pair(6))

    stdscr.refresh()
    stdscr.timeout(-1)
    stdscr.getch()


def init_colors():
    curses.start_color()
    curses.use_default_colors()

    if curses.can_change_color():
        # Custom biopunk palette
        curses.init_color(10, 0, 1000, 255)    # bright green
        curses.init_color(11, 0, 400, 100)      # dim green
        curses.init_color(12, 40, 40, 40)        # near-black bg
        curses.init_color(13, 600, 800, 0)       # yellow-green (dying)
        curses.init_color(14, 150, 150, 150)     # dark gray
        curses.init_pair(1, 10, 12)   # ON dots: bright green on black
        curses.init_pair(2, 10, -1)   # title/status: green on default
        curses.init_pair(3, 11, -1)   # border: dim green
        curses.init_pair(4, 13, 12)   # dying dots: yellow-green
        curses.init_pair(5, 14, 12)   # OFF dots: dark gray on black
        curses.init_pair(6, 11, -1)   # help text: dim green
    else:
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_GREEN, -1)


def monitor_mode(stdscr, host):
    """Live monitor: polls the server and renders the actual display state."""
    import json
    import urllib.request
    import urllib.error

    curses.curs_set(0)
    init_colors()

    base_url = f'http://{host}:5000' if ':' not in host else f'http://{host}'
    poll_interval = 0.25  # seconds

    stdscr.timeout(int(poll_interval * 1000))

    frame_num = 0
    last_error = None
    grid = Grid(ROWS, COLS)
    server_info = {}

    while True:
        # Poll server
        try:
            req = urllib.request.Request(f'{base_url}/api/display/frame')
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
            frame_data = data.get('frame', [0] * 105)
            grid = Grid.from_display_bytes(bytes(frame_data))
            server_info = data
            last_error = None
            frame_num += 1
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            last_error = str(e)[:60]

        # Draw
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        needed_w = COLS * 2 + 4
        needed_h = ROWS + 10
        if h < needed_h or w < needed_w:
            stdscr.addstr(0, 0, f"Terminal too small ({w}x{h}). Need {needed_w}x{needed_h}.")
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                break
            continue

        x_off = max(0, (w - needed_w) // 2)
        y_off = 1

        # Title
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(y_off, x_off, f" LIVE MONITOR \u2014 {base_url} ".center(needed_w))
        stdscr.attroff(curses.color_pair(2))
        y_off += 1

        # Top border
        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(y_off, x_off, "\u250c" + "\u2500" * (COLS * 2) + "\u2510")
        stdscr.attroff(curses.color_pair(3))
        y_off += 1

        # Grid
        for r in range(ROWS):
            stdscr.attron(curses.color_pair(3))
            stdscr.addstr(y_off + r, x_off, "\u2502")
            stdscr.attroff(curses.color_pair(3))

            for c in range(COLS):
                if grid.get(r, c):
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(y_off + r, x_off + 1 + c * 2, DOT_ON)
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.attron(curses.color_pair(5))
                    stdscr.addstr(y_off + r, x_off + 1 + c * 2, DOT_OFF)
                    stdscr.attroff(curses.color_pair(5))

            stdscr.attron(curses.color_pair(3))
            stdscr.addstr(y_off + r, x_off + 1 + COLS * 2, "\u2502")
            stdscr.attroff(curses.color_pair(3))

        y_off += ROWS

        # Bottom border
        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(y_off, x_off, "\u2514" + "\u2500" * (COLS * 2) + "\u2518")
        stdscr.attroff(curses.color_pair(3))
        y_off += 1

        # Status
        queue = server_info.get('queue_pending', '?')
        playlist = server_info.get('playlist_playing') or 'none'
        automaton = server_info.get('automaton') or 'none'
        alive = grid.count_alive()

        status = f" frame:{frame_num}  dots:{alive}  queue:{queue}  playlist:{playlist}  CA:{automaton}"
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(y_off, x_off, status[:needed_w].ljust(needed_w))
        stdscr.attroff(curses.color_pair(2))
        y_off += 1

        if last_error:
            stdscr.attron(curses.color_pair(4))
            stdscr.addstr(y_off, x_off, f" ERR: {last_error}"[:needed_w])
            stdscr.attroff(curses.color_pair(4))
            y_off += 1

        # Help
        stdscr.attron(curses.color_pair(6))
        stdscr.addstr(y_off + 1, x_off, f" q:quit  +/-:poll speed ({poll_interval:.2f}s) ")
        stdscr.attroff(curses.color_pair(6))

        stdscr.refresh()

        # Handle input
        key = stdscr.getch()
        if key in (ord('q'), ord('Q'), 27):
            break
        elif key in (ord('+'), ord('=')):
            poll_interval = max(0.05, poll_interval - 0.05)
            stdscr.timeout(int(poll_interval * 1000))
        elif key in (ord('-'), ord('_')):
            poll_interval = min(5.0, poll_interval + 0.05)
            stdscr.timeout(int(poll_interval * 1000))


def main(stdscr):
    curses.curs_set(0)
    init_colors()

    args = sys.argv[1:]

    # Monitor mode
    if args and args[0] == 'monitor':
        host = args[1] if len(args) > 1 else 'localhost'
        monitor_mode(stdscr, host)
        return

    # Text preview mode
    if args and args[0] == 'text':
        text = ' '.join(args[1:]) or 'HELLO'
        draw_text_preview(stdscr, text)
        return

    # Parse automaton type
    automaton = 'life'
    rule = 30
    if args:
        if args[0] in AUTOMATA_NAMES:
            automaton = args[0]
        if automaton == 'elementary' and len(args) > 1:
            rule = int(args[1])

    sim = Simulator(automaton=automaton, rule=rule)
    stdscr.timeout(int(sim.speed * 1000))

    while True:
        draw_frame(stdscr, sim)

        key = stdscr.getch()

        if key in (ord('q'), ord('Q'), 27):  # q or ESC
            break
        elif key == ord(' '):
            sim.paused = not sim.paused
        elif key == ord('r'):
            sim._init_grid()
            if sim.automaton != 'elementary':
                sim.grid.randomize(0.4)
        elif key == ord('c'):
            sim.grid.clear()
            sim.dying_grid.clear()
            sim.generation = 0
        elif key == ord('n'):
            sim.next_automaton()
        elif key == ord('1'):
            sim.automaton = 'life'
            sim._init_grid()
        elif key == ord('2'):
            sim.automaton = 'brain'
            sim._init_grid()
        elif key == ord('3'):
            sim.automaton = 'elementary'
            sim._init_grid()
        elif key == ord('4'):
            sim.automaton = 'cyclic'
            sim._init_grid()
        elif key in (ord('+'), ord('=')):
            sim.speed = max(0.02, sim.speed - 0.03)
            stdscr.timeout(int(sim.speed * 1000))
        elif key in (ord('-'), ord('_')):
            sim.speed = min(2.0, sim.speed + 0.03)
            stdscr.timeout(int(sim.speed * 1000))

        if not sim.paused:
            sim.step()


if __name__ == '__main__':
    curses.wrapper(main)
