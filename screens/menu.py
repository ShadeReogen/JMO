#!/usr/bin/env python3
from PIL import Image, ImageDraw
from displayhatmini import DisplayHATMini


BUTTON_NAMES = {
    DisplayHATMini.BUTTON_A: "A",
    DisplayHATMini.BUTTON_B: "B",
    DisplayHATMini.BUTTON_X: "X",
    DisplayHATMini.BUTTON_Y: "Y",
}


class MenuScreen:
    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int, display: DisplayHATMini):
        """
        draw    - shared ImageDraw instance from main
        width   - display width
        height  - display height
        display - DisplayHATMini instance (used for button reading)
        """
        self.draw = draw
        self.width = width
        self.height = height
        self.display = display

        # Track button states to detect press edges (avoid repeated prints)
        self._prev_states = {btn: False for btn in BUTTON_NAMES}

        # Load background image
        self._bg = self._load_bg()

        # Register button callback (alternative approach — works alongside polling)
        self.display.on_button_pressed(self._button_callback)

    def _load_bg(self):
        try:
            img = Image.open("assets/main_menu.jpg").convert("RGB")
            img = img.resize((self.width, self.height))
            return img
        except FileNotFoundError:
            print("[MenuScreen] assets/main_menu.jpg not found, using solid background.")
            return None

    def _button_callback(self, pin):
        """Called by DisplayHATMini on any button event."""
        if not self.display.read_button(pin):
            return  # Ignore releases
        name = BUTTON_NAMES.get(pin, f"pin{pin}")
        print(f"[Menu] Button pressed: {name}")
        # TODO: route to mode screens once implemented
        # e.g. A → digital frame, B → daily screen, X → mood, Y → settings

    def update(self):
        # Polling fallback — catches presses even if callback misses edges
        for btn, name in BUTTON_NAMES.items():
            pressed = self.display.read_button(btn)
            if pressed and not self._prev_states[btn]:
                print(f"[Menu] Button pressed (poll): {name}")
            self._prev_states[btn] = pressed

    def render(self):
        w, h = self.width, self.height

        if self._bg:
            # Paste background image into the draw buffer's underlying image
            # We need a reference to the image — retrieve it from the draw object
            self.draw._image.paste(self._bg, (0, 0))
        else:
            # Fallback: plain dark background
            self.draw.rectangle((0, 0, w, h), fill=(20, 20, 30))

        # Optional: overlay a semi-transparent label strip at the bottom
        # (PIL doesn't support true alpha compositing without an RGBA step,
        #  so we just draw a dark bar directly)
        bar_h = 28
        self.draw.rectangle((0, h - bar_h, w, h), fill=(0, 0, 0))

        try:
            from PIL import ImageFont
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11
            )
        except Exception:
            from PIL import ImageFont
            font = ImageFont.load_default()

        hints = "A · B · X · Y  →  choose mode"
        try:
            bbox = self.draw.textbbox((0, 0), hints, font=font)
            tw = bbox[2] - bbox[0]
        except AttributeError:
            tw, _ = self.draw.textsize(hints, font=font)

        self.draw.text(
            ((w - tw) // 2, h - bar_h + 7),
            hints,
            font=font,
            fill=(180, 180, 180),
        )