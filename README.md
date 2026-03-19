# 🧬 Biopunk Flipdot Display

<div align="center">

<img src="docs/biopunk-logo.svg" alt="Biopunk Flipdot Lab" width="600"/>


![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi%204-A22846?style=for-the-badge&logo=raspberrypi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-00ff41?style=for-the-badge)

**A cyberpunk-inspired interactive flipdot display server built as an educational Flask project.**

*Electromagnetic pixels. Real-time input. Biopunk aesthetic.*

```
 ╔══════════════════════════════════════════════════════╗
 ║  ● ○ ● ● ○ ● ●   B I O P U N K   ● ● ○ ● ● ○ ●  ║
 ║  ○ ● ○ ○ ● ○ ○   D I S P L A Y   ○ ○ ● ○ ○ ● ○  ║
 ╚══════════════════════════════════════════════════════╝
```

</div>

---

## 🎯 What Is This?

A **Flask web application** that drives a physical 7×105 electromagnetic flipdot display through multiple input channels — web UI, REST API, voice commands, hand gestures, and webcam presence detection. Every pixel physically flips between black and yellow with a satisfying click.

Built as a **hands-on educational project** following the structure of Miguel Grinberg's [Flask Mega-Tutorial](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world), adapted for hardware hacking and creative coding.

### 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   INPUT SOURCES                      │
│  🌐 Web UI  🎤 Voice  🖐️ Gesture  📷 Webcam  🔌 API │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
        ┌──────▼──────────────────────▼──────┐
        │      ⚡ Priority Message Queue      │
        │      (SQLite + background thread)   │
        └──────────────┬─────────────────────┘
                       │
        ┌──────────────▼─────────────────────┐
        │      🖥️ DisplayManager              │
        │      (thread-safe hardware wrapper) │
        └──────────────┬─────────────────────┘
                       │
        ┌──────────────▼─────────────────────┐
        │   ⬛⬜⬛⬜ Flipdot Display ⬜⬛⬜⬛   │
        │   FTDI Serial · 38400 baud          │
        │   7 rows × 105 cols (30 visible)    │
        └────────────────────────────────────┘
```

---

## 🗺️ Development Roadmap — Flask Mega-Tutorial Chapters

Each chapter builds on the last, turning a bare Flask app into a full interactive display server.

| | Chapter | Topic | What We Build | Status |
|---|---------|-------|---------------|--------|
| 🟢 | **1** | Hello World | Flask app factory + `DisplayManager` wrapper + first route | ✅ Done |
| 🟢 | **2** | Templates | Jinja2 templates with biopunk dark theme | ✅ Done |
| 🟢 | **3** | Web Forms | `Flask-WTF` message form with transition picker | ✅ Done |
| 🟢 | **4** | Database | `Flask-SQLAlchemy` Message model + SQLite persistence | ✅ Done |
| 🟢 | **5** | Message Queue | Priority queue + background scheduler thread | ✅ Done |
| 🟢 | **6** | Bootstrap UI | Bootstrap 5 dark theme, green-on-black biopunk aesthetic | ✅ Done |
| 🟢 | **7** | Voice Input | Vosk offline speech recognition via Blue Yeti mic | ✅ Done |
| 🟢 | **8** | Gesture Input | Leap Motion hand tracking → display commands | ✅ Done |
| 🟢 | **9** | Webcam | OpenCV presence detection via LifeCam HD-3000 | ✅ Done |
| 🟢 | **10** | User Auth | `Flask-Login` for multi-user access control | ✅ Done |
| 🟢 | **11** | REST API | Full CRUD API blueprint (groundwork already in place) | ✅ Done |
| 🟢 | **12** | Playlists | Playlist-as-data: JSON-defined display sequences | ✅ Done |
| 🟢 | **13** | Deployment | `systemd` service, Gunicorn, udev rules, auto-start on boot | ✅ Done |
| 🟢 | **14** | OpenClaw AI | Claude API tool_use agent + autonomous mode | ✅ Done |
| 🟢 | **15** | Generative Art | Cellular automata engine: Life, Wolfram rules, reaction-diffusion | ✅ Done |
| 🟢 | **16** | Data Streams | Live data sources: system stats, weather, ISS tracker, clock | ✅ Done |
| 🟢 | **17** | Workshop Mode | Collaborative display: QR submit, moderation, voting, leaderboard | ✅ Done |

---

## 🖥️ Hardware

| Component | Role | Interface |
|-----------|------|-----------|
| **Raspberry Pi 4B** (4GB) | Server brain | Fedora 42 aarch64 |
| **Flipdot Panel** (7×105) | The display! Electromagnetic pixels | FTDI USB serial `/dev/ttyUSB0` @ 38400 baud |
| **Leap Motion** | Hand gesture input | USB `f182:0003` |
| **Blue Yeti** | Voice commands (offline via Vosk) | USB audio card 3 |
| **LifeCam HD-3000** | Presence detection | `/dev/video0` |

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/m9h/biopunk-display.git
cd biopunk-display

# Install dependencies (using uv)
uv venv
uv pip install -r requirements.txt

# Initialize the database
uv run flask db init
uv run flask db migrate -m "initial"
uv run flask db upgrade

# Run the server
uv run python -c "from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=5000)"
```

