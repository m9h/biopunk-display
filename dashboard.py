#!/usr/bin/env python3
"""
Biopunk Flipdot Dashboard — curses-based monitoring console.

Combines live display mirror, server status, system stats, and process info.
Designed to run in a byobu/tmux pane on the Pi's monitor.

Usage:
  python dashboard.py                  # Connect to localhost:5000
  python dashboard.py 192.168.1.50     # Connect to remote host
  python dashboard.py :8080            # Custom port on localhost

Controls:
  q / ESC   — quit
  1-5       — start CA (1=life 2=brain 3=rule30 4=rule90 5=cyclic)
  0 / s     — stop CA
  +/-       — poll speed
  r         — restart current CA
"""

import curses
import json
import os
import sys
import time
import urllib.request
import urllib.error

from app.display.automata import Grid

# Display dimensions
ROWS = 7
COLS = 30

# Characters for rendering
DOT_ON = "\u2588\u2588"    # ██
DOT_OFF = "\u2592\u2592"   # ▒▒

CA_KEYS = {
    ord('1'): ('life', {}),
    ord('2'): ('brain', {}),
    ord('3'): ('elementary', {'rule': 30}),
    ord('4'): ('elementary', {'rule': 90}),
    ord('5'): ('cyclic', {}),
}


def init_colors():
    curses.start_color()
    curses.use_default_colors()

    if curses.can_change_color():
        curses.init_color(10, 0, 1000, 255)     # bright green
        curses.init_color(11, 0, 400, 100)       # dim green
        curses.init_color(12, 40, 40, 40)         # near-black bg
        curses.init_color(13, 600, 800, 0)        # yellow-green
        curses.init_color(14, 150, 150, 150)      # dark gray
        curses.init_color(15, 1000, 300, 300)     # red
        curses.init_pair(1, 10, 12)   # ON dots
        curses.init_pair(2, 10, -1)   # title/status
        curses.init_pair(3, 11, -1)   # border/dim
        curses.init_pair(4, 13, -1)   # warning/dying
        curses.init_pair(5, 14, 12)   # OFF dots
        curses.init_pair(6, 11, -1)   # help text
        curses.init_pair(7, 15, -1)   # error/red
    else:
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_YELLOW, -1)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_GREEN, -1)
        curses.init_pair(7, curses.COLOR_RED, -1)


def get_system_stats():
    """Gather Pi system stats from /proc and friends."""
    stats = {}

    # CPU temp
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            stats['cpu_temp'] = int(f.read().strip()) / 1000.0
    except (FileNotFoundError, ValueError):
        stats['cpu_temp'] = None

    # Load average
    try:
        with open('/proc/loadavg') as f:
            parts = f.read().split()
            stats['load'] = f"{parts[0]} {parts[1]} {parts[2]}"
            stats['procs'] = parts[3]
    except (FileNotFoundError, IndexError):
        stats['load'] = '?'
        stats['procs'] = '?'

    # Memory
    try:
        with open('/proc/meminfo') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    meminfo[key] = int(val)
            total = meminfo.get('MemTotal', 1)
            avail = meminfo.get('MemAvailable', 0)
            stats['mem_total_mb'] = total // 1024
            stats['mem_used_mb'] = (total - avail) // 1024
            stats['mem_pct'] = round(100 * (total - avail) / total)
    except (FileNotFoundError, KeyError, ZeroDivisionError):
        stats['mem_total_mb'] = 0
        stats['mem_used_mb'] = 0
        stats['mem_pct'] = 0

    # Uptime
    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
            days, rem = divmod(secs, 86400)
            hours, rem = divmod(rem, 3600)
            mins, _ = divmod(rem, 60)
            if days:
                stats['uptime'] = f"{days}d {hours}h {mins}m"
            else:
                stats['uptime'] = f"{hours}h {mins}m"
    except (FileNotFoundError, ValueError):
        stats['uptime'] = '?'

    return stats


def get_usb_devices():
    """Check key USB devices."""
    devices = []
    try:
        # Check for flipdot serial
        if os.path.exists('/dev/ttyUSB0'):
            devices.append(('Flipdot', '/dev/ttyUSB0', True))
        else:
            devices.append(('Flipdot', '/dev/ttyUSB0', False))

        # Check for webcam
        if os.path.exists('/dev/video0'):
            devices.append(('Webcam', '/dev/video0', True))
        else:
            devices.append(('Webcam', '/dev/video0', False))

        # Check for Leap Motion via lsusb-style check
        leap_found = os.path.exists('/dev/bus/usb')
        # Just check if the device node pattern exists
        devices.append(('Leap', 'USB', None))  # can't easily check without lsusb

    except Exception:
        pass

    return devices


