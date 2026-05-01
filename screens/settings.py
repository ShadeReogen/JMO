#!/usr/bin/env python3
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config as cfg_module
from PIL import ImageDraw, ImageFont
from displayhatmini import DisplayHATMini

CONFIG_PATH = "config.json"

BUTTON_NAMES = {
    DisplayHATMini.BUTTON_A: "A",
    DisplayHATMini.BUTTON_B: "B",
    DisplayHATMini.BUTTON_X: "X",
    DisplayHATMini.BUTTON_Y: "Y",
}

BG           = (10,  10,  20)
COLOR_TITLE  = (0,  240, 255)
COLOR_ITEM   = (180, 180, 200)
COLOR_SEL    = (255, 255, 255)
COLOR_SEL_BG = (35,  35,  80)
COLOR_VAL    = (160, 160,  80)
COLOR_VAL_SEL= (255, 220,  60)
COLOR_HINT   = (70,  70, 110)
COLOR_DIV    = (50,  50,  90)

PHOTO_INTERVAL_OPTIONS = [1, 5, 12, 24]
PHOTO_INTERVAL_LABELS  = {1: "1 hr", 5: "5 hrs", 12: "12 hrs", 24: "Daily"}

ITEMS = ["brightness", "night_mode_start", "photo_interval", "update"]
LABELS = {
    "brightness":      "Brightness",
    "night_mode_start": "Night Mode",
    "photo_interval":  "Photo Refresh",
    "update":          "Update",
}


class SettingsScreen:
    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int,
                 display: DisplayHATMini, on_done):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.display = display
        self.on_done = on_done

        self._prev = {btn: False for btn in BUTTON_NAMES}
        self._sel  = 0

        self._config = self._load_config()
        self._font   = self._load_font(13)
        self._font_b = self._load_font_bold(15)

        self._apply_brightness()

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception as e:
            print(f"[Settings] Failed to load config: {e}")
            return {"brightness": 80, "night_mode": {"start": "23:00"}}

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self._config, f, indent=2)
            cfg_module.reload()
            print("[Settings] Config saved.")
        except Exception as e:
            print(f"[Settings] Failed to save config: {e}")

    # ── Fonts ─────────────────────────────────────────────────────────────────

    def _load_font(self, size):
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _load_font_bold(self, size):
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return self._load_font(size)

    # ── Input ─────────────────────────────────────────────────────────────────

    def update(self):
        for btn, name in BUTTON_NAMES.items():
            pressed = self.display.read_button(btn)
            if pressed and not self._prev[btn]:
                self._on_press(name)
            self._prev[btn] = pressed

    def _on_press(self, name):
        print(f"[Settings] Button: {name}  sel={self._sel}")
        if name == "B":
            self._sel = (self._sel + 1) % len(ITEMS)
        elif name == "Y":
            self._save_config()
            self.on_done()
        elif name in ("A", "X"):
            self._change(name)

    def _change(self, button):
        item = ITEMS[self._sel]

        if item == "brightness":
            v = self._config.get("brightness", 80)
            if button == "X":
                v = min(100, v + 10)
            elif button == "A":
                v = max(10, v - 10)
            self._config["brightness"] = v
            self._apply_brightness()

        elif item == "night_mode_start":
            start = self._config.get("night_mode", {}).get("start", "23:00")
            h, m = map(int, start.split(":"))
            if button == "A":
                h = (h + 1) % 24
            elif button == "X":
                m = (m + 15) % 60
            self._config.setdefault("night_mode", {})["start"] = f"{h:02d}:{m:02d}"

        elif item == "photo_interval":
            current = self._config.get("photo_interval_hours", 24)
            opts = PHOTO_INTERVAL_OPTIONS
            idx = opts.index(current) if current in opts else len(opts) - 1
            if button == "X":
                idx = (idx + 1) % len(opts)
            elif button == "A":
                idx = (idx - 1) % len(opts)
            self._config["photo_interval_hours"] = opts[idx]

        elif item == "update":
            if button == "X":
                self._do_update()

    def _apply_brightness(self):
        brightness = self._config.get("brightness", 80)
        self.display.set_backlight(brightness / 100.0)

    def _do_update(self):
        pass  # TODO: implement update

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _text_w(self, text, font):
        try:
            bb = self.draw.textbbox((0, 0), text, font=font)
            return bb[2] - bb[0]
        except AttributeError:
            w, _ = self.draw.textsize(text, font=font)
            return w

    def render(self):
        w, h = self.width, self.height
        d = self.draw

        d.rectangle((0, 0, w, h), fill=BG)

        # Title
        title = "Settings"
        tw = self._text_w(title, self._font_b)
        d.text(((w - tw) // 2, 8), title, font=self._font_b, fill=COLOR_TITLE)

        # Divider
        d.line((8, 30, w - 8, 30), fill=COLOR_DIV, width=1)

        # Items
        row_h   = 42
        start_y = 38

        for i, item in enumerate(ITEMS):
            y   = start_y + i * row_h
            sel = (i == self._sel)

            if sel:
                d.rectangle((4, y, w - 4, y + row_h - 4), fill=COLOR_SEL_BG)

            label_color = COLOR_SEL if sel else COLOR_ITEM
            d.text((14, y + (row_h - 4) // 2 - 7), LABELS[item],
                   font=self._font, fill=label_color)

            value = self._value_str(item)
            if value:
                val_color = COLOR_VAL_SEL if sel else COLOR_VAL
                vw = self._text_w(value, self._font)
                d.text((w - vw - 14, y + (row_h - 4) // 2 - 7), value,
                       font=self._font, fill=val_color)

        # Hint
        hint = "B:next   A/X:change   Y:save"
        hw = self._text_w(hint, self._font)
        d.text(((w - hw) // 2, h - 16), hint, font=self._font, fill=COLOR_HINT)

    def _value_str(self, item):
        if item == "brightness":
            return f"{self._config.get('brightness', 80)}%"
        if item == "night_mode_start":
            return self._config.get("night_mode", {}).get("start", "23:00")
        if item == "photo_interval":
            hours = self._config.get("photo_interval_hours", 24)
            return PHOTO_INTERVAL_LABELS.get(hours, f"{hours} hrs")
        return ""
