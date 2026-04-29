#!/usr/bin/env python3
import json
import math
import time
import threading
import urllib.request
from datetime import datetime
from PIL import ImageDraw, ImageFont
from displayhatmini import DisplayHATMini

CONFIG_PATH    = "config.json"
NOTES_PATH     = "notes.json"
FETCH_INTERVAL = 600

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,weather_code"
    "&temperature_unit={unit}"
)

BUTTON_NAMES = {
    DisplayHATMini.BUTTON_A: "A",
    DisplayHATMini.BUTTON_B: "B",
    DisplayHATMini.BUTTON_X: "X",
    DisplayHATMini.BUTTON_Y: "Y",
}

AMBER     = (215, 148,  18)   # card background
AMBER_DRK = (170, 112,   8)   # note strip
WHITE     = (255, 255, 255)   # primary text / icons
OFF_WHITE = (245, 232, 195)   # secondary text
RAIN_TINT = (170, 215, 255)   # rain drops (only colour accent on amber)


# ── WMO codes ─────────────────────────────────────────────────────────────────

def _wmo_info(code):
    if code == 0:  return "Clear",         "sun"
    if code <= 2:  return "Partly cloudy", "partly_cloudy"
    if code == 3:  return "Overcast",      "cloud"
    if code <= 48: return "Foggy",         "fog"
    if code <= 55: return "Drizzle",       "drizzle"
    if code <= 65: return "Rain",          "rain"
    if code <= 77: return "Snow",          "snow"
    if code <= 82: return "Showers",       "rain"
    if code <= 94: return "Snow showers",  "snow"
    return                "Thunderstorm",  "storm"


# ── Icon primitives — all white/single-tint for legibility on amber ───────────

def _p_sun(d, cx, cy, r=26, c=WHITE):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
    for deg in range(0, 360, 45):
        rad = math.radians(deg)
        x1 = cx + (r + 4) * math.cos(rad)
        y1 = cy + (r + 4) * math.sin(rad)
        x2 = cx + (r + 13) * math.cos(rad)
        y2 = cy + (r + 13) * math.sin(rad)
        d.line(((x1, y1), (x2, y2)), fill=c, width=3)


