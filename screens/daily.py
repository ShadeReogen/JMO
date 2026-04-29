#!/usr/bin/env python3
"""
DailyScreen — redesigned for 320×240 Display HAT Mini.

Layout (all values in px, origin top-left):
  ┌─────────────────────────────────────────┐  y=0
  │  TOP BAR  city · · · · · · · · time/date│  h=38
  ├─────────────────────────────────────────┤  y=38
  │                                         │
  │   [ICON 72×72]   TEMP   condition       │  h=146
  │                                         │
  ├─────────────────────────────────────────┤  y=184
  │  NOTE (italic, truncated)          [Y]  │  h=56
  └─────────────────────────────────────────┘  y=240

Nothing bleeds outside 320×240. Icon is always fully inside the middle zone.
"""

import json
import time
import threading
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from displayhatmini import DisplayHATMini

# ── Paths ──────────────────────────────────────────────────────────────────────
CONFIG_PATH    = "config.json"
NOTES_PATH     = "notes.json"

# ── Timing ─────────────────────────────────────────────────────────────────────
FETCH_INTERVAL = 600          # seconds between weather refreshes

# ── Weather API ────────────────────────────────────────────────────────────────
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,weather_code"
    "&temperature_unit={unit}"
)

# ── Buttons ────────────────────────────────────────────────────────────────────
BUTTON_NAMES = {
    DisplayHATMini.BUTTON_A: "A",
    DisplayHATMini.BUTTON_B: "B",
    DisplayHATMini.BUTTON_X: "X",
    DisplayHATMini.BUTTON_Y: "Y",
}

# ── Palette ────────────────────────────────────────────────────────────────────
BG            = ( 11,  15,  28)   # deep navy
DIVIDER       = ( 40,  46,  68)   # subtle separator
WHITE         = (255, 255, 255)
TEXT_PRIMARY  = (255, 255, 255)
TEXT_DIM      = (140, 152, 190)   # secondary / muted blue-white
TEXT_FAINT    = ( 82,  96, 130)   # very muted (unit symbol, hints)
ACCENT        = (255, 209, 102)   # warm amber — used for icon tint fallback

# ── Layout constants (all pixels) ─────────────────────────────────────────────
W, H          = 320, 240

TOP_H         = 38    # top bar height
BTM_H         = 56    # bottom bar height
MID_Y         = TOP_H                          #  38
MID_H         = H - TOP_H - BTM_H             # 146
MID_CY        = MID_Y + MID_H // 2            # vertical centre of middle zone

PAD_X         = 16    # horizontal padding from screen edges

ICON_SIZE     = 72    # rendered icon size (down-sampled from 512×512 source)
ICON_X        = PAD_X
ICON_Y        = MID_Y + (MID_H - ICON_SIZE) // 2   # vertically centred

TEMP_X        = ICON_X + ICON_SIZE + 14       # left edge of temperature text

# Font sizes
FS_LABEL      = 11
FS_TEMP       = 54    # large temperature numeral
FS_UNIT       = 22    # °C / °F superscript
FS_COND       = 13    # weather condition label
FS_NOTE       = 11


# ── Weather helpers ────────────────────────────────────────────────────────────

def _wmo_label(code: int) -> str:
    if code == 0:   return "Clear sky"
    if code <= 2:   return "Mostly clear"
    if code == 3:   return "Overcast"
    if code <= 48:  return "Foggy"
    if code <= 55:  return "Drizzle"
    if code <= 65:  return "Rainy"
    if code <= 77:  return "Snowy"
    if code <= 82:  return "Showers"
    if code <= 94:  return "Snow showers"
    return                  "Thunderstorm"


def _icon_name(code: int, hour: int) -> str:
    night = not (6 <= hour < 20)
    if code == 0:   return "clear_night" if night else "sunny"
    if code <= 3:   return "partly_night" if night else "partly"
    if code <= 48:  return "foggy"
    if code <= 65:  return "rainy"
    if code <= 77:  return "snowy"
    if code <= 82:  return "rainy"
    if code <= 94:  return "snowy"
    return                  "thunder"


def _resize(img: Image.Image, size: tuple) -> Image.Image:
    try:
        return img.resize(size, Image.LANCZOS)
    except AttributeError:
        return img.resize(size, Image.ANTIALIAS)


