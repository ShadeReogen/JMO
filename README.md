# pi-frame 💕

A personal interactive display for Raspberry Pi Zero 2 W + Pimoroni Display HAT Mini.

## Modes

| Button | Mode |
|--------|------|
| A | Daily screen (clock, weather, notes) |
| B | Photo frame |
| X | Mood check-in |
| Y | Settings |

## Setup

```bash
git clone <your-private-repo> pi-frame
cd pi-frame
bash install.sh
```

Then reboot if SPI was newly enabled.

## Project layout

```
pi-frame/
├── main.py          # Entry point & state machine
├── config.json      # User settings
├── notes.json       # Date-specific notes
├── core/
│   ├── display.py   # Display abstraction
│   ├── buttons.py   # Button input handler
│   ├── config.py    # Config loader/saver
│   ├── night_mode.py# Night mode watcher thread
│   └── updater.py   # Self-update via git
├── modes/
│   ├── splash.py    # Boot animation
│   ├── menu.py      # Main menu
│   ├── daily.py     # Smart daily screen
│   ├── frame.py     # Photo frame
│   ├── mood.py      # Mood check-in
│   ├── settings.py  # Settings
│   └── night.py     # Night screen
└── assets/
    ├── images/      # Photos for frame mode
    ├── fonts/       # Custom TTF fonts
    └── icons/       # UI icons
```

## Adding photos

Drop JPEG/PNG files into `assets/images/`. They're gitignored — push images
separately or copy them directly to the Pi.

## Updating remotely

From the Settings screen → "Check for Update". The Pi will `git pull` and restart itself.

## Night mode

Configured in `config.json`:
```json
"night_mode": {
  "enabled": true,
  "start": "23:00",
  "end": "08:00",
  "message": "Good night ❤️",
  "brightness": 10
}
```
