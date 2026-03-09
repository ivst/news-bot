#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/news-bot}"
APP_USER="${APP_USER:-news-bot}"
SERVICE="${SERVICE:-}"
BRANCH="${BRANCH:-main}"
TEMPLATE_GLOB="${TEMPLATE_GLOB:-news-bot@*.service}"

cd "$APP_DIR"
sudo -u "$APP_USER" git pull origin "$BRANCH"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

declare -a services=()

if [[ -n "$SERVICE" ]]; then
  services=("$SERVICE")
else
  while IFS= read -r unit; do
    [[ -n "$unit" ]] && services+=("$unit")
  done < <(systemctl list-units --type=service --all --no-legend "$TEMPLATE_GLOB" | awk '{print $1}' | sort -u)

  if [[ ${#services[@]} -eq 0 ]]; then
    services=("news-bot")
  fi
fi

for svc in "${services[@]}"; do
  echo "Restarting $svc ..."
  sudo systemctl restart "$svc"
  sudo systemctl status "$svc" --no-pager -l
done
