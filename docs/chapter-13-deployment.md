# Chapter 13: Deployment — systemd, Production WSGI, and the Headless Pi

## From Laptop to Lab

Up to this point, every chapter has ended with `flask run`. That works beautifully
for development: instant reloads, verbose tracebacks, a debugger you can poke at
in the browser. But `flask run` is not how you ship software. The built-in Werkzeug
server is single-threaded, has no process supervision, and prints a warning every
time you start it: *"Do not use it in a production deployment."*

The flipdot display lives in a university lab. Nobody is going to SSH in and type
`flask run` every morning. The system needs to:

1. **Start automatically** when the Pi boots
2. **Restart itself** if the process crashes
3. **Log everything** so you can debug problems after the fact
4. **Protect its serial port** so only the right user can talk to the display
5. **Serve web traffic reliably** behind a production-grade WSGI server

This chapter makes all of that happen.

## Why systemd?

If you've administered a Linux server, you've probably encountered several
approaches to keeping a process alive. Here's why systemd wins for our case.

### The alternatives, and why they fall short

**cron with `@reboot`** starts your process once at boot. That's it. If it
crashes at 3 PM, it stays dead until the next reboot. You could write a cron
job that checks every minute and restarts it, but now you've built a fragile,
ad-hoc process manager with no logging.

**GNU Screen or tmux** keeps a terminal session alive, which is great for
interactive development. But it requires someone to log in and create the
session. If the Pi loses power and reboots, the screen session is gone.

**supervisord** is a legitimate process manager, and plenty of projects use it
well. But on Fedora 42 (and every other modern Linux distribution), systemd is
already running. It's PID 1. Adding supervisord means running a process manager
inside a process manager. That's not wrong, but it's unnecessary complexity.

**systemd gives us all of this for free:**

| Feature | systemd | cron | screen | supervisord |
|---------|---------|------|--------|-------------|
| Auto-start on boot | Yes | `@reboot` only | No | Yes (if enabled) |
| Restart on crash | Configurable policy | No | No | Yes |
| Dependency ordering | `After=`, `Requires=` | No | No | Priority numbers |
| Structured logging | journald | Redirect to file | scrollback buffer | Log files |
| Resource limits | `MemoryMax=`, `CPUQuota=` | No | No | No |
| Socket activation | Yes | No | No | No |
| Already installed | Yes (PID 1) | Yes | Usually | No (extra package) |

The bottom line: systemd is already there, it's battle-tested, and it provides
exactly the reliability guarantees we need.

## Choosing a Production WSGI Server

Flask's built-in server uses Werkzeug, which is designed for development. For
production, we need a proper WSGI server. The two main contenders are:

**Gunicorn** (Green Unicorn) is the most popular choice in the Python ecosystem.
It uses a pre-fork worker model: a master process spawns worker processes, each
handling requests independently. If a worker dies, the master replaces it.

**Waitress** is a pure-Python alternative that works on all platforms (including
Windows, if that matters). It's simpler but less configurable.

We'll use **Gunicorn** because it gives us fine-grained control over workers and
threads, handles signals cleanly for systemd integration, and is the standard
recommendation in the Flask documentation.

### Why 1 worker, 4 threads?

This is the critical architectural decision for our project, and it comes down
to the serial port.

The flipdot display connects via a single FTDI serial port at `/dev/ttyUSB0`.
Serial communication is inherently sequential: one byte at a time, 38400 baud.
If we ran multiple Gunicorn workers (separate processes), each would get its own
copy of the `DisplayManager`, and they'd fight over the serial port. Bytes from
different messages would interleave. The display would show garbage.

One worker process means one `DisplayManager`, one serial connection, one lock.
But we still need concurrency for the web interface and API. That's what threads
give us: within the single worker, 4 threads can handle HTTP requests in
parallel, while the `threading.Lock` in `DisplayManager` serializes actual
hardware access.

```bash
# The production command
gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 biopunk:app
```

- **`-w 1`** -- one worker process (serial port safety)
- **`--threads 4`** -- four threads per worker (web concurrency)
- **`-b 0.0.0.0:5000`** -- bind to all interfaces on port 5000
- **`biopunk:app`** -- the module:variable pointing to our Flask application