def api_call(base_url, path, method='GET', data=None):
    """Make an API call, return parsed JSON or None on error."""
    try:
        url = f"{base_url}{path}"
        if data is not None:
            req = urllib.request.Request(
                url, data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'},
                method=method,
            )
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def draw_box(stdscr, y, x, w, title, color_pair=3):
    """Draw a titled box top border. Returns y+1 for content."""
    stdscr.attron(curses.color_pair(color_pair))
    stdscr.addstr(y, x, f"\u250c\u2500 {title} " + "\u2500" * max(0, w - len(title) - 5) + "\u2510")
    stdscr.attroff(curses.color_pair(color_pair))
    return y + 1


def draw_box_line(stdscr, y, x, w, text, color_pair=3, text_color=2):
    """Draw a line inside a box."""
    stdscr.attron(curses.color_pair(color_pair))
    stdscr.addstr(y, x, "\u2502")
    stdscr.addstr(y, x + w - 1, "\u2502")
    stdscr.attroff(curses.color_pair(color_pair))
    stdscr.attron(curses.color_pair(text_color))
    stdscr.addstr(y, x + 2, text[:w - 4])
    stdscr.attroff(curses.color_pair(text_color))


def draw_box_bottom(stdscr, y, x, w, color_pair=3):
    """Draw box bottom border."""
    stdscr.attron(curses.color_pair(color_pair))
    stdscr.addstr(y, x, "\u2514" + "\u2500" * (w - 2) + "\u2518")
    stdscr.attroff(curses.color_pair(color_pair))


