"""
modes/splash.py
---------------
Boot splash — "JMO 3.0" types in letter by letter with a jittery bounce,
then the whole block slides off to the left and the menu loads.
"""

import time
import math
from PIL import Image, ImageDraw, ImageFont
from modes.base_mode import BaseMode

TEXT           = "JMO 3.0"
FONT_SIZE      = 64
LETTER_SPACING = 3

# When each character of TEXT appears (seconds from boot).
# Intentionally irregular to feel hand-typed.
CHAR_TIMES = (0.15, 0.47, 0.76, 0.94, 1.26, 1.49, 1.79)

HOLD_START      = 2.2   # typing ends — hold complete text here
EXIT_START      = 2.7   # slide-off begins
EXIT_END        = 3.55  # slide complete → switch to menu
SPLASH_DURATION = EXIT_END

# Per-character initial bounce offset (px). Alternating & irregular.
JITTER_DURATION = 0.25
_JITTERS        = (9, -7, 10, -5, 8, -11, 6)

BG_COLOR     = (0,   0,   0)
TEXT_COLOR   = (240, 252, 255)   # near-white, slight cool tint
CURSOR_COLOR = (0,  220, 255)    # cyan


def _load_font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except IOError:
        return ImageFont.load_default()


class SplashMode(BaseMode):
    name = "Splash"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_time = None
        self._done       = False
        self._font       = None
        self._positions  = None   # x position per char (+ 1 cursor slot)
        self._text_y     = 0

    def start(self):
        self._start_time = time.monotonic()
        self._done       = False
        self._font       = _load_font(FONT_SIZE)
        self._positions  = None

    def stop(self):
        self.buttons.clear()

    # ------------------------------------------------------------------

    def _build_positions(self, W, H):
        """Compute per-character x positions, centred on the display."""
        dummy = Image.new("RGB", (1, 1))
        d     = ImageDraw.Draw(dummy)

        widths = []
        for ch in TEXT:
            bb = d.textbbox((0, 0), ch, font=self._font)
            widths.append(bb[2] - bb[0])

        total_w = sum(widths) + LETTER_SPACING * (len(TEXT) - 1)
        bb      = d.textbbox((0, 0), TEXT, font=self._font)
        text_h  = bb[3] - bb[1]

        x            = (W - total_w) // 2
        self._text_y = (H - text_h) // 2

        positions = []
        for w in widths:
            positions.append(x)
            x += w + LETTER_SPACING
        positions.append(x)          # slot for cursor after last char
        self._positions = positions

    # ------------------------------------------------------------------

    def update(self):
        if self._done:
            return

        elapsed  = time.monotonic() - self._start_time
        progress = min(elapsed / SPLASH_DURATION, 1.0)

        W, H = self.display.width, self.display.height

        if self._positions is None:
            self._build_positions(W, H)

        # Phase
        if elapsed < HOLD_START:
            phase = "type"
        elif elapsed < EXIT_START:
            phase = "hold"
        else:
            phase = "exit"

        num_visible = sum(1 for t in CHAR_TIMES if elapsed >= t)

        # ── Text surface ─────────────────────────────────────────────
        text_surf = Image.new("RGB", (W, H), BG_COLOR)
        td        = ImageDraw.Draw(text_surf)
        y0        = self._text_y

        for i in range(num_visible):
            char_age = elapsed - CHAR_TIMES[i]
            jitter_y = 0
            if char_age < JITTER_DURATION:
                t_norm   = char_age / JITTER_DURATION
                # Damped cosine: large on arrival, decays to zero
                jitter_y = int(
                    _JITTERS[i] * (1.0 - t_norm) * math.cos(t_norm * math.pi * 1.5)
                )
            td.text(
                (self._positions[i], y0 + jitter_y),
                TEXT[i], font=self._font, fill=TEXT_COLOR,
            )

        # Blinking cursor
        if phase in ("type", "hold"):
            if int(elapsed * 2.5) % 2 == 0:
                ci = min(num_visible, len(TEXT))
                td.text(
                    (self._positions[ci], y0),
                    "|", font=self._font, fill=CURSOR_COLOR,
                )

        # ── Compose final frame ───────────────────────────────────────
        img = Image.new("RGB", (W, H), BG_COLOR)

        if phase == "exit":
            t_norm  = min((elapsed - EXIT_START) / (EXIT_END - EXIT_START), 1.0)
            # Quadratic ease-in: slow start, then rushes off to the left
            slide_x = int(-W * 1.15 * (t_norm ** 2))
            img.paste(text_surf, (slide_x, 0))
        else:
            img.paste(text_surf, (0, 0))

        self.display.show(img)

        if progress >= 1.0 and not self._done:
            self._done = True
            self.switch_to("menu")
