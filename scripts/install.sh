#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/news-bot}"
APP_USER="${APP_USER:-news-bot}"
SERVICE="${SERVICE:-news-bot}"
BRANCH="${BRANCH:-master}"
REPO_URL="${REPO_URL:-https://github.com/ivst/news-bot.git}"

# ---- create system user ----
if id "$APP_USER" &>/dev/null; then
  echo "[OK] User '$APP_USER' already exists"
else
  sudo useradd -r -s /usr/sbin/nologin "$APP_USER"
  echo "[OK] Created user '$APP_USER'"
fi

# ---- clone / prepare repo ----
if [[ -d "$APP_DIR/.git" ]]; then
  echo "[OK] Repository already exists at $APP_DIR"
  sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"
else
  sudo mkdir -p "$(dirname "$APP_DIR")"
  sudo git clone "$REPO_URL" "$APP_DIR"
  echo "[OK] Cloned $REPO_URL → $APP_DIR"
  sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"
fi

# ---- venv ----
if [[ -f "$APP_DIR/.venv/bin/python" ]]; then
  echo "[OK] venv already exists"
else
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
  echo "[OK] Created venv"
fi

# ---- pip install ----
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
echo "[OK] Dependencies installed"

# ---- .env ----
if [[ -f "$APP_DIR/.env" ]]; then
  echo "[OK] .env already exists, skipping"
else
  sudo -u "$APP_USER" cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "[WARN] Created .env from .env.example — EDIT IT BEFORE STARTING: $APP_DIR/.env"
fi

# ---- systemd unit ----
if [[ "$SERVICE" == *@* ]]; then
  UNIT_FILE="news-bot@.service"
  UNIT_PATH="/etc/systemd/system/news-bot@.service"
else
  UNIT_FILE="news-bot.service"
  UNIT_PATH="/etc/systemd/system/news-bot.service"
fi

sudo cp "$APP_DIR/deploy/$UNIT_FILE" "$UNIT_PATH"
sudo systemctl daemon-reload
echo "[OK] Installed $SERVICE"

if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
  echo "[OK] $SERVICE is already running"
else
  read -rp "Start and enable $SERVICE now? [Y/n] " reply
  if [[ "${reply,,}" != "n" ]]; then
    sudo systemctl enable --now "$SERVICE"
    sudo systemctl status "$SERVICE" --no-pager -l
  fi
fi

echo
echo "=== Done ==="
echo "Logs:  sudo journalctl -u $SERVICE -f"
echo "Update: $APP_DIR/scripts/update_service.sh"