### Installing Gunicorn

Gunicorn isn't in `requirements.txt` because it's a deployment dependency, not
an application dependency. The app doesn't import it. You install it into the
virtual environment on the Pi:

```bash
source /home/mhough/biopunk-display/.venv/bin/activate
pip install gunicorn
```

Or, if you're using the `deploy.sh` script (more on that later), it handles this
automatically.

## The systemd Unit File

Here's the complete unit file. We'll walk through every line.

```ini
[Unit]
Description=Biopunk Flipdot Display Server
After=network.target
Wants=network.target

[Service]
Type=notify
User=mhough
Group=mhough
WorkingDirectory=/home/mhough/biopunk-display

ExecStart=/home/mhough/biopunk-display/.venv/bin/gunicorn \
    -w 1 \
    --threads 4 \
    -b 0.0.0.0:5000 \
    biopunk:app

Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5

EnvironmentFile=/home/mhough/biopunk-display/.env

StandardOutput=journal
StandardError=journal
SyslogIdentifier=biopunk

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/mhough/biopunk-display
ProtectHome=read-only
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Section by section

**`[Unit]`** describes the service and its dependencies.

- **`After=network.target`** -- don't start until networking is up. This matters
  if OpenClaw needs to call the Claude API, or if someone configures a remote
  database. It also ensures DNS resolution works for any outbound requests.
- **`Wants=network.target`** -- a soft dependency. If networking fails to start,
  our service starts anyway (the display and local features work fine offline).
  Use `Requires=` instead if you need a hard dependency.

**`[Service]`** defines how the process runs.

- **`Type=notify`** -- Gunicorn supports the systemd notification protocol. It
  tells systemd "I'm ready" after workers are forked and listening. This means
  `systemctl start` won't return success until the server is actually accepting
  connections. (Note: this requires the `--preload` flag or Gunicorn 20.1+ which
  supports notify by default. If you see issues, fall back to `Type=exec`.)
- **`User=mhough`** and **`Group=mhough`** -- run as a regular user, never as
  root. The `mhough` account is uid 1000, in the `wheel` group for sudo, and
  (crucially) in the `dialout` group for serial port access.
- **`WorkingDirectory`** -- sets the current directory before executing. This
  is essential because our app uses relative paths for the SQLite database
  (`app.db` or `biopunk.db`), playlist JSON files, and the Vosk speech model.
- **`ExecStart`** -- the full, absolute path to the venv's Gunicorn. Never rely
  on `PATH` in a systemd unit. The venv is not "activated" in the shell sense;
  we just call its Python/Gunicorn binaries directly, which automatically use
  the venv's `site-packages`.

**Restart policy:**

- **`Restart=on-failure`** -- restart if the process exits with a non-zero code,
  is killed by a signal (SIGSEGV, OOM killer), or times out. We use `on-failure`
  rather than `always` because `always` would also restart on clean exit
  (`systemctl stop`), causing a brief zombie resurrection before systemd
  realizes you meant to stop it. With `on-failure`, a clean stop stays stopped.
- **`RestartSec=5`** -- wait 5 seconds before restarting. This prevents a tight
  crash loop: if the serial port is unplugged, restarting immediately every time
  would flood the journal with thousands of identical error messages.
- **`StartLimitIntervalSec=300`** and **`StartLimitBurst=5`** -- if the service
  crashes more than 5 times within 300 seconds (5 minutes), systemd stops trying.
  This prevents infinite restart loops. You can manually restart with
  `systemctl reset-failed biopunk-display && systemctl start biopunk-display`
  after fixing the underlying problem.

**`[Install]`** controls `systemctl enable`.

- **`WantedBy=multi-user.target`** -- start this service when the system reaches
  multi-user mode (the normal boot target for a headless server). This is how
  `systemctl enable` works: it creates a symlink in
  `/etc/systemd/system/multi-user.target.wants/`.

### Security hardening

The unit file includes several security directives that are worth understanding:

- **`NoNewPrivileges=true`** -- the process cannot gain new privileges through
  setuid binaries or other mechanisms. Since we run as a regular user and never
  need root, this is pure defense-in-depth.
- **`ProtectSystem=strict`** -- mounts `/usr`, `/boot`, and `/etc` as read-only.
  Our Flask app has no business writing to system directories.
- **`ReadWritePaths=/home/mhough/biopunk-display`** -- the exception to
  `ProtectSystem`. We need write access to our project directory for the SQLite
  database, uploaded playlists, and log files.
- **`ProtectHome=read-only`** -- the home directory is readable (we need to read
  our code) but not writable outside the explicit `ReadWritePaths`.
- **`PrivateTmp=true`** -- gives the service its own `/tmp` directory, isolated
  from other processes. Prevents a whole class of symlink-based attacks.

## Environment Variables and Secrets

### The problem with inline `Environment=`

You might be tempted to put secrets directly in the unit file:

```ini
# DON'T DO THIS
Environment=SECRET_KEY=my-super-secret-key-12345
```

The unit file lives in `/etc/systemd/system/` and is world-readable. Anyone who
can log into the Pi can read your secrets. Worse, if you check the unit file
into git (as a template), your secrets end up in version control.

### The solution: EnvironmentFile

systemd's `EnvironmentFile` directive reads key-value pairs from a file:

```ini
EnvironmentFile=/home/mhough/biopunk-display/.env
```

Create the `.env` file with restrictive permissions:

```bash
# Generate a proper secret key
python3 -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" > /home/mhough/biopunk-display/.env