def dashboard(stdscr, host):
    curses.curs_set(0)
    init_colors()

    base_url = f'http://{host}:5000' if ':' not in host else f'http://{host}'
    poll_interval = 0.25
    stdscr.timeout(int(poll_interval * 1000))

    frame_num = 0
    server_ok = False
    server_info = {}
    server_status = {}
    grid = Grid(ROWS, COLS)
    last_sys_check = 0
    sys_stats = {}
    usb_devices = []

    while True:
        now = time.time()

        # Poll display frame from server
        frame_data = api_call(base_url, '/api/display/frame')
        if frame_data:
            server_ok = True
            server_info = frame_data
            grid = Grid.from_display_bytes(bytes(frame_data.get('frame', [0] * 105)))
            frame_num += 1
        else:
            server_ok = False

        # Poll system stats every 2 seconds
        if now - last_sys_check > 2.0:
            sys_stats = get_system_stats()
            usb_devices = get_usb_devices()
            server_status = api_call(base_url, '/api/display/status') or {}
            last_sys_check = now

        # --- Draw ---
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        display_w = COLS * 2 + 4  # 64 chars for display box
        min_w = display_w + 2
        min_h = 22

        if h < min_h or w < min_w:
            stdscr.addstr(0, 0, f"Terminal too small ({w}x{h}). Need {min_w}x{min_h}.")
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                break
            continue

        # Layout: display on top, info panels below
        # If wide enough, put info panels to the right
        wide_mode = w >= display_w + 38
        panel_w = w - display_w - 2 if wide_mode else display_w
        x_off = 1
        y = 0

        # ── Title bar ──
        title = " BIOPUNK FLIPDOT DASHBOARD "
        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(y, x_off, title.center(min(w - 2, display_w)))
        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
        y += 1

        # ── Display mirror ──
        y = draw_box(stdscr, y, x_off, display_w, "DISPLAY", 3)

        for r in range(ROWS):
            stdscr.attron(curses.color_pair(3))
            stdscr.addstr(y + r, x_off, "\u2502")
            stdscr.addstr(y + r, x_off + 1 + COLS * 2, "\u2502")
            stdscr.attroff(curses.color_pair(3))

            for c in range(COLS):
                if grid.get(r, c):
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(y + r, x_off + 1 + c * 2, DOT_ON)
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.attron(curses.color_pair(5))
                    stdscr.addstr(y + r, x_off + 1 + c * 2, DOT_OFF)
                    stdscr.attroff(curses.color_pair(5))

        y += ROWS
        draw_box_bottom(stdscr, y, x_off, display_w)
        y += 1

        # ── Display status line ──
        automaton = server_info.get('automaton') or 'idle'
        alive = grid.count_alive()
        queue = server_info.get('queue_pending', '?')
        playlist = server_info.get('playlist_playing') or 'none'

        status_line = f" CA:{automaton}  dots:{alive}/210  queue:{queue}  playlist:{playlist}"
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(y, x_off, status_line[:display_w].ljust(display_w))
        stdscr.attroff(curses.color_pair(2))
        y += 1

        # ── Side panel or below panel ──
        if wide_mode:
            px = x_off + display_w + 1
            py = 1
        else:
            px = x_off
            py = y + 1

        pw = panel_w if wide_mode else display_w

        # ── Server panel ──
        py = draw_box(stdscr, py, px, pw, "SERVER", 3)
        if server_ok:
            draw_box_line(stdscr, py, px, pw, f"Status: ONLINE  frame:{frame_num}  poll:{poll_interval:.2f}s", text_color=2)
        else:
            draw_box_line(stdscr, py, px, pw, f"Status: OFFLINE  {base_url}", text_color=7)
        py += 1

        connected = server_status.get('connected', False)
        hw_str = "CONNECTED" if connected else "NO HARDWARE"
        draw_box_line(stdscr, py, px, pw, f"Hardware: {hw_str}", text_color=2 if connected else 4)
        py += 1
        draw_box_bottom(stdscr, py, px, pw)
        py += 1

        # ── System panel ──
        py = draw_box(stdscr, py, px, pw, "SYSTEM", 3)

        temp = sys_stats.get('cpu_temp')
        temp_str = f"{temp:.1f}C" if temp else "?"
        temp_color = 7 if temp and temp > 70 else (4 if temp and temp > 55 else 2)
        draw_box_line(stdscr, py, px, pw, f"CPU: {temp_str}  Load: {sys_stats.get('load', '?')}", text_color=temp_color)
        py += 1

        mem_pct = sys_stats.get('mem_pct', 0)
        mem_color = 7 if mem_pct > 85 else (4 if mem_pct > 70 else 2)
        draw_box_line(stdscr, py, px, pw,
                      f"RAM: {sys_stats.get('mem_used_mb', 0)}/{sys_stats.get('mem_total_mb', 0)}MB ({mem_pct}%)",
                      text_color=mem_color)
        py += 1

        draw_box_line(stdscr, py, px, pw, f"Up: {sys_stats.get('uptime', '?')}  Procs: {sys_stats.get('procs', '?')}", text_color=3)
        py += 1
        draw_box_bottom(stdscr, py, px, pw)
        py += 1

        # ── USB devices panel ──
        py = draw_box(stdscr, py, px, pw, "DEVICES", 3)
        for name, path, present in usb_devices:
            if present is None:
                draw_box_line(stdscr, py, px, pw, f"{name:8s} {path}", text_color=3)
            elif present:
                draw_box_line(stdscr, py, px, pw, f"{name:8s} {path} \u2713", text_color=2)
            else:
                draw_box_line(stdscr, py, px, pw, f"{name:8s} {path} \u2717", text_color=7)
            py += 1
        draw_box_bottom(stdscr, py, px, pw)
        py += 1

        # ── Help bar (bottom) ──
        help_y = max(py + 1, h - 3) if not wide_mode else h - 3
        if help_y < h - 1:
            stdscr.attron(curses.color_pair(6))
            stdscr.addstr(help_y, x_off,     " 1:life  2:brain  3:rule30  4:rule90  5:cyclic  0/s:stop ")
            stdscr.addstr(help_y + 1, x_off, " r:restart  +/-:poll speed  q:quit ")
            stdscr.attroff(curses.color_pair(6))

        stdscr.refresh()

        # ── Input ──
        key = stdscr.getch()
        if key in (ord('q'), ord('Q'), 27):
            break
        elif key in CA_KEYS:
            automaton_name, opts = CA_KEYS[key]
            api_call(base_url, '/api/automata/stop', method='POST')
            api_call(base_url, '/api/automata/start', method='POST',
                     data={'automaton': automaton_name, **opts})
        elif key in (ord('0'), ord('s'), ord('S')):
            api_call(base_url, '/api/automata/stop', method='POST')
        elif key == ord('r'):
            # Restart current CA
            current = server_info.get('automaton')
            if current:
                api_call(base_url, '/api/automata/stop', method='POST')
                api_call(base_url, '/api/automata/start', method='POST',
                         data={'automaton': current})
        elif key in (ord('+'), ord('=')):
            poll_interval = max(0.05, poll_interval - 0.05)
            stdscr.timeout(int(poll_interval * 1000))
        elif key in (ord('-'), ord('_')):
            poll_interval = min(5.0, poll_interval + 0.05)
            stdscr.timeout(int(poll_interval * 1000))


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    curses.wrapper(lambda stdscr: dashboard(stdscr, host))


if __name__ == '__main__':
    main()
