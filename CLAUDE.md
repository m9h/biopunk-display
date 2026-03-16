# Biopunk Flipdot Display - Project Context

## Hardware (Raspberry Pi 4 Model B, 4GB RAM, Fedora 42 aarch64)
- **Flipdot display**: FTDI serial at `/dev/ttyUSB0`, 38400 baud, 7x105 columns (30-col visible, wraps at col 75)
- **Leap Motion Controller**: USB `f182:0003` — gesture input
- **Blue Yeti Microphone**: USB audio card 3 — voice input via Vosk (offline)
- **Microsoft LifeCam HD-3000**: `/dev/video0` — webcam/presence detection
- **Keyboard + Mouse**: standard USB HID

## Project Plan: Biopunk Lab Interactive Server

We are rebuilding this flipdot display system as a **Flask Mega-Tutorial style educational project**.
Target repo: `github.com/m9h/biopunk-display`

### Architecture: Hybrid Flask + OpenClaw
- **Flask app is the reliable core** — always runs, serves web UI, manages queue/scheduler, works offline
- **OpenClaw (optional layer)** — AI agent that can compose dynamic messages, react to webcam, handle complex NLP voice commands via Flask API
- All inputs (web, voice, gesture, webcam, webhook, OpenClaw) feed the same priority message queue

### Structure
```
biopunk-display/
  docs/                    # Educational blog chapters (chapter-01 through chapter-27)
  app/                     # Flask app factory
    __init__.py, models.py
    main/                  # Web UI blueprint (routes, forms, templates)
    api/                   # REST API blueprint
    display/               # DisplayManager, transitions, fonts, scheduler
    inputs/                # voice.py, gesture.py, webcam.py, webhook.py
    templates/, static/
  openclaw/                # OpenClaw integration (system-prompt, MCP tools)
  hardware/                # Wiring docs, serial protocol
  config.py, biopunk.py, requirements.txt, migrations/, tests/
```

### Build Order
1. Flask app factory + display wrapper + first route (Chapter 1)
2. Jinja2 templates (Chapter 2)
3. Web forms with Flask-WTF (Chapter 3)
4. SQLite database with Flask-SQLAlchemy (Chapter 4)
5. Message queue + background scheduler (Chapter 5)
6. Bootstrap UI (Chapter 6)
7. Voice input via Vosk + Blue Yeti (Chapter 7)
8. Gesture input via Leap Motion (Chapter 8)
9. Webcam presence detection (Chapter 9)
10. User auth with Flask-Login (Chapter 10)
11. REST API blueprint (Chapter 11)
12. Playlist-as-data (JSON files) (Chapter 12)
13. Deployment: systemd service, auto-start (Chapter 13)
14. OpenClaw integration (Chapter 14, capstone)

### Key Dependencies
flask, flask-sqlalchemy, flask-migrate, flask-login, flask-wtf, bootstrap-flask,
flask-moment, python-dotenv, vosk, sounddevice, opencv-python-headless, pyserial, Pillow

### Existing Working Code (in this repo)
- `core/core.py` — WorkingFlipdotCore class, character dict, serial comms, fill/scroll/transition primitives
- `transition/transition.py` — transition effects (righttoleft, magichat, pop, dissolve, matrix, typewriter, etc.)
- `video/video.py` — video frame playback from PNG sequences
- Display constants: TROW=7, TCOLUMN=105, ROW_BREAK=75, BITMASK=[1,2,4,8,0x10,0x20,0x40]

### GitHub
- Org: m9h
- Need to: install gh (`sudo dnf install -y gh`), authenticate (`gh auth login`), create repo

### User
- Primary account on this Pi: `mhough` (uid 1000, wheel group)
- Development account: `flipdots` (where original code lives)
