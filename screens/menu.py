#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
from displayhatmini import DisplayHATMini


BUTTON_NAMES = {
    DisplayHATMini.BUTTON_A: "A",
    DisplayHATMini.BUTTON_B: "B",
    DisplayHATMini.BUTTON_X: "X",
    DisplayHATMini.BUTTON_Y: "Y",
}


class MenuScreen:
    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int, display: DisplayHATMini,
                 on_settings=None, on_daily=None, on_photo=None, on_memory=None):
        self.draw        = draw
        self.width       = width
        self.height      = height
        self.display     = display
        self.on_settings = on_settings
        self.on_daily    = on_daily
        self.on_photo    = on_photo
        self.on_memory   = on_memory

        # Edge-detect state: only fire once per physical press
        self._prev = {btn: False for btn in BUTTON_NAMES}

        self._bg = self._load_bg()
        self._font = self._load_font()

    def _load_bg(self):
        try:
            img = Image.open("assets/main_menu.jpg").convert("RGB")
            return img.resize((self.width, self.height))
        except FileNotFoundError:
            print("[Menu] assets/main_menu.jpg not found — using fallback background.")
            return None

    def _load_font(self):
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]:
            try:
                return ImageFont.truetype(path, 11)
            except Exception:
                continue
        return ImageFont.load_default()

    def update(self):
        for btn, name in BUTTON_NAMES.items():
            pressed = self.display.read_button(btn)
            if pressed and not self._prev[btn]:
                self._on_press(name)
            self._prev[btn] = pressed

    def _on_press(self, name):
        print(f"[Menu] Button pressed: {name}")
        if name == "A" and self.on_photo:
            self.on_photo()
        elif name == "B" and self.on_daily:
            self.on_daily()
        elif name == "X" and self.on_memory:
            self.on_memory()
        elif name == "Y" and self.on_settings:
            self.on_settings()

    def render(self):
        w, h = self.width, self.height

        if self._bg:
            self.draw._image.paste(self._bg, (0, 0))
        else:
            self.draw.rectangle((0, 0, w, h), fill=(20, 20, 30))