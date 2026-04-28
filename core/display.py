"""
core/display.py
---------------
Abstraction layer over the DisplayHATMini + ST7789.
All rendering goes through here — no other module touches the hardware directly.
"""

import logging
import os
import threading
from PIL import Image
from displayhatmini import DisplayHATMini

logger = logging.getLogger(__name__)

WIDTH  = DisplayHATMini.WIDTH   # 320
HEIGHT = DisplayHATMini.HEIGHT  # 240


class Display:
    """
    Wraps DisplayHATMini and exposes:
      - show(image)        push a PIL Image to the screen
      - set_brightness(%)  0-100 percent
      - clear()            blank the screen black
    Thread-safe: a lock prevents concurrent SPI writes.
    """

    def __init__(self):
        # DisplayHATMini wants a buffer object or None for headless init.
        # We pass a blank PIL image as the buffer so it owns a real surface.
        self._buffer = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        self._dhm    = DisplayHATMini(self._buffer)
        self._lock   = threading.Lock()
        self._brightness = 80  # percent
        self.set_brightness(self._brightness)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, image: Image.Image):
        """Push a PIL RGB image (320×240) to the display. Thread-safe."""
        if image.size != (WIDTH, HEIGHT):
            image = image.resize((WIDTH, HEIGHT))
        if image.mode != "RGB":
            image = image.convert("RGB")
        try:
            with self._lock:
                self._dhm.buffer = image
                self._dhm.display()
        except Exception:
            logger.exception("display.show() failed")

    def set_brightness(self, percent: int):
        """Set backlight brightness 0–100."""
        percent = max(0, min(100, percent))
        self._brightness = percent
        # DisplayHATMini exposes set_led on the backlight; brightness is
        # driven by the ST7789 backlight GPIO via PWM duty cycle (0.0–1.0).
        self._dhm.set_backlight(percent / 100.0)

    def get_brightness(self) -> int:
        return self._brightness

    def clear(self, colour=(0, 0, 0)):
        """Blank the display to a solid colour (default black)."""
        img = Image.new("RGB", (WIDTH, HEIGHT), colour)
        self.show(img)

    def set_led(self, r: float, g: float, b: float):
        """
        Set the RGB LED on the hat.
        r, g, b are floats 0.0–1.0
        """
        self._dhm.set_led(r, g, b)

    @property
    def width(self) -> int:
        return WIDTH

    @property
    def height(self) -> int:
        return HEIGHT
