"""
modes/frame.py
--------------
Digital Photo Frame.

Cycles through images in assets/images/ at a configurable interval.
Supports JPEG and PNG. Images are scaled to fill 320×240.

Buttons:
  A → previous image
  B → next image
  Y → back to menu
"""

import os
import random
import time
from PIL import Image

from modes.base_mode import BaseMode
from core.buttons    import Button
from core.config     import config

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
EXTENSIONS  = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}


class FrameMode(BaseMode):
    name = "Frame"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._images:    list[str] = []
        self._index:     int       = 0
        self._last_flip: float     = 0.0
        self._current_img = None

    def start(self):
        self._load_image_list()
        self._index    = 0
        self._last_flip = time.monotonic()

        self.buttons.on_press(Button.A, lambda _: self._prev())
        self.buttons.on_press(Button.B, lambda _: self._next())
        self.buttons.on_press(Button.Y, lambda _: self.switch_to("menu"))

        if self._images:
            self._show_image(self._index)
        else:
            self._show_placeholder()

    def stop(self):
        self.buttons.clear()
        self._current_img = None

    def update(self):
        if not self._images:
            return

        interval = config.get("frame", "interval_seconds", default=30)
        if time.monotonic() - self._last_flip >= interval:
            self._next()

    # ------------------------------------------------------------------

    def _load_image_list(self):
        if not os.path.isdir(IMAGES_DIR):
            self._images = []
            return
        files = [
            os.path.join(IMAGES_DIR, f)
            for f in os.listdir(IMAGES_DIR)
            if os.path.splitext(f)[1].lower() in EXTENSIONS
        ]
        if config.get("frame", "shuffle", default=True):
            random.shuffle(files)
        else:
            files.sort()
        self._images = files

    def _show_image(self, index: int):
        path = self._images[index]
        try:
            img = Image.open(path).convert("RGB")
            img = self._fit(img)
            self.display.show(img)
            self._current_img = path
        except Exception as e:
            print(f"[Frame] Failed to load {path}: {e}")
        self._last_flip = time.monotonic()

    def _fit(self, img: Image.Image) -> Image.Image:
        """Scale to fill 320×240, centred crop."""
        W, H = self.display.width, self.display.height
        ratio  = max(W / img.width, H / img.height)
        new_w  = int(img.width  * ratio)
        new_h  = int(img.height * ratio)
        img    = img.resize((new_w, new_h), Image.LANCZOS)
        left   = (new_w - W) // 2
        top    = (new_h - H) // 2
        return img.crop((left, top, left + W, top + H))

    def _show_placeholder(self):
        from PIL import ImageDraw, ImageFont
        img  = Image.new("RGB", (self.display.width, self.display.height), (20, 20, 35))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except IOError:
            font = ImageFont.load_default()
        msg  = "No images found"
        bbox = draw.textbbox((0, 0), msg, font=font)
        mw   = bbox[2] - bbox[0]
        draw.text(((self.display.width - mw) // 2, self.display.height // 2 - 10),
                  msg, font=font, fill=(120, 120, 150))
        hint = "Add images to assets/images/"
        bbox = draw.textbbox((0, 0), hint, font=font)
        hw   = bbox[2] - bbox[0]
        draw.text(((self.display.width - hw) // 2, self.display.height // 2 + 15),
                  hint, font=font, fill=(70, 70, 100))
        self.display.show(img)

    def _next(self):
        if not self._images:
            return
        self._index = (self._index + 1) % len(self._images)
        self._show_image(self._index)

    def _prev(self):
        if not self._images:
            return
        self._index = (self._index - 1) % len(self._images)
        self._show_image(self._index)
