"""
modes/settings.py
-----------------
Settings screen.

A/B scroll through settings items.
X adjusts the selected setting.
Y → back to menu.

Settings available:
  - Brightness (10–100, step 10)
  - Night mode on/off
  - Night start time
  - Night end time
  - Check for update
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
        ("Brightness",       ("brightness",),                   "range",  (10, 100, 10)),
        ("Night Mode",       ("night_mode", "enabled"),         "bool",   None),
        ("Night Start",      ("night_mode", "start"),           "time",   ("hours", 1)),
        ("Night End",        ("night_mode", "end"),             "time",   ("hours", 1)),
        ("Frame Interval",   ("frame", "interval_seconds"),     "range",  (10, 300, 10)),
        ("Check for Update", None,                              "action", None),
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

        self.buttons.on_press(Button.A, lambda _: self._scroll(-1))
        self.buttons.on_press(Button.B, lambda _: self._scroll(+1))
        self.buttons.on_press(Button.X, lambda _: self._adjust())
        self.buttons.on_press(Button.Y, lambda _: self.switch_to("menu"))

    def stop(self):
        self.buttons.clear()

    def update(self):
        # Clear status message after 3 s
        if self._status_msg and time.monotonic() - self._status_t > 3:
            self._status_msg = ""
            self._dirty = True

        if not self._dirty:
            return
        self._render()
        self._dirty = False

    # ------------------------------------------------------------------

    def _scroll(self, direction: int):
        self._selected = (self._selected + direction) % len(self.ITEMS)
        self._dirty    = True

    def _adjust(self):
        label, keys, kind, opts = self.ITEMS[self._selected]

        if kind == "action":
            self._run_update()
            return

        val = config.get(*keys)

        if kind == "bool":
            config.set(*keys, not val)

        elif kind == "range":
            mn, mx, step = opts
            new_val = (val + step - mn) % (mx - mn + step) + mn
            config.set(*keys, new_val)
            # Apply brightness immediately
            if keys == ("brightness",):
                self.display.set_brightness(new_val)

        elif kind == "time":
            # Cycle through hours 00:00 – 23:00
            h, m = map(int, val.split(":"))
            h = (h + 1) % 24
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

        draw.text((12, 8), "Settings ⚙️", font=font_title, fill=(200, 200, 255))
        draw.line([(10, 32), (W - 10, 32)], fill=(40, 40, 70), width=1)

        # Visible window of items
        visible = 5
        start   = max(0, self._selected - 2)
        end     = min(len(self.ITEMS), start + visible)

        for i, idx in enumerate(range(start, end)):
            label, keys, kind, opts = self.ITEMS[idx]
            y       = 38 + i * 34
            is_sel  = (idx == self._selected)

            if is_sel:
                draw.rounded_rectangle([8, y - 3, W - 8, y + 26],
                                        radius=6, fill=(30, 30, 55), outline=(100, 100, 200), width=1)

            draw.text((16, y), label, font=font_item,
                      fill=(230, 230, 255) if is_sel else (130, 130, 160))

            # Value
            if keys is not None:
                val = config.get(*keys)
                if kind == "bool":
                    val_str = "On ✓" if val else "Off"
                    val_col = (100, 220, 130) if val else (180, 80, 80)
                else:
                    if kind == "range" and keys == ("brightness",):
                        val_str = f"{val}%"
                    else:
                        val_str = str(val)
                    val_col = (200, 200, 255) if is_sel else (120, 120, 160)
                vbbox = draw.textbbox((0, 0), val_str, font=font_val)
                vw    = vbbox[2] - vbbox[0]
                draw.text((W - vw - 16, y), val_str, font=font_val, fill=val_col)
            elif is_sel:
                draw.text((W - 70, y), "← X", font=font_val, fill=(160, 160, 220))

        # Hints
        draw.text((8, H - 18), "A/B: scroll  X: change  Y: back",
                  font=font_hint, fill=(55, 55, 80))

        # Status message
        if self._status_msg:
            bbox = draw.textbbox((0, 0), self._status_msg, font=font_hint)
            mw   = bbox[2] - bbox[0]
            draw.text(((W - mw) // 2, H - 32), self._status_msg,
                      font=font_hint, fill=(100, 220, 150))

        self.display.show(img)
