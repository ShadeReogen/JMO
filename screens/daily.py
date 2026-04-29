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
FETCH_INTERVAL = 600  # seconds between weather refreshes

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

BG      = (8,   8,  18)
C_WHITE = (230, 230, 240)
C_DIM   = (110, 110, 130)
C_CYAN  = (0,  210, 255)
C_WARM  = (255, 170,  50)
C_NOTE  = (190, 180, 150)
C_DIV   = (40,  40,  70)
C_CLOUD = (190, 190, 210)
C_SUN   = (255, 210,   0)
C_RAIN  = ( 80, 140, 255)
C_SNOW  = (200, 220, 255)
C_STORM = (200, 200, 100)
C_FOG   = (150, 150, 170)


# ── WMO weather codes ─────────────────────────────────────────────────────────

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


# ── Icon drawing primitives ───────────────────────────────────────────────────

def _sun(d, cx, cy, r=15):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=C_SUN)
    for deg in range(0, 360, 45):
        rad = math.radians(deg)
        x1 = cx + (r + 3) * math.cos(rad)
        y1 = cy + (r + 3) * math.sin(rad)
        x2 = cx + (r + 9) * math.cos(rad)
        y2 = cy + (r + 9) * math.sin(rad)
        d.line(((x1, y1), (x2, y2)), fill=C_SUN, width=2)


def _cloud(d, cx, cy, w=40, fill=C_CLOUD):
    bh = w // 2
    br = bh // 2
    d.ellipse((cx - w // 2, cy - br, cx + w // 2, cy + br), fill=fill)
    d.ellipse((cx - w // 4 - br, cy - bh, cx - w // 4 + br, cy), fill=fill)
    d.ellipse((cx + w // 8 - br, cy - bh - br // 2, cx + w // 8 + br, cy - br // 2), fill=fill)


def _rain(d, cx, cy, n=5):
    for i in range(n):
        x  = cx + (i - n // 2) * 8
        yo = (i % 2) * 4
        d.line(((x, cy + yo), (x - 4, cy + yo + 10)), fill=C_RAIN, width=2)


def _snow(d, cx, cy, n=6):
    for i in range(n):
        x = cx + (i - n // 2) * 8 + (i % 2) * 3
        y = cy + (i % 2) * 6
        d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=C_SNOW)


def _fog(d, cx, cy, w=44):
    for i, frac in enumerate((1.0, 0.65, 0.85, 0.55)):
        lw = int(w * frac)
        y  = cy + i * 8 - 12
        d.line(((cx - lw // 2, y), (cx + lw // 2, y)), fill=C_FOG, width=2)


def _lightning(d, cx, cy):
    pts = [(cx + 4, cy - 12), (cx - 3, cy + 1), (cx + 3, cy + 1), (cx - 5, cy + 14)]
    d.polygon(pts, fill=C_STORM)


def _draw_icon(d, cx, cy, kind):
    if kind == "sun":
        _sun(d, cx, cy)
    elif kind == "partly_cloudy":
        _sun(d, cx - 10, cy - 9, r=10)
        _cloud(d, cx + 5, cy + 5, w=30)
    elif kind == "cloud":
        _cloud(d, cx, cy)
    elif kind == "fog":
        _fog(d, cx, cy)
    elif kind in ("drizzle", "rain"):
        _cloud(d, cx, cy - 9, w=40)
        _rain(d, cx, cy + 9, n=4 if kind == "drizzle" else 5)
    elif kind == "snow":
        _cloud(d, cx, cy - 9, w=40)
        _snow(d, cx, cy + 9)
    elif kind == "storm":
        _cloud(d, cx, cy - 10, w=40, fill=(120, 120, 140))
        _lightning(d, cx, cy + 6)


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

        self._font_day  = self._font(12)
        self._font_date = self._font(13)
        self._font_time = self._font_bold(46)
        self._font_temp = self._font_bold(20)
        self._font_desc = self._font(11)
        self._font_note = self._font(12)

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

    def render(self):
        w, h   = self.width, self.height
        d, now = self.draw, datetime.now()

        d.rectangle((0, 0, w, h), fill=BG)

        # ── Date & time ───────────────────────────────────────────────────────
        day_str  = now.strftime("%A")
        date_str = now.strftime("%-d %B %Y")
        time_str = now.strftime("%H:%M")

        dw = self._tw(day_str, self._font_day)
        d.text(((w - dw) // 2, 6), day_str, font=self._font_day, fill=C_DIM)

        dtw = self._tw(date_str, self._font_date)
        d.text(((w - dtw) // 2, 22), date_str, font=self._font_date, fill=C_WHITE)

        timew = self._tw(time_str, self._font_time)
        d.text(((w - timew) // 2, 42), time_str, font=self._font_time, fill=C_CYAN)

        # ── Weather ───────────────────────────────────────────────────────────
        with self._wlock:
            code, temp = self._wcode, self._wtemp

        # Icon centered left-of-center; temp+desc text to the right
        icon_cx = w // 2 - 55
        icon_cy = 148
        text_x  = w // 2 + 10

        if code is not None:
            label, kind = _wmo_info(code)
            _draw_icon(d, icon_cx, icon_cy, kind)

            unit_sym = "°C" if self._config.get("weather", {}).get("unit") == "celsius" else "°F"
            temp_str = f"{temp:.0f}{unit_sym}"
            d.text((text_x, icon_cy - 18), temp_str, font=self._font_temp, fill=C_WARM)
            d.text((text_x, icon_cy +  6), label,    font=self._font_desc, fill=C_DIM)
        else:
            msg = "Fetching weather..."
            mw  = self._tw(msg, self._font_desc)
            d.text(((w - mw) // 2, icon_cy - 6), msg, font=self._font_desc, fill=C_DIM)

        # ── Note ─────────────────────────────────────────────────────────────
        if self._note:
            note_y = h - 35
            d.line((10, note_y - 6, w - 10, note_y - 6), fill=C_DIV, width=1)
            nw = self._tw(self._note, self._font_note)
            d.text((max(8, (w - nw) // 2), note_y), self._note,
                   font=self._font_note, fill=C_NOTE)
