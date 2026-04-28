#!/usr/bin/env python3
import time
import math
from PIL import ImageFont, ImageDraw, Image


# ── Timing (seconds) ──────────────────────────────────────────────────────────
T_FADE_IN   = 0.0   # title fade-in starts
T_HOLD      = 1.2   # full opacity hold starts
T_LINE      = 1.6   # accent underline sweeps in
T_SUB       = 2.0   # subtitle fades in
T_FADE_OUT  = 3.2   # everything fades out
T_DONE      = 4.0   # hand off to menu


def _ease_in_out(t):
    """Smooth cubic ease, t in [0, 1]."""
    return t * t * (3.0 - 2.0 * t)


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _phase(start, end, elapsed):
    """Eased 0→1 progress through a [start, end] time window."""
    if elapsed <= start:
        return 0.0
    if elapsed >= end:
        return 1.0
    return _ease_in_out((elapsed - start) / (end - start))


def _blend(fg, bg, a):
    """Alpha-blend fg onto bg, a in [0, 1]."""
    return tuple(int(bg[i] + (fg[i] - bg[i]) * a) for i in range(3))


class SplashScreen:
    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int, on_done):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.on_done = on_done
        self._image  = draw._image   # underlying PIL Image for compositing

        self.start_time = time.time()
        self.done = False

        self._init_fonts()
        self._measure()

    # ── Setup ──────────────────────────────────────────────────────────────────

    def _init_fonts(self):
        candidates = [
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            ("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
             "/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ]
        self.font_large = ImageFont.load_default()
        self.font_small = ImageFont.load_default()
        for bold, regular in candidates:
            try:
                self.font_large = ImageFont.truetype(bold,    46)
                self.font_small = ImageFont.truetype(regular, 11)
                break
            except Exception:
                continue

    def _textsize(self, text, font):
        try:
            bb = self.draw.textbbox((0, 0), text, font=font)
            return bb[2] - bb[0], bb[3] - bb[1]
        except AttributeError:
            return self.draw.textsize(text, font=font)

    def _measure(self):
        w, h = self.width, self.height
        self.title = "JMO 3.0"
        self.sub   = "your personal display"

        tw, th = self._textsize(self.title, self.font_large)
        sw, _  = self._textsize(self.sub,   self.font_small)

        self.tx, self.ty = (w - tw) // 2, (h - th) // 2 - 10
        self.tw, self.th = tw, th

        self.sx = (w - sw) // 2
        self.sy = self.ty + th + 18

        # Underline geometry
        self.ul_y  = self.ty + th + 6
        self.ul_x0 = self.tx
        self.ul_x1 = self.tx + tw

        # Dot pulse row
        self.dot_y = self.sy + 22

    # ── Drawing helpers ────────────────────────────────────────────────────────

    def _stamp(self, text, x, y, font, color, alpha):
        """Composite text onto the main buffer via an RGBA scratch surface."""
        if alpha <= 0.0:
            return
        tw, th = self._textsize(text, font)
        if tw <= 0 or th <= 0:
            return
        pad  = 4
        surf = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        d    = ImageDraw.Draw(surf)
        d.text((pad, pad), text, font=font, fill=(*color, int(alpha * 255)))
        self._image.paste(surf, (x - pad, y - pad), surf)

    def _glow(self, text, x, y, font, color, alpha, spread=6):
        """Soft glow by stamping dim offset copies."""
        if alpha <= 0.0:
            return
        ga = alpha * 0.15
        for dx, dy in [(-spread, 0), (spread, 0), (0, -spread), (0, spread),
                       (-spread, -spread), (spread, spread),
                       (-spread//2, spread), (spread//2, -spread)]:
            self._stamp(text, x + dx, y + dy, font, color, ga)

    # ── Public interface ───────────────────────────────────────────────────────

    def update(self):
        if not self.done and (time.time() - self.start_time) >= T_DONE:
            self.done = True
            self.on_done()

    def render(self):
        if self.done:
            return

        elapsed = time.time() - self.start_time
        w, h    = self.width, self.height
        BG      = (8, 8, 18)

        # ── Global fade-out alpha ──────────────────────────────────────────────
        ga = 1.0 - _phase(T_FADE_OUT, T_DONE, elapsed)   # 1 → 0

        # ── Background + cheap vignette ────────────────────────────────────────
        self.draw.rectangle((0, 0, w, h), fill=BG)
        for row in range(0, h, 2):
            dist = abs(row - h / 2) / (h / 2)
            dim  = int(dist * 10)
            c    = (_clamp(BG[0] - dim, 0, 255),
                    _clamp(BG[1] - dim, 0, 255),
                    _clamp(BG[2] - dim + 5, 0, 255))
            self.draw.line([(0, row), (w, row)], fill=c)

        # ── Title ─────────────────────────────────────────────────────────────
        ta = _phase(T_FADE_IN, T_HOLD, elapsed) * ga

        # Glow (cool blue-white)
        self._glow (self.title, self.tx, self.ty, self.font_large, (140, 190, 255), ta)
        # Text (white)
        self._stamp(self.title, self.tx, self.ty, self.font_large, (255, 255, 255), ta)

        # ── Accent underline sweep ─────────────────────────────────────────────
        lp = _phase(T_LINE, T_LINE + 0.45, elapsed) * ga
        if lp > 0:
            x1 = int(self.ul_x0 + (self.ul_x1 - self.ul_x0) * lp)
            ACCENT = (255, 90, 115)
            self.draw.line(
                [(self.ul_x0, self.ul_y), (x1, self.ul_y)],
                fill=_blend(ACCENT, BG, ga), width=2)
            self.draw.line(
                [(self.ul_x0, self.ul_y + 2), (x1, self.ul_y + 2)],
                fill=_blend((160, 50, 70), BG, ga * 0.35), width=1)

        # ── Subtitle ───────────────────────────────────────────────────────────
        sa = _phase(T_SUB, T_SUB + 0.5, elapsed) * ga
        self._stamp(self.sub, self.sx, self.sy, self.font_small, (155, 165, 200), sa)

        # ── Dot-pulse loader ───────────────────────────────────────────────────
        if sa > 0:
            t0 = elapsed - T_SUB
            for i in range(3):
                phase = (t0 / 0.9 - i * 0.3) % 1.0
                dot_a = _clamp(math.sin(phase * math.pi)) * sa
                cx    = w // 2 - 10 + i * 10
                r     = 2
                c     = _blend((220, 90, 115), BG, dot_a)
                self.draw.ellipse((cx - r, self.dot_y - r,
                                   cx + r, self.dot_y + r), fill=c)