Then open **http://localhost:5000** — type a message, pick a transition effect, and watch it flip!

> **Note:** Without the physical flipdot display connected, the app runs in graceful-degradation mode — messages are queued and logged but no serial output is sent.

---

## 📂 Project Structure

```
biopunk-display/
├── app/
│   ├── __init__.py          # App factory — wires everything together
│   ├── models.py            # Message model (SQLAlchemy)
│   ├── main/                # Web UI blueprint
│   │   ├── routes.py        # GET/POST / and /clear
│   │   └── forms.py         # MessageForm (WTForms)
│   ├── api/                 # REST API blueprint
│   │   └── routes.py        # /api/messages, /api/display/*, /api/playlists, /api/openclaw
│   ├── display/             # Hardware abstraction
│   │   ├── manager.py       # Thread-safe DisplayManager
│   │   ├── queue.py         # Priority message queue + worker
│   │   ├── playlist.py      # JSON playlist loader/player (Ch.12)
│   │   ├── automata.py      # Cellular automata engine (Ch.15)
│   │   └── fonts.py         # Double-height 14px font rendering
│   ├── inputs/              # Sensor input modules
│   │   ├── voice.py         # Vosk speech-to-text (Ch.7)
│   │   ├── gesture.py       # Leap Motion gestures (Ch.8)
│   │   ├── webcam.py        # Presence detection (Ch.9)
│   │   └── webhook.py       # External webhook processor
│   ├── generators/          # Generative art engine (Ch.15)
│   │   ├── engine.py        # Plugin-based generator runner
│   │   └── automata.py      # Life, Wolfram, reaction-diffusion, sparks
│   ├── streams/             # Live data streams (Ch.16)
│   │   ├── engine.py        # Stream scheduler + queue integration
│   │   └── sources.py       # System stats, weather, ISS, clock, sensors
│   ├── workshop/            # Collaborative workshop mode (Ch.17)
│   │   ├── routes.py        # QR submit, moderate, vote, leaderboard
│   │   └── models.py        # Submission + Vote models
│   ├── openclaw/            # AI agent layer (Ch.14)
│   │   ├── agent.py         # Claude API tool_use agent
│   │   └── autonomous.py    # Periodic autonomous mode loop
│   └── templates/
│       ├── base.html        # Bootstrap 5 dark biopunk theme
│       ├── index.html       # Dashboard: send messages + history
│       └── workshop/        # Workshop submit, board, moderate, QR views
├── core/
│   └── core.py              # WorkingFlipdotCore — serial comms, char dict
├── transition/
│   └── transition.py        # Transition effects (scroll, dissolve, matrix, etc.)
├── deploy/                  # Deployment files (Ch.13)
│   └── 99-flipdot.rules     # udev rules for stable /dev/flipdot symlink
├── docs/                    # Educational chapter write-ups (Ch.1–17)
├── playlists/               # JSON playlist + CA pattern files
├── tests/                   # pytest suite (285 tests)
├── migrations/              # Flask-Migrate (Alembic) DB migrations
├── dashboard.py             # Curses-based monitoring console
├── config.py                # Flask configuration (env var overrides)
├── biopunk.py               # Entry point (flask run)
├── wsgi.py                  # WSGI entry point (gunicorn)
├── deploy.sh                # Automated deployment script
├── biopunk-display.service  # systemd unit file
├── .env.example             # Environment variable reference
├── requirements.txt         # Python dependencies
└── .flaskenv                # Flask environment vars
```

---

## 🎨 Transition Effects

The flipdot display supports multiple transition animations:

| Effect | Description |
|--------|-------------|
| `righttoleft` | Classic scrolling text |
| `typewriter` | Character-by-character reveal |
| `matrix_effect` | Matrix-style rain |
| `dissolve` | Random pixel dissolve |
| `magichat` | Magic hat reveal |
| `pop` | Pop-in animation |
| `bounce` | Bouncing entrance |
| `slide_in_left` | Slide from left |
| `amdissolve` | Alternating dissolve |