# Add the rest of the configuration
cat >> /home/mhough/biopunk-display/.env << 'EOF'
FLASK_APP=biopunk.py
FLIPDOT_PORT=/dev/ttyUSB0
FLIPDOT_BAUD=38400
WEBHOOK_SECRET=your-webhook-secret-here
OPENCLAW_ENABLED=false
# ANTHROPIC_API_KEY=sk-ant-...  # Uncomment if using OpenClaw
EOF

# Lock down permissions: owner read/write only
chmod 600 /home/mhough/biopunk-display/.env
```

Now only `mhough` can read the secrets, and `.env` is in `.gitignore` so it
never gets committed.

### Full environment variable reference

Here's every environment variable the application recognizes, with production
recommendations:

| Variable | Default | Production Recommendation |
|----------|---------|--------------------------|
| `SECRET_KEY` | `biopunk-flipdot-dev-key` | **Must change.** `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `sqlite:///app.db` | Keep SQLite for this project; no need for Postgres on a Pi |
| `FLIPDOT_PORT` | Auto-detect | Set to `/dev/ttyUSB0` explicitly (auto-detect is slow on boot) |
| `FLIPDOT_BAUD` | `38400` | Keep default (matches display hardware) |
| `VOSK_MODEL_PATH` | `./vosk-model` | Absolute path: `/home/mhough/biopunk-display/vosk-model` |
| `VOSK_DEVICE` | Default mic | Set if multiple audio devices present |
| `WEBCAM_DEVICE` | `0` | Keep default (`/dev/video0`) |
| `WEBCAM_MOTION_THRESHOLD` | `5000` | Tune for your environment's lighting |
| `WEBCAM_COOLDOWN` | `30` | Seconds between greetings |
| `WEBHOOK_SECRET` | None | Random string for HMAC validation |
| `PLAYLIST_DIR` | `./playlists` | Absolute path recommended |
| `ANTHROPIC_API_KEY` | None | Only needed if `OPENCLAW_ENABLED=true` |
| `OPENCLAW_ENABLED` | `false` | Set `true` to enable AI agent |
| `OPENCLAW_MODEL` | `claude-sonnet-4-6` | Override for different model |
| `OPENCLAW_INTERVAL` | `300` | Seconds between autonomous AI cycles |

Note that `python-dotenv` (listed in `requirements.txt`) also reads `.env` when
using `flask run` in development. So the same file serves both development and
production, just with different values.

## Serial Port Permissions

The flipdot display communicates over an FTDI USB-to-serial adapter that appears
as `/dev/ttyUSB0`. By default, serial ports on Linux are owned by `root:dialout`
with permissions `crw-rw----`. Only root and members of the `dialout` group can
open them.

