#!/usr/bin/env bash
# update.sh
# Called by core/updater.py when a remote update is available.
# Pulls latest code and restarts the systemd service.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[update] Pulling latest code…"
cd "$SCRIPT_DIR"
git pull origin main

echo "[update] Restarting piframe service…"
sudo systemctl restart piframe

echo "[update] Done."
