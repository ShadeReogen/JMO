"""
core/config.py
--------------
Centralised config and notes access.
Loads once at startup, write-through on save.
"""

import json
import os
from datetime import datetime

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
NOTES_PATH  = os.path.join(BASE_DIR, "notes.json")

# Defaults — used if a key is missing from the file
_DEFAULTS = {
    "brightness": 80,
    "night_mode": {
        "enabled": True,
        "start": "23:00",
        "end": "08:00",
        "message": "Good night ❤️",
        "brightness": 10,
    },
    "weather": {"lat": 47.37, "lon": 8.54, "unit": "celsius"},
    "frame": {"interval_seconds": 30, "shuffle": True},
    "last_mode": "menu",
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class Config:
    def __init__(self):
        self._data: dict = {}
        self.reload()

    def reload(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                loaded = json.load(f)
            self._data = _deep_merge(_DEFAULTS, loaded)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = dict(_DEFAULTS)

    def save(self):
        with open(CONFIG_PATH, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, *keys, default=None):
        """config.get('night_mode', 'start') → '23:00'"""
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

    def set(self, *keys_and_value):
        """config.set('brightness', 60)  or  config.set('night_mode', 'start', '22:00')"""
        *keys, value = keys_and_value
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self.save()

    def today_note(self) -> str | None:
        """Return the note text for today's date (MM-DD), if any."""
        try:
            with open(NOTES_PATH, "r") as f:
                notes = json.load(f).get("notes", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        today = datetime.now().strftime("%m-%d")
        for note in notes:
            if note.get("date") == today:
                return note.get("text")
        return None


# Module-level singleton — import and use directly
config = Config()
