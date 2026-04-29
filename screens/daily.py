#!/usr/bin/env python3
import json
import time
import threading
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
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

# Palette
BG_TOP  = (13,  17,  46)   # deep indigo
BG_BOT  = ( 7,   9,  22)   # near-black
WHITE   = (255, 255, 255)
MUTED   = ( 98, 116, 168)   # slate-blue secondary
SEP     = ( 28,  36,  68)   # barely-visible divider
NOTE_C  = (162, 175, 212)   # note text

ICON_SIZE = (80, 80)

# WMO code → asset name (day / night variants)
def _icon_name(code, hour):
    night = not (6 <= hour < 20)
    if code == 0:   return "clear_night" if night else "sunny"
    if code <= 2:   return "partly_night" if night else "partly"
    if code == 3:   return "partly_night" if night else "partly"
    if code <= 48:  return "foggy"
    if code <= 65:  return "rainy"
    if code <= 77:  return "snowy"
    if code <= 82:  return "rainy"
    if code <= 94:  return "snowy"
    return                  "thunder"

def _wmo_label(code):
    if code == 0:   return "Clear"
    if code <= 2:   return "Mostly clear"
    if code == 3:   return "Overcast"
    if code <= 48:  return "Foggy"
    if code <= 55:  return "Drizzle"
    if code <= 65:  return "Rain"
    if code <= 77:  return "Snow"
    if code <= 82:  return "Showers"
    if code <= 94:  return "Snow showers"
    return                  "Thunderstorm"


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

        self._f_date = self._font(10)
        self._f_time = self._font_bold(50)
        self._f_temp = self._font_bold(34)
        self._f_unit = self._font(17)
        self._f_cond = self._font(12)
        self._f_note = self._font(11)

        self._bg    = self._make_gradient()
        self._icons = self._load_icons()

        self._trigger_fetch()

    # ── Setup ─────────────────────────────────────────────────────────────────

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

    def _make_gradient(self):
        img = Image.new("RGB", (self.width, self.height))
        d   = ImageDraw.Draw(img)
        for y in range(self.height):
            t = y / (self.height - 1)
            r = int(BG_TOP[0] + t * (BG_BOT[0] - BG_TOP[0]))
            g = int(BG_TOP[1] + t * (BG_BOT[1] - BG_TOP[1]))
            b = int(BG_TOP[2] + t * (BG_BOT[2] - BG_TOP[2]))
            d.line((0, y, self.width, y), fill=(r, g, b))
        return img

    def _load_icons(self):
        names = ["sunny", "clear_night", "partly", "partly_night",
                 "foggy", "rainy", "snowy", "thunder"]
        icons = {}
        for name in names:
            try:
                img = Image.open(f"assets/weather/{name}.png").convert("RGBA")
                icons[name] = img.resize(ICON_SIZE, Image.LANCZOS)
            except Exception as e:
                print(f"[Daily] Icon '{name}' not loaded: {e}")
        return icons

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
            print(f"[Daily] Weather: code={code} temp={temp}")
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
            bb = self.draw.textbbox((0, 0), "0", font=font)
            return bb[3] - bb[1]
        except AttributeError:
            _, h = self.draw.textsize("0", font=font)
            return h

    def render(self):
        w, h   = self.width, self.height
        d, now = self.draw, datetime.now()
        MX     = 16   # left margin

        # ── Background gradient ───────────────────────────────────────────────
        self.draw._image.paste(self._bg, (0, 0))

        with self._wlock:
            code, temp = self._wcode, self._wtemp

        has_note  = bool(self._note)
        NOTE_ZONE = 36   # pixels reserved at bottom when note exists

        # ── Date header ───────────────────────────────────────────────────────
        date_str = now.strftime("%A · %-d %B")
        d.text((MX, 10), date_str, font=self._f_date, fill=MUTED)

        # ── Time (hero) ───────────────────────────────────────────────────────
        time_str = now.strftime("%H:%M")
        TIME_Y   = 22
        d.text((MX, TIME_Y), time_str, font=self._f_time, fill=WHITE)
        time_h = self._th(self._f_time)

        # ── Weather icon (right, vertically centred in upper ~60% of screen) ──
        upper_h  = h - NOTE_ZONE if has_note else h
        icon_y   = max(14, (upper_h - ICON_SIZE[1]) // 2 - 8)
        icon_x   = w - ICON_SIZE[0] - 14

        if code is not None:
            name = _icon_name(code, now.hour)
            icon = self._icons.get(name)
            if icon:
                self.draw._image.paste(icon, (icon_x, icon_y), icon)

        # ── Temperature ───────────────────────────────────────────────────────
        TEMP_Y  = TIME_Y + time_h + 14
        unit    = self._config.get("weather", {}).get("unit", "celsius")
        unit_ch = "C" if unit == "celsius" else "F"

        if temp is not None:
            num_str = f"{temp:.0f}°"
            d.text((MX, TEMP_Y), num_str, font=self._f_temp, fill=WHITE)
            nw = self._tw(num_str, self._f_temp)
            # Smaller unit char, top-aligned with number
            d.text((MX + nw + 2, TEMP_Y + 4), unit_ch,
                   font=self._f_unit, fill=MUTED)
            cond_y = TEMP_Y + self._th(self._f_temp) + 6
        else:
            d.text((MX, TEMP_Y + 8), "—", font=self._f_temp, fill=MUTED)
            cond_y = TEMP_Y + 42

        # ── Condition label ───────────────────────────────────────────────────
        if code is not None:
            d.text((MX, cond_y), _wmo_label(code), font=self._f_cond, fill=MUTED)
        elif temp is None:
            d.text((MX, cond_y), "Fetching weather…", font=self._f_cond, fill=MUTED)

        # ── Note ─────────────────────────────────────────────────────────────
        if has_note:
            sep_y  = h - NOTE_ZONE
            note_h = self._th(self._f_note)
            note_y = sep_y + (NOTE_ZONE - note_h) // 2

            d.line((MX, sep_y, w - MX, sep_y), fill=SEP, width=1)

            nw = self._tw(self._note, self._f_note)
            d.text((max(MX, (w - nw) // 2), note_y),
                   self._note, font=self._f_note, fill=NOTE_C)