### Step 1: Add your user to the dialout group

```bash
sudo usermod -aG dialout mhough
```

**Important:** Group changes don't take effect in existing sessions. You must
log out and back in, or reboot. To verify:

```bash
groups mhough
# Should include: dialout
```

### Step 2: Create a udev rule for predictable naming

USB devices can enumerate in different order depending on boot timing. The FTDI
adapter is usually `/dev/ttyUSB0`, but if you plug in another USB-serial device
first, it might become `/dev/ttyUSB1`. A udev rule creates a stable symlink.

Create `/etc/udev/rules.d/99-flipdot.rules`:

```
# FTDI USB-Serial adapter for flipdot display
# Find your values with: udevadm info -a -n /dev/ttyUSB0 | grep -E 'idVendor|idProduct|serial'
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", \
    SYMLINK+="flipdot", MODE="0660", GROUP="dialout"
```

This rule does three things:

1. **`SYMLINK+="flipdot"`** -- creates `/dev/flipdot` as a stable symlink to
   whatever `/dev/ttyUSBn` the adapter gets assigned. Update your `.env` to use
   `FLIPDOT_PORT=/dev/flipdot` and the port never moves.
2. **`MODE="0660"`** -- read/write for owner and group.
3. **`GROUP="dialout"`** -- ensures the dialout group owns the device.

Reload udev rules without rebooting:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
ls -la /dev/flipdot   # Should point to ttyUSB0
```

### Finding your device's vendor and product IDs

The values `0403:6001` are standard for FTDI FT232R chips, which are the most
common USB-serial adapters. If your adapter uses a different chip, find the
correct IDs:

```bash
udevadm info -a -n /dev/ttyUSB0 | grep -E 'idVendor|idProduct'
```

Or simply:

```bash
lsusb | grep -i serial
```

## Installing and Managing the Service

### Initial installation

The project includes a `biopunk-display.service` file in the repository root.
Copy it to systemd's directory and activate it:

```bash
# Copy the unit file
sudo cp /home/mhough/biopunk-display/biopunk-display.service /etc/systemd/system/

# Tell systemd to re-read its configuration
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable biopunk-display

# Start the service now
sudo systemctl start biopunk-display
```

**What `enable` actually does:** it creates a symlink:

```
/etc/systemd/system/multi-user.target.wants/biopunk-display.service
  -> /etc/systemd/system/biopunk-display.service
```

When the system reaches `multi-user.target` during boot, systemd follows these
symlinks and starts everything that's "wanted."

### Checking status

```bash
sudo systemctl status biopunk-display
```

A healthy service looks like this:

```
● biopunk-display.service - Biopunk Flipdot Display Server
     Loaded: loaded (/etc/systemd/system/biopunk-display.service; enabled)
     Active: active (running) since Tue 2026-03-18 09:15:32 EDT; 2h ago
   Main PID: 1234 (gunicorn)
      Tasks: 5 (limit: 4531)
     Memory: 87.3M
        CPU: 1min 23.456s
     CGroup: /system.slice/biopunk-display.service
             ├─1234 /home/mhough/biopunk-display/.venv/bin/python /home/...gunicorn
             └─1235 /home/mhough/biopunk-display/.venv/bin/python /home/...gunicorn
```

Key things to look for:
- **`enabled`** means it will start on boot
- **`active (running)`** means it's currently running
- **Memory** should be under 200MB for our app (the Pi has 4GB)
- **Tasks** should be around 5-10 (1 master + threads + input threads)

### The deploy script

The repository includes `deploy.sh`, a convenience script that automates the
full update cycle. It handles virtual environment creation, dependency
installation, database migrations, and service restart:

```bash
cd /home/mhough/biopunk-display
./deploy.sh
```

The script uses user-level systemd (`systemctl --user`) with `loginctl
enable-linger` so the service runs even when `mhough` is not logged in. This
is an alternative to the system-level unit file approach described above. Either
approach works; the system-level approach is more traditional for server
deployments, while user-level is more convenient for single-user Pi setups where
you want to avoid `sudo`.

## Log Management with journalctl

systemd captures all stdout and stderr from your service and stores it in the
binary journal. No log rotation configuration needed -- journald handles it
automatically.

### Essential journalctl commands

```bash
# Follow logs in real time (like tail -f)
journalctl -u biopunk-display -f

