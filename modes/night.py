"""
modes/night.py
--------------
Night screen — shown during configured quiet hours.
Dim, soft, minimal. Just a clock and a sweet message.
Any button press is ignored (no accidental wake from pocket etc.)
"""

import time
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from modes.base_mode import BaseMode
from core.config import config


class NightScreen(BaseMode):
    name = "Night"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_minute = -1

    def start(self):
        self._last_minute = -1
        # No button callbacks intentionally

    def stop(self):
        self.buttons.clear()

    def update(self):
        now = datetime.now()
        if now.minute == self._last_minute:
            return  # only redraw every minute
        self._last_minute = now.minute

        W, H = self.display.width, self.display.height
        img  = Image.new("RGB", (W, H), (5, 5, 12))
        draw = ImageDraw.Draw(img)

        try:
            font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
            font_msg  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_date = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except IOError:
            font_time = font_msg = font_date = ImageFont.load_default()

        # Soft pulsing star-dots in background
        t = time.monotonic()
        for i in range(18):
            sx = int((i * 137.5) % W)
            sy = int((i * 73.1)  % H)
            alpha = int(30 + 20 * math.sin(t * 0.4 + i))
            c = (alpha, alpha, alpha + 10)
            draw.ellipse([sx-1, sy-1, sx+1, sy+1], fill=c)

        # Time
        time_str = now.strftime("%H:%M")
        bbox = draw.textbbox((0, 0), time_str, font=font_time)
        tw   = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, H // 2 - 55), time_str,
                  font=font_time, fill=(180, 140, 160))

        # Date
        date_str = now.strftime("%A, %d %B")
        bbox = draw.textbbox((0, 0), date_str, font=font_date)
        dw   = bbox[2] - bbox[0]
        draw.text(((W - dw) // 2, H // 2 + 10), date_str,
                  font=font_date, fill=(100, 80, 100))

        # Sweet message
        msg  = config.get("night_mode", "message", default="Good night ❤️")
        bbox = draw.textbbox((0, 0), msg, font=font_msg)
        mw   = bbox[2] - bbox[0]
        draw.text(((W - mw) // 2, H // 2 + 38), msg,
                  font=font_msg, fill=(160, 90, 110))

        self.display.show(img)