# ── Font helpers ───────────────────────────────────────────────────────────────

_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(paths: list, size: int) -> ImageFont.ImageFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ── Text measurement helpers ───────────────────────────────────────────────────

def _tw(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Text width in pixels."""
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    except AttributeError:
        w, _ = draw.textsize(text, font=font)
        return w


def _th(draw: ImageDraw.ImageDraw, font) -> int:
    """Approximate cap-height for vertical alignment."""
    try:
        bb = draw.textbbox((0, 0), "0", font=font)
        return bb[3] - bb[1]
    except AttributeError:
        _, h = draw.textsize("0", font=font)
        return h


def _truncate(draw: ImageDraw.ImageDraw, text: str, font,
              max_w: int) -> str:
    """Truncate text with ellipsis so it fits within max_w pixels."""
    if _tw(draw, text, font) <= max_w:
        return text
    while text:
        text = text[:-1]
        if _tw(draw, text + "…", font) <= max_w:
            return text + "…"
    return "…"


# ── Main screen class ──────────────────────────────────────────────────────────

class DailyScreen:
    """
    Renders a clean weather + date/time + daily note screen
    strictly within 320×240 px.
    """

    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        display: DisplayHATMini,
        on_done,
    ):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.display = display
        self.on_done = on_done

        self._prev = {btn: False for btn in BUTTON_NAMES}

        # Config + note
        self._config  = self._load_config()
        self._note    = self._load_note()

        # Weather state (thread-safe)
        self._wcode      = None
        self._wtemp      = None
        self._wlock      = threading.Lock()
        self._fetching   = False
        self._last_fetch = 0.0

        # Fonts
        self._f_label = _load_font(_REGULAR_PATHS, FS_LABEL)
        self._f_temp  = _load_font(_BOLD_PATHS,    FS_TEMP)
        self._f_unit  = _load_font(_REGULAR_PATHS, FS_UNIT)
        self._f_cond  = _load_font(_REGULAR_PATHS, FS_COND)
        self._f_note  = _load_font(_REGULAR_PATHS, FS_NOTE)

        # Icons
        self._icons = self._load_icons()

        # Kick off first fetch
        self._trigger_fetch()

    # ── Config / notes ─────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            return {"weather": {"lat": 40.8197, "lon": 14.3411, "unit": "celsius"}}

    def _load_note(self) -> str | None:
        try:
            with open(NOTES_PATH) as f:
                data = json.load(f)
            today = datetime.now().strftime("%m-%d")
            for entry in data.get("notes", []):
                if entry.get("date") == today:
                    return entry.get("text", "").strip() or None
        except Exception as e:
            print(f"[Daily] Note load failed: {e}")
        return None

    # ── Icons ──────────────────────────────────────────────────────────────────

    def _load_icons(self) -> dict:
        names = [
            "sunny", "clear_night", "partly", "partly_night",
            "foggy", "rainy", "snowy", "thunder",
        ]
        icons: dict = {}
        size = (ICON_SIZE, ICON_SIZE)
        for name in names:
            try:
                img = Image.open(f"assets/weather/{name}.png").convert("RGBA")
                icons[name] = _resize(img, size)
            except Exception as e:
                print(f"[Daily] Icon '{name}' not loaded: {e}")
        return icons

    # ── Weather fetch ──────────────────────────────────────────────────────────

    def _trigger_fetch(self):
        if self._fetching:
            return
        self._fetching   = True
        self._last_fetch = time.time()
        threading.Thread(target=self._fetch_weather, daemon=True).start()

    def _fetch_weather(self):
        try:
            cfg  = self._config.get("weather", {})
            lat  = cfg.get("lat",  40.8197)
            lon  = cfg.get("lon",  14.3411)
            unit = cfg.get("unit", "celsius")
            url  = WEATHER_URL.format(lat=lat, lon=lon, unit=unit)
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            code = int(data["current"]["weather_code"])
            temp = float(data["current"]["temperature_2m"])
            with self._wlock:
                self._wcode = code
                self._wtemp = temp
            print(f"[Daily] Weather: code={code} temp={temp}")
        except Exception as e:
            print(f"[Daily] Weather fetch failed: {e}")
        finally:
            self._fetching = False

    # ── Input ──────────────────────────────────────────────────────────────────

    def update(self):
        for btn, name in BUTTON_NAMES.items():
            pressed = self.display.read_button(btn)
            if pressed and not self._prev[btn]:
                self._on_press(name)
            self._prev[btn] = pressed

        if not self._fetching and time.time() - self._last_fetch > FETCH_INTERVAL:
            self._trigger_fetch()

    def _on_press(self, name: str):
        if name == "Y":
            self.on_done()

    # ── Render ─────────────────────────────────────────────────────────────────

    def render(self):
        d   = self.draw
        buf = d._image          # underlying PIL Image for paste()
        now = datetime.now()

        with self._wlock:
            code, temp = self._wcode, self._wtemp

        # ── Background ────────────────────────────────────────────────────────
        d.rectangle((0, 0, W, H), fill=BG)

        # ── TOP BAR (y 0–38) ──────────────────────────────────────────────────
        # City label (left)
        cfg      = self._config.get("weather", {})
        city     = cfg.get("city", "")
        if city:
            city_str = city.upper()
            d.text((PAD_X, 12), city_str, font=self._f_label, fill=TEXT_DIM)

        # Date + time (right-aligned)
        dt_str = now.strftime("%H:%M  ·  %a %-d %b").upper()
        dt_w   = _tw(d, dt_str, self._f_label)
        d.text((W - PAD_X - dt_w, 12), dt_str, font=self._f_label, fill=TEXT_FAINT)

        # Divider
        d.line((0, TOP_H, W, TOP_H), fill=DIVIDER)

        # ── MIDDLE ZONE (y 38–184) ────────────────────────────────────────────

        # Weather icon — always within ICON_X, ICON_Y, clipped to 72×72
        if code is not None:
            icon = self._icons.get(_icon_name(code, now.hour))
            if icon:
                buf.paste(icon, (ICON_X, ICON_Y), icon)

        # Temperature numeral
        unit_key = cfg.get("unit", "celsius")
        unit_str = "°C" if unit_key == "celsius" else "°F"

        temp_str   = f"{temp:.0f}" if temp is not None else "—"
        temp_h     = _th(d, self._f_temp)
        temp_y     = MID_CY - temp_h // 2

        d.text((TEMP_X, temp_y), temp_str, font=self._f_temp, fill=TEXT_PRIMARY)

        # Unit symbol — top-right of the numeral, smaller & dimmer
        num_w   = _tw(d, temp_str, self._f_temp)
        unit_x  = TEMP_X + num_w + 3
        unit_y  = temp_y + 6          # slight vertical offset looks better
        d.text((unit_x, unit_y), unit_str, font=self._f_unit, fill=TEXT_FAINT)

        # Condition label — below temperature
        cond_str = _wmo_label(code) if code is not None else "Loading…"
        cond_y   = temp_y + temp_h + 6
        d.text((TEMP_X, cond_y), cond_str, font=self._f_cond, fill=TEXT_DIM)

        # ── BOTTOM BAR (y 184–240) ────────────────────────────────────────────
        BTM_Y = H - BTM_H
        d.line((0, BTM_Y, W, BTM_Y), fill=DIVIDER)

        # Button hint [Y] — right side
        btn_label = "Y"
        btn_w     = 18
        btn_x     = W - PAD_X - btn_w
        btn_cy    = BTM_Y + BTM_H // 2
        d.rounded_rectangle(
            (btn_x, btn_cy - 9, btn_x + btn_w, btn_cy + 9),
            radius=4,
            outline=TEXT_FAINT,
        )
        bw = _tw(d, btn_label, self._f_label)
        d.text(
            (btn_x + (btn_w - bw) // 2, btn_cy - _th(d, self._f_label) // 2),
            btn_label, font=self._f_label, fill=TEXT_FAINT,
        )

        # Note text — left side, truncated to avoid the button
        note_text = self._note if self._note else ""
        if note_text:
            max_note_w = btn_x - PAD_X - 8
            note_str   = _truncate(d, note_text, self._f_note, max_note_w)
            note_h     = _th(d, self._f_note)
            note_y     = BTM_Y + (BTM_H - note_h) // 2
            d.text((PAD_X, note_y), note_str, font=self._f_note, fill=TEXT_DIM)