# Chapter 13: Deployment — systemd and Production

## Why systemd?

The flipdot display should start when the Pi boots and recover if the process
crashes. That's what systemd does: auto-start, crash recovery, and journal
logging. No cron hacks, no `screen` sessions, no `nohup`.

## Why Gunicorn Over `flask run`?

Flask's built-in server is single-threaded and explicitly warns "Do not use it
in a production deployment." Gunicorn gives us:

- **Worker management** — restart workers that crash
- **Thread pool** — handle concurrent web requests
- **Clean shutdown** — SIGTERM handling for systemd

We use 1 worker with 4 threads because there's one serial port. Multiple
workers would fight over `/dev/ttyUSB0`. The threads handle concurrent web
and API requests within that single worker.

```bash
gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 biopunk:app
```

## The Service File

```ini
[Unit]
Description=Biopunk Flipdot Display Server
After=network.target

[Service]
User=mhough
WorkingDirectory=/home/mhough/biopunk-display
ExecStart=/home/mhough/biopunk-display/.venv/bin/gunicorn \
    -w 1 --threads 4 -b 0.0.0.0:5000 biopunk:app
Restart=always
RestartSec=5
Environment=FLASK_APP=biopunk.py
Environment=SECRET_KEY=change-this-in-production
Environment=FLIPDOT_PORT=/dev/ttyUSB0

[Install]
WantedBy=multi-user.target
```

Line by line:

- **After=network.target** — wait for networking (needed if OpenClaw calls the Claude API)
- **User=mhough** — don't run as root
- **WorkingDirectory** — so relative paths (SQLite DB, playlists) resolve correctly
- **ExecStart** — full path to the venv's gunicorn, not a system-wide install
- **Restart=always** — restart on any exit (crash, OOM kill, etc.)
- **RestartSec=5** — wait 5 seconds before restarting to avoid tight crash loops
- **Environment** — production config; override SECRET_KEY before deploying

## Environment Variables

| Variable | Production Value | Why |
|----------|-----------------|-----|
| `SECRET_KEY` | Random 32+ char string | CSRF/session security |
| `FLIPDOT_PORT` | `/dev/ttyUSB0` | Skip auto-detection on boot |
| `FLIPDOT_BAUD` | `38400` | Display baud rate |
| `WEBHOOK_SECRET` | Random string | HMAC validation for webhooks |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Only if OpenClaw enabled |
| `OPENCLAW_ENABLED` | `true` or `false` | Enable AI agent |

## Installing the Service

```bash
# Copy the service file
sudo cp biopunk-display.service /etc/systemd/system/

# Reload systemd, enable, start
sudo systemctl daemon-reload
sudo systemctl enable biopunk-display
sudo systemctl start biopunk-display

# Check status
sudo systemctl status biopunk-display
```

## Updating the Code

```bash
cd /home/mhough/biopunk-display
git pull
source .venv/bin/activate
pip install -r requirements.txt
flask db upgrade
sudo systemctl restart biopunk-display
```

## Debugging

**Check logs:**
```bash
journalctl -u biopunk-display -f          # follow live
journalctl -u biopunk-display --since today  # today's logs
```

**Serial port permissions:**
```bash
# Add user to dialout group for serial access
sudo usermod -aG dialout mhough
# Verify the port exists
ls -la /dev/ttyUSB0
```

**Common issues:**
- **Port busy** — another process has the serial port. Check with `fuser /dev/ttyUSB0`
- **OOM killed** — the Pi has 4GB; check `journalctl -k` for OOM messages
- **Port 5000 in use** — another service on that port. Check with `ss -tlnp | grep 5000`
- **Permission denied on serial** — user not in dialout group, or udev rules needed

## What's Next

Chapter 14 adds the OpenClaw AI agent — the capstone that gives the display
a mind of its own.