# Today's logs only
journalctl -u biopunk-display --since today

# Logs from the last hour
journalctl -u biopunk-display --since "1 hour ago"

# Logs from a specific time window (great for debugging "it broke at 3 PM")
journalctl -u biopunk-display --since "2026-03-18 15:00" --until "2026-03-18 16:00"

# Last 50 lines
journalctl -u biopunk-display -n 50

# Only errors and above
journalctl -u biopunk-display -p err

# Show the previous boot's logs (if the Pi rebooted and the problem is gone)
journalctl -u biopunk-display -b -1

# Output as JSON for programmatic parsing
journalctl -u biopunk-display -o json --since today
```

### What appears in the journal

Gunicorn logs its own lifecycle events (worker boot, requests, errors) to
stderr, which journald captures. Flask's `app.logger` also writes to stderr by
default. So you'll see:

- Gunicorn master/worker startup messages
- HTTP request logs (method, path, status code, response time)
- Python exceptions with full tracebacks
- Our custom log messages from input modules ("Voice recognized: HELLO",
  "Webcam: presence detected", etc.)

### Journal storage limits

On Fedora 42, journald defaults to keeping logs until they fill 10% of the
filesystem or 4GB, whichever is smaller. On a Pi with a 32GB SD card, that's
about 3.2GB -- more than enough. You can check usage with:

```bash
journalctl --disk-usage
```

If you need to reclaim space:

```bash
# Keep only the last 7 days
sudo journalctl --vacuum-time=7d

# Or keep only the last 500MB
sudo journalctl --vacuum-size=500M
```

## Firewall Configuration

Fedora 42 ships with `firewalld` enabled by default. This means the Pi's
network ports are closed unless explicitly opened. If you try to access
`http://your-pi:5000` from another machine and get a connection timeout (not
a refused connection -- a *timeout*), the firewall is blocking it.

### Opening port 5000 directly

The simplest approach for a lab environment:

```bash
# Open port 5000 for TCP traffic, permanently
sudo firewall-cmd --permanent --add-port=5000/tcp

# Reload to apply
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
# Output: 5000/tcp
```

**`--permanent`** makes the rule survive reboots. Without it, the rule applies
only until the next reboot or `firewall-cmd --reload`.

### A note on network security

Port 5000 in a university lab environment is generally fine -- you're on an
internal network behind the institution's firewall. But if the Pi is directly
internet-accessible (unlikely but possible), you should use a reverse proxy
with TLS instead of exposing Gunicorn directly. See the nginx section below.

## Optional: nginx as a Reverse Proxy

For a lab deployment, Gunicorn directly on port 5000 is perfectly adequate. But
if you want to add TLS (HTTPS), serve static files more efficiently, or run on
port 80/443 without running Gunicorn as root, nginx is the standard solution.

### Why a reverse proxy?

- **Static files**: nginx serves CSS, JavaScript, and images directly from disk
  without involving Python. For our small app this barely matters, but it's good
  practice.
- **TLS termination**: nginx handles HTTPS, and Gunicorn sees plain HTTP
  internally. No need to configure certificates in Python.
- **Port 80/443**: Gunicorn running as `mhough` can't bind to ports below 1024.
  nginx runs as root (briefly) to grab the port, then drops privileges.
- **Connection buffering**: nginx buffers slow client connections, freeing
  Gunicorn threads to handle other requests.

### Installation and configuration

```bash
sudo dnf install -y nginx
```

Create `/etc/nginx/conf.d/biopunk.conf`:

```nginx
server {
    listen 80;
    server_name _;   # Accept any hostname

    # Serve static files directly
    location /static/ {
        alias /home/mhough/biopunk-display/app/static/;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy everything else to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if we add live updates later)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable and start nginx:

```bash
# Remove the default welcome page
sudo rm -f /etc/nginx/conf.d/default.conf

# Test the configuration
sudo nginx -t

