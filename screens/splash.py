#!/usr/bin/env python3
import time
import math
from PIL import ImageFont, ImageDraw, Image


T_FADE_OUT = 2.1
T_DONE     = 2.8

_STAGGER   = 0.09   # seconds between consecutive character drops
_WORD_GAP  = 0.20   # extra pause between "JMO" and "3.0" groups
_ANIM_DUR  = 0.50   # duration of each character's spring animation

BG         = (4,   4,   8)
COLOR_JMO  = (0,   240, 255)   # electric cyan
COLOR_VER  = (255,  20, 147)   # shocking pink


def _ease_in_out(t):
    return t * t * (3.0 - 2.0 * t)


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _phase(start, end, elapsed):
    if elapsed <= start: return 0.0
    if elapsed >= end:   return 1.0
    return _ease_in_out((elapsed - start) / (end - start))


def _spring_disp(t):
    """1.0 at t=0 → ~0 at t=1, with a quick overshoot at t≈0.4."""
    if t <= 0: return 1.0
    if t >= 1: return 0.0
    return math.exp(-5.0 * t) * math.cos(2.5 * math.pi * t)


class SplashScreen:
    _FULL = "JMO 3.0"

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
                self.font = ImageFont.truetype(path, 56)
                break
            except Exception:
                continue

    def _bb(self, text):
        """(left, top, right, bottom) bounding box relative to PIL origin (0, 0)."""
        try:
            return self.draw.textbbox((0, 0), text, font=self.font)
        except AttributeError:
            w, h = self.draw.textsize(text, font=self.font)
            return (0, 0, w, h)

    def _layout(self):
        full_bb = self._bb(self._FULL)
        vis_w   = full_bb[2] - full_bb[0]
        vis_h   = full_bb[3] - full_bb[1]

        # PIL origin that visually centres the full string
        ox_base = (self.width  - vis_w) // 2 - full_bb[0]
        oy_base = (self.height - vis_h) // 2 - full_bb[1]

        # visual top Y when settled = (height - vis_h) // 2
        vis_top = oy_base + full_bb[1]
        self.drop = vis_top + vis_h + 8   # chars start just above top of screen

        # Animation timing per group
        timed = []
        t = 0.0
        for ch in "JMO":
            timed.append((ch, COLOR_JMO, t)); t += _STAGGER
        t += _WORD_GAP
        for ch in "3.0":
            timed.append((ch, COLOR_VER, t)); t += _STAGGER

        # X origin for each character: advance from prefix of the full string.
        # This matches font kerning exactly.
        self.char_data = []
        vis_idx = 0
        for i, ch in enumerate(self._FULL):
            if ch == ' ':
                continue
            prefix_adv = self._bb(self._FULL[:i])[2] if i else 0
            _, color, t_start = timed[vis_idx]
            self.char_data.append((ch, ox_base + prefix_adv, oy_base, color, t_start))
            vis_idx += 1

    # ── Rendering helpers ──────────────────────────────────────────────────────

    def _stamp(self, text, ox, oy, color, alpha):
        """Stamp text at PIL origin (ox, oy), correctly offsetting the bbox."""
        if alpha <= 0.0:
            return
        bb = self._bb(text)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if tw <= 0 or th <= 0:
            return
        pad  = 2
        surf = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        d    = ImageDraw.Draw(surf)
        # Draw so the visual top-left of text lands at (pad, pad) in the surface.
        # bb[0]/bb[1] are the offsets from PIL origin to the visual bbox edges.
        d.text((pad - bb[0], pad - bb[1]), text, font=self.font,
               fill=(*color, int(alpha * 255)))
        # Paste so (pad, pad) in the surface → (ox + bb[0], oy + bb[1]) in the frame.
        self._image.paste(surf, (ox + bb[0] - pad, oy + bb[1] - pad), surf)

    # ── Public interface ───────────────────────────────────────────────────────

    def update(self):
        if not self.done and (time.time() - self.start_time) >= T_DONE:
            self.done = True
            self.on_done()

    def render(self):
        if self.done:
            return

        elapsed = time.time() - self.start_time

        # Solid fill — no banding
        self.draw.rectangle((0, 0, self.width, self.height), fill=BG)

        global_a = 1.0 - _phase(T_FADE_OUT, T_DONE, elapsed)

        for ch, ox, oy, color, t_start in self.char_data:
            t    = _clamp((elapsed - t_start) / _ANIM_DUR)
            disp = _spring_disp(t)
            fade = _clamp((1.0 - disp) * 2.0)
            self._stamp(ch, ox, oy - int(self.drop * disp), color, fade * global_a)
