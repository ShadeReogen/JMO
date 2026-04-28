#!/usr/bin/env bash
# install.sh
# First-time setup for pi-frame on Raspberry Pi OS Lite.
# Run as: bash install.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  pi-frame installer"
echo "============================================"

# ── System packages ──────────────────────────────────────────────────
echo "[1/5] Installing system packages…"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip \
    python3-pil \
    python3-gpiozero \
    python3-rpi.gpio \
    git \
    fonts-dejavu-core \
    libopenjp2-7

# ── Python dependencies ───────────────────────────────────────────────
echo "[2/5] Installing Python packages…"
pip3 install --break-system-packages -r "$SCRIPT_DIR/requirements.txt"

# ── Enable SPI (needed for the display) ──────────────────────────────
echo "[3/5] Enabling SPI interface…"
if ! grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
    BOOT_CONFIG="/boot/firmware/config.txt"
    [ -f /boot/config.txt ] && BOOT_CONFIG="/boot/config.txt"
    echo "dtparam=spi=on" | sudo tee -a "$BOOT_CONFIG"
    echo "  → SPI enabled (reboot required after install)"
else
    echo "  → SPI already enabled"
fi

# ── Create asset and log directories ─────────────────────────────────
echo "[4/5] Creating asset and log directories…"
mkdir -p "$SCRIPT_DIR/assets/images"
mkdir -p "$SCRIPT_DIR/assets/fonts"
mkdir -p "$SCRIPT_DIR/assets/icons"
mkdir -p "$SCRIPT_DIR/logs"

# ── systemd service ───────────────────────────────────────────────────
echo "[5/5] Installing systemd service…"
SERVICE_FILE="/etc/systemd/system/piframe.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=pi-frame display service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $SCRIPT_DIR/main.py
WorkingDirectory=$SCRIPT_DIR
Restart=always
RestartSec=5
User=$USER
Environment=PYTHONUNBUFFERED=1
StandardOutput=append:$SCRIPT_DIR/logs/piframe.log
StandardError=append:$SCRIPT_DIR/logs/piframe.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable piframe

echo ""
echo "============================================"
echo "  Installation complete!"
echo "  Logs: $SCRIPT_DIR/logs/piframe.log"
echo ""
echo "  Rebooting in 5 seconds to apply SPI…"
echo "  (Ctrl+C to cancel)"
echo "============================================"
sleep 5
sudo reboot