# Start nginx
sudo systemctl enable --now nginx

# Open port 80 in the firewall (instead of 5000)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

When using a reverse proxy, change Gunicorn to bind to localhost only:

```ini
# In the systemd unit file, change:
ExecStart=/home/mhough/biopunk-display/.venv/bin/gunicorn \
    -w 1 \
    --threads 4 \
    -b 127.0.0.1:5000 \
    biopunk:app
```

This ensures Gunicorn only accepts connections from nginx, not from the network
directly.

### nginx and SELinux on Fedora

Fedora enables SELinux by default. If nginx can't connect to Gunicorn, it's
likely an SELinux policy issue:

```bash
# Check for SELinux denials
sudo ausearch -m AVC --ts recent

# Allow nginx to make network connections to local services
sudo setsebool -P httpd_can_network_connect 1
```

The `httpd_can_network_connect` boolean is the most common SELinux fix for
reverse proxy setups on Fedora.

## Health Checks and Monitoring

A running service is not necessarily a *healthy* service. The process might be
alive but the serial port disconnected, or the message queue thread might have
crashed.

### systemd watchdog (basic)

systemd can periodically check that a service is still responding. Gunicorn
doesn't natively support the systemd watchdog protocol at the application level,
but you can add a simple HTTP health check using `ExecStartPost` and a timer:

Create a health-check script at `/home/mhough/biopunk-display/healthcheck.sh`:

Actually, a simpler approach: just use the API endpoint we already built. Our
REST API (Chapter 11) exposes system status. If you have a `/api/status`
endpoint, you can monitor it with a systemd timer or a simple cron job.

### HTTP health check with curl

```bash
# Quick health check from the command line
curl -sf http://localhost:5000/api/status || echo "UNHEALTHY"
```

### Monitoring with a systemd timer

Create two files for a periodic health check.

`/etc/systemd/system/biopunk-healthcheck.service`:
```ini
[Unit]
Description=Biopunk health check

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -sf --max-time 10 http://localhost:5000/api/status
```

`/etc/systemd/system/biopunk-healthcheck.timer`:
```ini
[Unit]
Description=Run biopunk health check every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now biopunk-healthcheck.timer
```

If the health check fails, you'll see it in the journal:

```bash
journalctl -u biopunk-healthcheck --since today
```

### Monitoring serial port connectivity

The FTDI adapter can be unplugged (accidentally or by a curious student). When
that happens, `/dev/ttyUSB0` disappears, and the `DisplayManager` will fail on
the next write. The app handles this gracefully -- it logs an error and continues
serving the web UI -- but you should know about it.

```bash
# Check if the serial port exists
ls /dev/ttyUSB0 2>/dev/null && echo "OK" || echo "MISSING"

# Check if the symlink from our udev rule works
ls -la /dev/flipdot

# Check who's using the serial port
fuser /dev/ttyUSB0
```

### Checking Pi resources

The Raspberry Pi 4 has 4GB of RAM. Our app typically uses 80-150MB, leaving
plenty of headroom. But if the Vosk speech model is large, or if OpenCV is
processing webcam frames, memory usage can climb.

```bash
# Memory usage of the service
systemctl status biopunk-display | grep Memory

# Detailed process info
ps aux | grep gunicorn

# Overall system resources
free -h
df -h /     # SD card space
vcgencmd measure_temp  # CPU temperature (RPi-specific)
```

The Pi 4 can thermal-throttle under sustained load. In a lab environment, make
sure it has adequate ventilation. If the CPU temperature consistently exceeds
80 degrees C, consider a heatsink or fan.

## Updating and Redeploying

When you push new code to the repository, updating the Pi is straightforward.

### Manual update

```bash
cd /home/mhough/biopunk-display

# Pull the latest code
git pull

# Activate the venv and update dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Run any new database migrations
flask db upgrade

# Restart the service to pick up code changes
sudo systemctl restart biopunk-display

# Verify it came back up cleanly
sudo systemctl status biopunk-display
journalctl -u biopunk-display -n 20
```

### Using the deploy script

The `deploy.sh` script in the repository root automates this entire sequence.
It also handles first-time setup (creating the virtual environment, installing
Gunicorn):

