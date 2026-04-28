#!/usr/bin/env python3
import time
import math
from PIL import ImageFont, ImageDraw, Image


T_FADE_OUT = 2.1
T_DONE     = 2.8

_STAGGER   = 0.09   # seconds between consecutive character drops
_WORD_GAP  = 0.20   # extra pause between "JMO" and "3.0" groups
_ANIM_DUR  = 0.50   # duration of each character's spring animation

BG        = (4,   4,   8)
COLOR_JMO = (255, 255, 255)
COLOR_VER = (0,   200, 255)


def _ease_in_out(t):
    return t * t * (3.0 - 2.0 * t)


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _phase(start, end, elapsed):
    if elapsed <= start: return 0.0
    if elapsed >= end:   return 1.0
    return _ease_in_out((elapsed - start) / (end - start))


def _spring_disp(t):
    """Displacement multiplier: 1.0 at t=0, decays to 0 at t=1 with bounce overshoot at t≈0.4."""
    if t <= 0: return 1.0
    if t >= 1: return 0.0
    return math.exp(-5.0 * t) * math.cos(2.5 * math.pi * t)


class SplashScreen:

    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int, on_done):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.on_done = on_done
        self._image  = draw._image

        self.start_time = time.time()
        self.done       = False

        self._init_fonts()
        self._layout()

    # ── Setup ──────────────────────────────────────────────────────────────────

    def _init_fonts(self):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        self.font = ImageFont.load_default()
        for path in candidates:
            try:
                self.font = ImageFont.truetype(path, 58)
                break
            except Exception:
                continue

    def _bbox(self, text):
        try:
            bb = self.draw.textbbox((0, 0), text, font=self.font)
            return bb[2] - bb[0], bb[3] - bb[1]
        except AttributeError:
            return self.draw.textsize(text, font=self.font)

    def _layout(self):
        # Assign each character an animation start time
        timed = []
        t = 0.0
        for ch in "JMO":
            timed.append((ch, COLOR_JMO, t))
            t += _STAGGER
        t += _WORD_GAP
        for ch in "3.0":
            timed.append((ch, COLOR_VER, t))
            t += _STAGGER

        spacing = 4
        space_w = max(8, self._bbox("M")[0] // 2)   # visual gap between JMO and 3.0
        widths  = [self._bbox(ch)[0] for ch, _, _ in timed]
        _, h    = self._bbox("M")
        total_w = sum(widths) + spacing * (len(timed) - 1) + space_w

        x = (self.width  - total_w) // 2
        y = (self.height - h)       // 2

        # Characters drop from just above the top of the screen
        self.drop = y + h + 8

        self.char_data = []
        for i, (ch, color, t_start) in enumerate(timed):
            self.char_data.append((ch, x, y, color, t_start))
            x += widths[i] + spacing
            if i == 2:      # extra gap after "O", before "3"
                x += space_w

    # ── Rendering helpers ──────────────────────────────────────────────────────

    def _stamp(self, text, x, y, color, alpha):
        if alpha <= 0.0:
            return
        tw, th = self._bbox(text)
        if tw <= 0 or th <= 0:
            return
        pad  = 2
        surf = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        d    = ImageDraw.Draw(surf)
        d.text((pad, pad), text, font=self.font, fill=(*color, int(alpha * 255)))
        self._image.paste(surf, (x - pad, y - pad), surf)

    # ── Public interface ───────────────────────────────────────────────────────

    def update(self):
        if not self.done and (time.time() - self.start_time) >= T_DONE:
            self.done = True
            self.on_done()

    def render(self):
        if self.done:
            return

        elapsed = time.time() - self.start_time

        # Solid fill — no per-row loop, no banding
        self.draw.rectangle((0, 0, self.width, self.height), fill=BG)

        global_a = 1.0 - _phase(T_FADE_OUT, T_DONE, elapsed)

        for ch, cx, cy, color, t_start in self.char_data:
            t     = _clamp((elapsed - t_start) / _ANIM_DUR)
            disp  = _spring_disp(t)
            y_off = int(self.drop * disp)
            fade  = _clamp((1.0 - disp) * 2.0)   # fully visible by the time char reaches final pos
            self._stamp(ch, cx, cy - y_off, color, fade * global_a)