def _p_cloud(d, cx, cy, w=54, c=WHITE):
    bh = w // 2
    br = bh // 2
    d.ellipse((cx - w // 2, cy - br,         cx + w // 2, cy + br),         fill=c)
    d.ellipse((cx - w // 4 - br, cy - bh,    cx - w // 4 + br, cy),         fill=c)
    d.ellipse((cx + w // 8 - br, cy - bh - br // 2,
               cx + w // 8 + br, cy - br // 2),                             fill=c)


def _p_rain(d, cx, cy, n=5, c=RAIN_TINT):
    for i in range(n):
        x  = cx + (i - n // 2) * 10
        yo = (i % 2) * 5
        d.line(((x, cy + yo), (x - 5, cy + yo + 13)), fill=c, width=2)


def _p_snow(d, cx, cy, n=6, c=WHITE):
    for i in range(n):
        x = cx + (i - n // 2) * 10 + (i % 2) * 4
        y = cy + (i % 2) * 8
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=c)


def _p_fog(d, cx, cy, w=56, c=OFF_WHITE):
    for i, frac in enumerate((1.0, 0.60, 0.82, 0.50)):
        lw = int(w * frac)
        y  = cy + i * 10 - 15
        d.line(((cx - lw // 2, y), (cx + lw // 2, y)), fill=c, width=3)


def _p_lightning(d, cx, cy, c=WHITE):
    pts = [(cx + 5, cy - 14), (cx - 4, cy + 2), (cx + 5, cy + 2), (cx - 6, cy + 17)]
    d.polygon(pts, fill=c)


def _draw_icon(d, cx, cy, kind):
    if kind == "sun":
        _p_sun(d, cx, cy)
    elif kind == "partly_cloudy":
        # Draw sun first; cloud overlaps, leaving rays visible at edges
        _p_sun(d, cx - 14, cy - 12, r=18)
        _p_cloud(d, cx + 10, cy + 8, w=40)
    elif kind == "cloud":
        _p_cloud(d, cx, cy)
    elif kind == "fog":
        _p_fog(d, cx, cy)
    elif kind in ("drizzle", "rain"):
        _p_cloud(d, cx, cy - 12, w=50)
        _p_rain(d, cx, cy + 12, n=4 if kind == "drizzle" else 5)
    elif kind == "snow":
        _p_cloud(d, cx, cy - 12, w=50)
        _p_snow(d, cx, cy + 12)
    elif kind == "storm":
        _p_cloud(d, cx, cy - 14, w=50, c=OFF_WHITE)
        _p_lightning(d, cx, cy + 6)


# ── Screen ────────────────────────────────────────────────────────────────────

class DailyScreen:
    def __init__(self, draw: ImageDraw.ImageDraw, width: int, height: int,
                 display: DisplayHATMini, on_done):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.display = display
        self.on_done = on_done

        self._prev = {btn: False for btn in BUTTON_NAMES}

        self._config = self._load_config()
        self._note   = self._load_note()

        self._wcode    = None
        self._wtemp    = None
        self._wlock    = threading.Lock()
        self._fetching = False
        self._last_fetch = 0.0

        self._f_header = self._font(11)
        self._f_temp   = self._font_bold(58)
        self._f_unit   = self._font_bold(22)   # °C superscript beside number
        self._f_cond   = self._font(14)
        self._f_note   = self._font(11)

        self._trigger_fetch()

    # ── Loaders ───────────────────────────────────────────────────────────────

    def _load_config(self):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            return {"weather": {"lat": 40.8197, "lon": 14.3411, "unit": "celsius"}}

    def _load_note(self):
        try:
            with open(NOTES_PATH) as f:
                data = json.load(f)
            today = datetime.now().strftime("%m-%d")
            for entry in data.get("notes", []):
                if entry.get("date") == today:
                    return entry.get("text", "").strip()
        except Exception as e:
            print(f"[Daily] Note load failed: {e}")
        return None

    def _font(self, size):
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _font_bold(self, size):
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return self._font(size)

    # ── Weather fetch ─────────────────────────────────────────────────────────

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
            print(f"[Daily] Weather fetched: code={code} temp={temp}")
        except Exception as e:
            print(f"[Daily] Weather fetch failed: {e}")
        finally:
            self._fetching = False

    # ── Input ─────────────────────────────────────────────────────────────────

    def update(self):
        for btn, name in BUTTON_NAMES.items():
            pressed = self.display.read_button(btn)
            if pressed and not self._prev[btn]:
                self._on_press(name)
            self._prev[btn] = pressed

        if not self._fetching and time.time() - self._last_fetch > FETCH_INTERVAL:
            self._trigger_fetch()

    def _on_press(self, name):
        if name == "Y":
            self.on_done()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _tw(self, text, font):
        try:
            bb = self.draw.textbbox((0, 0), text, font=font)
            return bb[2] - bb[0]
        except AttributeError:
            w, _ = self.draw.textsize(text, font=font)
            return w

    def _th(self, font):
        try:
            bb = self.draw.textbbox((0, 0), "Ag", font=font)
            return bb[3] - bb[1]
        except AttributeError:
            _, h = self.draw.textsize("Ag", font=font)
            return h

    def render(self):
        w, h   = self.width, self.height
        d, now = self.draw, datetime.now()

        NOTE_H   = 40
        has_note = bool(self._note)
        card_h   = h - NOTE_H if has_note else h

        # ── Backgrounds ───────────────────────────────────────────────────────
        d.rectangle((0, 0, w, h), fill=AMBER)
        if has_note:
            d.rectangle((0, h - NOTE_H, w, h), fill=AMBER_DRK)

        MARGIN = 14

        # ── Header: day+date left, time right ─────────────────────────────────
        day_str  = now.strftime("%A, %-d %B")
        time_str = now.strftime("%H:%M")
        d.text((MARGIN, 10), day_str,  font=self._f_header, fill=OFF_WHITE)
        tw = self._tw(time_str, self._f_header)
        d.text((w - MARGIN - tw, 10), time_str, font=self._f_header, fill=OFF_WHITE)

        # ── Temperature (large, left-aligned) ─────────────────────────────────
        with self._wlock:
            code, temp = self._wcode, self._wtemp

        unit_sym = "°C" if self._config.get("weather", {}).get("unit") == "celsius" else "°F"

        TEMP_Y = 36
        if temp is not None:
            num_str = f"{temp:.0f}"
            num_w   = self._tw(num_str, self._f_temp)
            num_h   = self._th(self._f_temp)
            d.text((MARGIN, TEMP_Y), num_str, font=self._f_temp, fill=WHITE)
            # Unit as smaller superscript to the right of the number
            d.text((MARGIN + num_w + 3, TEMP_Y + 8), unit_sym,
                   font=self._f_unit, fill=WHITE)
            cond_y = TEMP_Y + num_h + 2
        else:
            d.text((MARGIN, TEMP_Y + 16), "—", font=self._f_temp, fill=WHITE)
            cond_y = TEMP_Y + 58

        # ── Condition label ───────────────────────────────────────────────────
        if code is not None:
            label, _ = _wmo_info(code)
            d.text((MARGIN, cond_y), label, font=self._f_cond, fill=OFF_WHITE)
        elif temp is None:
            d.text((MARGIN, cond_y), "Fetching…", font=self._f_cond, fill=OFF_WHITE)

        # ── Icon (right side, centred vertically in card area) ────────────────
        icon_x = w - 78
        icon_y = card_h // 2 + 10
        if code is not None:
            _, kind = _wmo_info(code)
            _draw_icon(d, icon_x, icon_y, kind)

        # ── Note strip ────────────────────────────────────────────────────────
        if has_note:
            note_h  = self._th(self._f_note)
            note_y  = h - NOTE_H + (NOTE_H - note_h) // 2
            nw      = self._tw(self._note, self._f_note)
            d.text((max(MARGIN, (w - nw) // 2), note_y),
                   self._note, font=self._f_note, fill=OFF_WHITE)
