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
    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int, display: DisplayHATMini):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.display = display

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
        # TODO: swap to mode screens
        # A → digital frame
        # B → daily screen
        # X → mood / check-in
        # Y → settings

    def render(self):
        w, h = self.width, self.height

        if self._bg:
            self.draw._image.paste(self._bg, (0, 0))
        else:
            self.draw.rectangle((0, 0, w, h), fill=(20, 20, 30))

        # Bottom hint bar
        bar_h = 28
        self.draw.rectangle((0, h - bar_h, w, h), fill=(0, 0, 0))

        hints = "A · B · X · Y  →  choose mode"
        try:
            bb = self.draw.textbbox((0, 0), hints, font=self._font)
            tw = bb[2] - bb[0]
        except AttributeError:
            tw, _ = self.draw.textsize(hints, font=self._font)

        self.draw.text(
            ((w - tw) // 2, h - bar_h + 7),
            hints,
            font=self._font,
            fill=(180, 180, 180),
        )