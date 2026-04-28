#!/usr/bin/env python3
import time
from PIL import ImageFont, ImageDraw


SPLASH_DURATION = 3.0  # seconds


class SplashScreen:
    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int, on_done):
        """
        draw     - shared ImageDraw instance from main
        width    - display width
        height   - display height
        on_done  - callback invoked when the splash finishes
        """
        self.draw = draw
        self.width = width
        self.height = height
        self.on_done = on_done

        self.start_time = time.time()
        self.done = False

        # Try to load a bigger font, fall back to default
        try:
            self.font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40
            )
        except Exception:
            self.font_large = ImageFont.load_default()

    def update(self):
        elapsed = time.time() - self.start_time
        if not self.done and elapsed >= SPLASH_DURATION:
            self.done = True
            self.on_done()

    def render(self):
        if self.done:
            return

        w, h = self.width, self.height

        # Background: deep dark
        self.draw.rectangle((0, 0, w, h), fill=(10, 10, 20))

        # Centered title text
        text = "JMO 3.0"
        # PIL 9+ uses textbbox; older uses textsize
        try:
            bbox = self.draw.textbbox((0, 0), text, font=self.font_large)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw, th = self.draw.textsize(text, font=self.font_large)

        x = (w - tw) // 2
        y = (h - th) // 2

        # Soft glow effect — draw text slightly offset in dim colour first
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
            self.draw.text((x + dx, y + dy), text, font=self.font_large, fill=(30, 30, 80))

        # Main text in white
        self.draw.text((x, y), text, font=self.font_large, fill=(255, 255, 255))

        # Subtle subtitle
        try:
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
            )
        except Exception:
            font_small = ImageFont.load_default()

        sub = "loading..."
        try:
            sbbox = self.draw.textbbox((0, 0), sub, font=font_small)
            sw = sbbox[2] - sbbox[0]
        except AttributeError:
            sw, _ = self.draw.textsize(sub, font=font_small)

        self.draw.text(
            ((w - sw) // 2, y + th + 12),
            sub,
            font=font_small,
            fill=(100, 100, 140),
        )