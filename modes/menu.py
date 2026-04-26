"""
modes/menu.py
-------------
Main menu. The four buttons map to the four application modes.

  A → Daily Screen
  B → Photo Frame
  X → Mood Check-in
  Y → Settings
"""

from PIL import Image, ImageDraw, ImageFont
from modes.base_mode import BaseMode
from core.buttons import Button


# Maps button → (mode_key, label, accent_colour)
MENU_ITEMS = [
    (Button.A, "daily",    "A", "Daily",    (80, 160, 220)),
    (Button.B, "frame",    "B", "Frame",    (80, 200, 130)),
    (Button.X, "mood",     "X", "Mood",     (220, 120, 80)),
    (Button.Y, "settings", "Y", "Settings", (160, 100, 220)),
]


class MenuMode(BaseMode):
    name = "Menu"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dirty = True  # redraw flag — menu is static, only draw once

    def start(self):
        self._dirty = True

        for btn, mode_key, btn_label, item_label, colour in MENU_ITEMS:
            # Capture in closure
            def make_cb(mk):
                def cb(_btn):
                    self.switch_to(mk)
                return cb
            self.buttons.on_press(btn, make_cb(mode_key))

    def stop(self):
        self.buttons.clear()

    def update(self):
        if not self._dirty:
            return  # no need to redraw a static menu

        W, H = self.display.width, self.display.height
        img  = Image.new("RGB", (W, H), (12, 12, 22))
        draw = ImageDraw.Draw(img)

        try:
            font_title  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            font_label  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
            font_btn    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        except IOError:
            font_title = font_label = font_btn = ImageFont.load_default()

        # ── Title ────────────────────────────────────────────────────
        title = "What would you like? ❤️"
        bbox  = draw.textbbox((0, 0), title, font=font_title)
        tw    = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 10), title, font=font_title, fill=(255, 200, 215))

        # ── Menu cards ───────────────────────────────────────────────
        card_w  = (W - 30) // 2   # two columns
        card_h  = 80
        margin  = 10
        start_y = 42

        positions = [
            (margin,              start_y),
            (margin + card_w + 10, start_y),
            (margin,              start_y + card_h + margin),
            (margin + card_w + 10, start_y + card_h + margin),
        ]

        for i, (btn, mode_key, btn_label, item_label, colour) in enumerate(MENU_ITEMS):
            x, y = positions[i]
            # Card background
            draw.rounded_rectangle([x, y, x + card_w, y + card_h],
                                    radius=10, fill=(25, 25, 40), outline=colour, width=2)

            # Button badge
            badge_r = 12
            draw.ellipse([x + 10, y + 10, x + 10 + badge_r*2, y + 10 + badge_r*2],
                         fill=colour)
            bx = draw.textbbox((0, 0), btn_label, font=font_btn)
            bw = bx[2] - bx[0]
            draw.text((x + 10 + badge_r - bw // 2, y + 13), btn_label,
                      font=font_btn, fill=(10, 10, 20))

            # Mode label
            lx = draw.textbbox((0, 0), item_label, font=font_label)
            lw = lx[2] - lx[0]
            draw.text((x + card_w // 2 - lw // 2, y + card_h // 2 + 2),
                      item_label, font=font_label, fill=(230, 230, 240))

        self.display.show(img)
        self._dirty = False
