#!/usr/bin/env bash
# dev.sh — stop the service and run main.py in the foreground.
# Use this instead of running python3 main.py directly.
# When done: Ctrl+C, then the service won't restart until next boot
# (or run: sudo systemctl start piframe)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[dev] Stopping piframe service…"
sudo systemctl stop piframe

echo "[dev] Running main.py — Ctrl+C to stop"
echo "[dev] Log: $SCRIPT_DIR/logs/piframe.log"
cd "$SCRIPT_DIR"
python3 main.py
