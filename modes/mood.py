"""
modes/mood.py
-------------
Mood check-in screen.

  A → Happy 😊
  B → Angry 😠
  X → Thinking of you 💭
  Y → Exit (back to menu)

Logs entry to mood_log.json.
(Notification hook is a stub — wire up later.)
"""

import json
import os
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from modes.base_mode import BaseMode
from core.buttons    import Button

LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mood_log.json")

MOODS = {
    Button.A: ("Happy",           "😊", (80,  200, 120)),
    Button.B: ("Angry",           "😠", (220,  80,  80)),
    Button.X: ("Thinking of you", "💭", (120, 160, 240)),
}


class MoodMode(BaseMode):
    name = "Mood"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._state        = "idle"     # idle | confirmed
        self._selected     = None
        self._confirm_time = 0.0
        self._dirty        = True

    def start(self):
        self._state    = "idle"
        self._selected = None
        self._dirty    = True

        for btn, (label, emoji, colour) in MOODS.items():
            def make_cb(b, lb, em, co):
                def cb(_btn):
                    self._log_mood(lb)
                    self._selected = (lb, em, co)
                    self._state    = "confirmed"
                    self._confirm_time = time.monotonic()
                    self._dirty    = True
                return cb
            self.buttons.on_press(btn, make_cb(btn, label, emoji, colour))

        self.buttons.on_press(Button.Y, lambda _: self.switch_to("menu"))

    def stop(self):
        self.buttons.clear()
        self._state = "idle"

    def update(self):
        # Auto-return to menu after showing confirmation
        if self._state == "confirmed":
            if time.monotonic() - self._confirm_time > 2.5:
                self.switch_to("menu")
                return

        if not self._dirty:
            return

        if self._state == "confirmed" and self._selected:
            self._render_confirmed(*self._selected)
        else:
            self._render_idle()

        self._dirty = False

    # ------------------------------------------------------------------

    def _render_idle(self):
        W, H = self.display.width, self.display.height
        img  = Image.new("RGB", (W, H), (12, 12, 22))
        draw = ImageDraw.Draw(img)

        try:
            font_title  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
            font_label  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      14)
            font_btn    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        except IOError:
            font_title = font_label = font_btn = ImageFont.load_default()

        title = "How are you feeling? 💕"
        bbox  = draw.textbbox((0, 0), title, font=font_title)
        tw    = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 10), title, font=font_title, fill=(255, 200, 220))

        # Three mood cards (A, B, X) + Y hint
        card_configs = [
            (Button.A, "A", "Happy",           "😊", (80,  200, 120), (20,  52)),
            (Button.B, "B", "Angry",           "😠", (220,  80,  80), (170,  52)),
            (Button.X, "X", "Thinking of you", "💭", (120, 160, 240), (95,  142)),
        ]
        cw, ch = 130, 80

        for btn, btn_lbl, label, emoji, colour, (cx, cy) in card_configs:
            draw.rounded_rectangle([cx, cy, cx + cw, cy + ch],
                                    radius=10, fill=(22, 22, 38), outline=colour, width=2)
            # Badge
            draw.ellipse([cx + 8, cy + 8, cx + 30, cy + 30], fill=colour)
            bx = draw.textbbox((0, 0), btn_lbl, font=font_btn)
            bw = bx[2] - bx[0]
            draw.text((cx + 19 - bw // 2, cy + 11), btn_lbl, font=font_btn, fill=(10, 10, 20))
            # Label
            lx = draw.textbbox((0, 0), label, font=font_label)
            lw = lx[2] - lx[0]
            draw.text((cx + cw // 2 - lw // 2, cy + ch - 24), label,
                      font=font_label, fill=(210, 210, 230))

        # Y → exit hint
        draw.text((W - 60, H - 18), "Y: Back", font=font_label, fill=(60, 60, 90))
        self.display.show(img)

    def _render_confirmed(self, label: str, emoji: str, colour: tuple):
        W, H = self.display.width, self.display.height
        img  = Image.new("RGB", (W, H), (10, 10, 20))
        draw = ImageDraw.Draw(img)

        try:
            font_big  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
        except IOError:
            font_big = font_small = ImageFont.load_default()

        msg  = f"Logged: {label}"
        bbox = draw.textbbox((0, 0), msg, font=font_big)
        mw   = bbox[2] - bbox[0]
        draw.text(((W - mw) // 2, H // 2 - 30), msg, font=font_big, fill=colour)

        sub  = "Sending you a hug 💕"
        bbox = draw.textbbox((0, 0), sub, font=font_small)
        sw   = bbox[2] - bbox[0]
        draw.text(((W - sw) // 2, H // 2 + 10), sub, font=font_small, fill=(200, 170, 190))

        self.display.show(img)

    def _log_mood(self, label: str):
        entry = {"timestamp": datetime.now().isoformat(), "mood": label}
        try:
            try:
                with open(LOG_PATH, "r") as f:
                    log = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                log = []
            log.append(entry)
            with open(LOG_PATH, "w") as f:
                json.dump(log, f, indent=2)
        except Exception as e:
            print(f"[Mood] Failed to log: {e}")

    def _notify(self, label: str):
        """
        Stub — wire up notification here later.
        Options: Telegram bot, ntfy.sh, pushover, etc.
        """
        print(f"[Mood] Notification stub: mood={label}")
