#!/usr/bin/env bash
set -euo pipefail

# ===== ALANBOT VPS Setup Script =====
# Run as root on a fresh Ubuntu/Debian server:
#   curl -sSL <url> | bash
# Or: sudo bash deploy/setup.sh

APP_DIR="/opt/alanbot"
SERVICE_USER="alanbot"
SERVICE_NAME="alanbot"

echo "=== ALANBOT Setup ==="

# 1. Install system dependencies
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git > /dev/null

# 2. Create service user
echo "[2/6] Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "$APP_DIR" "$SERVICE_USER"
fi

# 3. Deploy code
echo "[3/6] Deploying code to $APP_DIR..."
mkdir -p "$APP_DIR"
# Copy project files (excluding .git, .env, data/)
rsync -a --exclude='.git' --exclude='.env' --exclude='data/' --exclude='venv/' \
    --exclude='__pycache__' --exclude='.claude' \
    "$(cd "$(dirname "$0")/.." && pwd)/" "$APP_DIR/"

mkdir -p "$APP_DIR/data"

# 4. Create venv and install deps
echo "[4/6] Setting up Python venv..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# 5. Setup .env if missing
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo "  !!! IMPORTANT: Edit /opt/alanbot/.env and set BOT_TOKEN and PARENT_PASSWORD !!!"
    echo ""
fi

# Fix ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# 6. Install and enable systemd service
echo "[5/6] Installing systemd service..."
cp "$APP_DIR/deploy/alanbot.service" /etc/systemd/system/"$SERVICE_NAME".service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "[6/6] Starting bot..."
systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "=== ALANBOT is running! ==="
else
    echo ""
    echo "=== ALANBOT failed to start. Check logs: ==="
    echo "    journalctl -u $SERVICE_NAME -n 30 --no-pager"
fi

echo ""
echo "Useful commands:"
echo "  systemctl status $SERVICE_NAME    — check status"
echo "  journalctl -u $SERVICE_NAME -f    — live logs"
echo "  systemctl restart $SERVICE_NAME   — restart bot"
echo "  systemctl stop $SERVICE_NAME      — stop bot"
echo "  nano /opt/alanbot/.env            — edit config"