---

## 🔌 API Examples

```bash
# Send a message
curl -X POST http://localhost:5000/api/messages \
  -H "Content-Type: application/json" \
  -d '{"body": "HELLO WORLD", "transition": "typewriter"}'

# List messages
curl http://localhost:5000/api/messages

# Check display status
curl http://localhost:5000/api/display/status

# Clear display
curl -X POST http://localhost:5000/api/display/clear
```

---

## 🧪 Built With

- **[Flask](https://flask.palletsprojects.com/)** — lightweight Python web framework
- **[Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)** — ORM for message persistence
- **[Flask-Migrate](https://flask-migrate.readthedocs.io/)** — Alembic database migrations
- **[Flask-WTF](https://flask-wtf.readthedocs.io/)** — form handling & CSRF protection
- **[Bootstrap 5](https://getbootstrap.com/)** — responsive dark theme UI
- **[pyserial](https://pyserial.readthedocs.io/)** — FTDI serial communication

---

## History

This display has lived several lives. Each unit/module/panel is 5 dots wide and 7 high.

**SXSW — Pepsico Display.** The display was originally configured as a 16ft, 29-panel,
145-column horizontal display at SXSW for Pepsico. The original wiring harness is wired
for this single long row.

**NAMII Booth (Jun 10-12, 2013).** Reconfigured into a 12ft, 21-panel, 105-column
vertical display plus a 4ft, 6-panel, 30-column vertical display. The codebase was
adapted for two separate controllers and two USB-to-serial devices. Most of the
original transitions and video playback code were designed for this vertical layout.

**Burning Man 2018 — Benderbot.** Mickey and Zen reconfigured the display into a curved
panel (2 units high by 6 units wide) fitted into the rear window of Mick's 1950 Flying
Cloud airstream. The playlist was a set of animated eyes with different expressions.

**Biopunk Lab (2025-present).** Now running as a 7-row by 30-column visible display
on a Raspberry Pi 4, driven by this Flask application.

---

## Serial Protocol Reference

This section documents the low-level serial protocol for programming the flipdot
controller directly. The Flask app abstracts all of this behind `DisplayManager` and
`WorkingFlipdotCore`, but understanding the protocol is essential for debugging and
writing new transition effects.

### Panel Layout

Each panel is 5 dots wide and 7 high. Columns are addressed with bytes between
`0x00` and `0x7f` (7 bits for 7 rows). Columns are addressed from the bottom up:

```
0x40  .  row 6 (top)
0x20  .  row 5
0x10  .  row 4
0x08  .  row 3
0x04  .  row 2
0x02  .  row 1
0x01  O  row 0 (bottom)      ← 0x01 lights this dot
```

### Fill Messages

Every time a data byte (`< 0x80`) is sent, the controller writes it to the current
column and auto-increments the cursor. To fill 5 columns solid white:

```python
ser.write(b'\x7f\x7f\x7f\x7f\x7f')
```

### Control Messages

Any byte `>= 0x81` is a control message:

- **First control byte = column set.** `0x81` = column 0, `0x82` = column 1, etc.
- **Second control byte = row set.** `0x81` = row 0, `0x82` = row 1.

To position the cursor at row 0, column 0: send `0x81 0x81`.
To position at row 1, column 0: send `0x81 0x82`.

### Row Break

The controller's first row has 75 addressable columns; the second has 70. When
filling the full 105-column buffer, you must reset at column 75:

```python
TCOLUMN = 105
ROW_BREAK = 75
reset = b'\x81'
row1 = b'\x81'
row2 = b'\x82'

def fill(message, fillmask=127):
    ser.write(reset + row1)
    for i in range(len(message)):
        if i == ROW_BREAK:
            ser.write(reset + row2)
        ser.write(bytes([message[i] & fillmask]))
```

### USB-to-Serial

The display uses FTDI USB serial adapters. On Linux (Raspberry Pi): `/dev/ttyUSB0`
at 38400 baud. On macOS: requires the
[FTDI VCP driver](http://www.ftdichip.com/Drivers/VCP.htm), device appears as
`/dev/tty.usbserial-*`.

### Display Constants

```python
TROW = 7          # Rows in the display
TCOLUMN = 105     # Total addressable columns
ROW_BREAK = 75    # Column where row 2 begins
BITMASK = [1, 2, 4, 8, 0x10, 0x20, 0x40]  # Bit per row (bottom to top)
```

---

<div align="center">

```
⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜
⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛
```

*Every pixel clicks. Every message matters.*

**[m9h](https://github.com/m9h)** · Raspberry Pi 4 · Fedora 42 · Flask Mega-Tutorial

</div>