```bash
cd /home/mhough/biopunk-display
./deploy.sh
```

### Zero-downtime considerations

For a flipdot display, "downtime" means the web UI is unreachable for a few
seconds during restart. The display itself holds its last state (the dots stay
flipped), so there's no visible disruption. A `systemctl restart` is fine.

If you ever need true zero-downtime deployment (unlikely for a lab display, but
good to know), Gunicorn supports graceful reload:

```bash
# Graceful reload: finish current requests, then load new code
sudo systemctl reload biopunk-display
```

For this to work, add a `ExecReload` directive to the unit file:

```ini
ExecReload=/bin/kill -s HUP $MAINPID
```

Sending `SIGHUP` to the Gunicorn master tells it to gracefully restart workers
with the new code while keeping the listening socket open.

## Putting It All Together

Here's the complete deployment checklist, from a fresh Fedora 42 installation
on a Raspberry Pi 4 to a running, auto-starting display server.

```bash
# 1. System packages
sudo dnf install -y git python3 python3-pip python3-devel

# 2. Clone the repository
cd /home/mhough
git clone https://github.com/m9h/biopunk-display.git
cd biopunk-display

# 3. Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# 4. Initialize the database
flask db upgrade

# 5. Create the production .env file
python3 -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" > .env
cat >> .env << 'EOF'
FLASK_APP=biopunk.py
FLIPDOT_PORT=/dev/ttyUSB0
FLIPDOT_BAUD=38400
OPENCLAW_ENABLED=false
EOF
chmod 600 .env

# 6. Serial port access
sudo usermod -aG dialout mhough

# 7. Udev rule for stable device naming
sudo tee /etc/udev/rules.d/99-flipdot.rules << 'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", \
    SYMLINK+="flipdot", MODE="0660", GROUP="dialout"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger

# 8. Install and start the systemd service
sudo cp biopunk-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now biopunk-display

# 9. Open the firewall
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload

# 10. Verify everything works
sudo systemctl status biopunk-display
curl -s http://localhost:5000/api/status | python3 -m json.tool
```

## Common Problems and Solutions

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Active: failed` in status | Crash on startup | `journalctl -u biopunk-display -n 50` for the traceback |
| `Permission denied: '/dev/ttyUSB0'` | User not in dialout group | `sudo usermod -aG dialout mhough` then reboot |
| Port 5000 connection timeout | Firewall blocking | `sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload` |
| Port 5000 connection refused | Service not running | `sudo systemctl start biopunk-display` |
| `Address already in use` | Something else on port 5000 | `ss -tlnp \| grep 5000` to find the culprit |
| `ModuleNotFoundError` | Wrong Python/venv | Verify `ExecStart` uses the full venv path |
| OOM killed | Too much memory usage | Check `journalctl -k` for OOM messages; reduce Vosk model size |
| Serial port is `/dev/ttyUSB1` | Device enumeration order changed | Use the udev symlink `/dev/flipdot` instead |
| Service starts but stops immediately | `StartLimitBurst` exceeded | `systemctl reset-failed biopunk-display` then fix the root cause |
| nginx returns 502 Bad Gateway | Gunicorn not running, or SELinux | Check Gunicorn status; `sudo setsebool -P httpd_can_network_connect 1` |

## What We've Achieved

The display server now:

- **Starts automatically** when the Pi boots, with no human intervention
- **Recovers from crashes** with configurable restart policies
- **Logs everything** to journald, queryable by time, severity, and boot session
- **Secures the serial port** with proper group permissions and stable device naming
- **Protects secrets** in a locked-down `.env` file, not in the unit file or git
- **Limits its own privileges** with systemd security hardening
- **Opens only the ports it needs** through firewalld

This is a production deployment. Not a Docker container, not a cloud service --
just a Python app, a systemd unit, and a Raspberry Pi with a serial port. Simple,
reliable, debuggable.

## What's Next

Chapter 14 is the capstone: OpenClaw, an AI agent powered by Claude that can
autonomously compose messages, react to webcam input, and manage playlists. The
deployment you just set up is the reliable foundation it runs on.
