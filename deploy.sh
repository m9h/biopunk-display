#!/bin/bash
# Biopunk Flipdot Display — deployment script
# Run on the Raspberry Pi to set up or update the service.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Biopunk Flipdot Deploy ==="

# Check architecture
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "Warning: expected aarch64 (Raspberry Pi), got $ARCH"
    echo "Continuing anyway..."
fi

# Create/update venv
if ! [ -d .venv ]; then
    echo "Creating virtual environment..."
    if command -v uv &>/dev/null; then
        uv venv .venv
    else
        python3 -m venv .venv
    fi
fi

echo "Installing dependencies..."
if command -v uv &>/dev/null; then
    uv pip install -r requirements.txt
else
    .venv/bin/pip install -r requirements.txt
fi

# Run database migrations
echo "Running database migrations..."
FLASK_APP=biopunk.py .venv/bin/flask db upgrade

# Install udev rules for stable /dev/flipdot symlink
if [ -f deploy/99-flipdot.rules ]; then
    echo "Installing udev rules for FTDI adapter..."
    sudo cp deploy/99-flipdot.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi

# Install systemd service (user-level, no sudo)
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cp biopunk-display.service "$SERVICE_DIR/"

# Fix WorkingDirectory to actual location
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$SCRIPT_DIR|" "$SERVICE_DIR/biopunk-display.service"
sed -i "s|ExecStart=.*gunicorn|ExecStart=$SCRIPT_DIR/.venv/bin/gunicorn|" "$SERVICE_DIR/biopunk-display.service"

echo "Reloading systemd..."
systemctl --user daemon-reload
systemctl --user enable biopunk-display

echo "Restarting service..."
systemctl --user restart biopunk-display

# Enable linger so user services start at boot
loginctl enable-linger "$USER" 2>/dev/null || true

echo ""
echo "=== Done ==="
systemctl --user status biopunk-display --no-pager || true
echo ""
echo "Useful commands:"
echo "  systemctl --user status biopunk-display"
echo "  systemctl --user restart biopunk-display"
echo "  journalctl --user -u biopunk-display -f"
