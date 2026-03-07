#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/news-bot}"
APP_USER="${APP_USER:-news-bot}"
SERVICE="${SERVICE:-news-bot}"
BRANCH="${BRANCH:-master}"

cd "$APP_DIR"
sudo -u "$APP_USER" git pull origin "$BRANCH"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
sudo systemctl restart "$SERVICE"
sudo systemctl status "$SERVICE" --no-pager -l
