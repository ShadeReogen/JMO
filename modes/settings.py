"""
modes/settings.py
-----------------
Settings screen.

X scrolls through settings items.
A/B adjust the selected setting:
  - range items: A decreases, B increases
  - time items:  A cycles hour (+1), B cycles minutes (+15)
  - action items: A or B triggers
Y → back to menu.
"""

import time
from PIL import Image, ImageDraw, ImageFont

from modes.base_mode import BaseMode
from core.buttons    import Button
from core.config     import config
from core import updater


class SettingsMode(BaseMode):
    name = "Settings"

    # Each item: (display_label, config_keys, type, options_or_range)
    ITEMS = [
        ("Brightness",       ("brightness",),               "range",  (10, 100, 10)),
        ("Night Start",      ("night_mode", "start"),       "time",   None),
        ("Night End",        ("night_mode", "end"),         "time",   None),
        ("Frame Interval",   ("frame", "interval_seconds"), "range",  (10, 300, 10)),
        ("Check for Update", None,                          "action", None),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected   = 0
        self._dirty      = True
        self._status_msg = ""
        self._status_t   = 0.0

    def start(self):
        self._selected   = 0
        self._dirty      = True
        self._status_msg = ""

        self.buttons.on_press(Button.X, lambda _: self._scroll())
        self.buttons.on_press(Button.Y, lambda _: self.switch_to("menu"))
        self.buttons.on_press(Button.A, lambda _: self._adjust_a())
        self.buttons.on_press(Button.B, lambda _: self._adjust_b())

    def stop(self):
        self.buttons.clear()

    def update(self):
        if self._status_msg and time.monotonic() - self._status_t > 3:
            self._status_msg = ""
            self._dirty = True

        if not self._dirty:
            return
        self._render()
        self._dirty = False

    # ------------------------------------------------------------------

    def _scroll(self):
        self._selected = (self._selected + 1) % len(self.ITEMS)
        self._dirty    = True

    def _adjust_a(self):
        """A: decrease range / cycle hour +1 / trigger action."""
        label, keys, kind, opts = self.ITEMS[self._selected]

        if kind == "action":
            self._run_update()
            return

        val = config.get(*keys)

        if kind == "range":
            mn, _, step = opts
            new_val = max(mn, val - step)
            config.set(*keys, new_val)
            if keys == ("brightness",):
                self.display.set_brightness(new_val)

        elif kind == "time":
            h, m = map(int, val.split(":"))
            h = (h + 1) % 24
            config.set(*keys, f"{h:02d}:{m:02d}")

        self._dirty = True

    def _adjust_b(self):
        """B: increase range / cycle minutes +15 / trigger action."""
        _, keys, kind, opts = self.ITEMS[self._selected]

        if kind == "action":
            self._run_update()
            return

        val = config.get(*keys)

        if kind == "range":
            _, mx, step = opts
            new_val = min(mx, val + step)
            config.set(*keys, new_val)
            if keys == ("brightness",):
                self.display.set_brightness(new_val)

        elif kind == "time":
            h, m = map(int, val.split(":"))
            m = (m + 15) % 60
            config.set(*keys, f"{h:02d}:{m:02d}")

        self._dirty = True

    def _run_update(self):
        self._status_msg = "Checking…"
        self._dirty      = True
        self._render()
        import threading
        def _do():
            if updater.check_for_update():
                self._status_msg = "Updating… rebooting"
                self._dirty      = True
                self._status_t   = time.monotonic()
                self._render()
                time.sleep(1)
                updater.apply_update()
            else:
                self._status_msg = "Already up to date ✓"
                self._dirty      = True
                self._status_t   = time.monotonic()
        threading.Thread(target=_do, daemon=True).start()

    def _render(self):
        W, H = self.display.width, self.display.height
        img  = Image.new("RGB", (W, H), (12, 12, 22))
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
            font_item  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      14)
            font_val   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
            font_hint  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      12)
        except IOError:
            font_title = font_item = font_val = font_hint = ImageFont.load_default()

        draw.text((12, 8), "Settings", font=font_title, fill=(200, 200, 255))
        draw.line([(10, 32), (W - 10, 32)], fill=(40, 40, 70), width=1)

        visible = 5
        start   = max(0, self._selected - 2)
        end     = min(len(self.ITEMS), start + visible)

        for i, idx in enumerate(range(start, end)):
            label, keys, kind, _ = self.ITEMS[idx]
            y      = 38 + i * 34
            is_sel = (idx == self._selected)

            if is_sel:
                draw.rounded_rectangle([8, y - 3, W - 8, y + 26],
                                        radius=6, fill=(30, 30, 55), outline=(100, 100, 200), width=1)

            draw.text((16, y), label, font=font_item,
                      fill=(230, 230, 255) if is_sel else (130, 130, 160))

            if keys is not None:
                val = config.get(*keys)
                val_str = f"{val}%" if (kind == "range" and keys == ("brightness",)) else str(val)
                val_col = (200, 200, 255) if is_sel else (120, 120, 160)
                vbbox = draw.textbbox((0, 0), val_str, font=font_val)
                draw.text((W - (vbbox[2] - vbbox[0]) - 16, y), val_str, font=font_val, fill=val_col)
            elif is_sel:
                draw.text((W - 80, y), "A/B: run", font=font_val, fill=(160, 160, 220))

        # Context-sensitive hint
        _, _, kind, _ = self.ITEMS[self._selected]
        if kind == "time":
            hint = "X:scroll  A:hour  B:min+15  Y:back"
        elif kind == "action":
            hint = "X:scroll  A/B:run  Y:back"
        else:
            hint = "X:scroll  A:-  B:+  Y:back"
        draw.text((8, H - 18), hint, font=font_hint, fill=(55, 55, 80))

        if self._status_msg:
            bbox = draw.textbbox((0, 0), self._status_msg, font=font_hint)
            mw   = bbox[2] - bbox[0]
            draw.text(((W - mw) // 2, H - 32), self._status_msg,
                      font=font_hint, fill=(100, 220, 150))

        self.display.show(img)
