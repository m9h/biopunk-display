# 🧬 Biopunk Flipdot Display

<div align="center">

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
| 🟡 | **7** | Voice Input | Vosk offline speech recognition via Blue Yeti mic | 🔜 Next |
| ⚪ | **8** | Gesture Input | Leap Motion hand tracking → display commands | ⬚ Planned |
| ⚪ | **9** | Webcam | OpenCV presence detection via LifeCam HD-3000 | ⬚ Planned |
| ⚪ | **10** | User Auth | `Flask-Login` for multi-user access control | ⬚ Planned |
| ⚪ | **11** | REST API | Full CRUD API blueprint (groundwork already in place) | ⬚ Planned |
| ⚪ | **12** | Playlists | Playlist-as-data: JSON-defined display sequences | ⬚ Planned |
| ⚪ | **13** | Deployment | `systemd` service, auto-start on boot | ⬚ Planned |
| 🔮 | **14** | OpenClaw AI | AI agent integration — dynamic content, NLP voice, webcam reactions | ⬚ Capstone |

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

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize the database
flask db init
flask db migrate -m "initial"
flask db upgrade

# Run the server
flask run
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
│   │   ├── __init__.py
│   │   ├── routes.py        # GET/POST / and /clear
│   │   └── forms.py         # MessageForm (WTForms)
│   ├── api/                 # REST API blueprint
│   │   ├── __init__.py
│   │   └── routes.py        # /api/messages, /api/display/*
│   ├── display/             # Hardware abstraction
│   │   ├── __init__.py
│   │   ├── manager.py       # Thread-safe DisplayManager
│   │   └── queue.py         # Priority message queue + worker
│   └── templates/
│       ├── base.html        # Bootstrap 5 dark biopunk theme
│       └── index.html       # Dashboard: send messages + history
├── config.py                # Flask configuration
├── biopunk.py               # Entry point (flask run)
├── requirements.txt         # Python dependencies
├── .flaskenv                # Flask environment vars
└── CLAUDE.md                # Full project plan & architecture notes
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

<div align="center">

```
⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜
⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛⬜⬛
```

*Every pixel clicks. Every message matters.*

**[m9h](https://github.com/m9h)** · Raspberry Pi 4 · Fedora 42 · Flask Mega-Tutorial

</div>
