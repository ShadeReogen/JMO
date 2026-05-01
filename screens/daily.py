import json
import time
import threading
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from displayhatmini import DisplayHATMini

CONFIG_PATH    = "config.json"
NOTES_PATH     = "notes.json"
BG_PATH        = "assets/weather/bg.jpg"

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

WHITE        = (255, 255, 255)
TEXT_PRIMARY = (255, 255, 255)
TEXT_DIM     = (140, 152, 190)
TEXT_FAINT   = ( 82,  96, 130)

W, H     = 320, 240
TOP_H    = 38
BTM_H    = 56
MID_Y    = TOP_H
MID_H    = H - TOP_H - BTM_H
MID_CY   = MID_Y + MID_H // 2
PAD_X    = 16
ICON_SIZE = 72
ICON_X   = PAD_X
ICON_Y   = MID_Y + (MID_H - ICON_SIZE) // 2
TEMP_X   = ICON_X + ICON_SIZE + 14

FS_LABEL = 20
FS_TEMP  = 54
FS_UNIT  = 22
FS_COND  = 13
FS_NOTE  = 20

_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
]
_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]


def _wmo_label(code: int) -> str:
    if code == 0:   return "Clear sky"
    if code <= 2:   return "Mostly Clear"
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


def _load_font(paths: list, size: int) -> ImageFont.ImageFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _tw(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    except AttributeError:
        w, _ = draw.textsize(text, font=font)
        return w


def _th(draw: ImageDraw.ImageDraw, font) -> int:
    try:
        bb = draw.textbbox((0, 0), "0", font=font)
        return bb[3] - bb[1]
    except AttributeError:
        _, h = draw.textsize("0", font=font)
        return h


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if _tw(draw, text, font) <= max_w:
        return text
    while text:
        text = text[:-1]
        if _tw(draw, text + "…", font) <= max_w:
            return text + "…"
    return "…"


class DailyScreen:

    def __init__(self, draw, width, height, display, on_done):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.display = display
        self.on_done = on_done

        self._prev = {btn: False for btn in BUTTON_NAMES}

        self._config = self._load_config()
        self._note   = self._load_note()

        self._wcode      = None
        self._wtemp      = None
        self._wlock      = threading.Lock()
        self._fetching   = False
        self._last_fetch = 0.0

        self._f_label  = _load_font(_REGULAR_PATHS, FS_LABEL)
        self._f_temp   = _load_font(_BOLD_PATHS,    FS_TEMP)
        self._f_unit   = _load_font(_REGULAR_PATHS, FS_UNIT)
        self._f_cond   = _load_font(_REGULAR_PATHS, FS_COND)
        self._f_note   = _load_font(_REGULAR_PATHS,  FS_NOTE)

        self._bg    = self._load_bg()
        self._icons = self._load_icons()

        self._trigger_fetch()

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

    def _load_bg(self) -> Image.Image | None:
        try:
            return Image.open(BG_PATH).convert("RGB")
        except Exception as e:
            print(f"[Daily] BG load failed: {e}")
            return None

    def _load_icons(self) -> dict:
        names = [
            "sunny", "clear_night", "partly", "partly_night",
            "foggy", "rainy", "snowy", "thunder",
        ]
        icons: dict = {}
        for name in names:
            try:
                img = Image.open(f"assets/weather/{name}.png").convert("RGBA")
                icons[name] = img
            except Exception as e:
                print(f"[Daily] Icon '{name}' not loaded: {e}")
        return icons

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

    def render(self):
        d   = self.draw
        buf = d._image
        now = datetime.now()

        with self._wlock:
            code, temp = self._wcode, self._wtemp

        # Background
        if self._bg:
            buf.paste(self._bg, (0, 0))
        else:
            d.rectangle((0, 0, W, H), fill=(11, 15, 28))

        # City (top left)
        cfg  = self._config.get("weather", {})
        city = cfg.get("city", "")
        if city:
            d.text((PAD_X, 12), city.upper(), font=self._f_label, fill=TEXT_DIM)

        # Time + date (top right)
        dt_str = now.strftime("%H:%M  ·  %a %-d %b").upper()
        dt_w   = _tw(d, dt_str, self._f_label)
        d.text((W - PAD_X - dt_w, 12), dt_str, font=self._f_label, fill=TEXT_FAINT)

        # Weather icon
        if code is not None:
            icon = self._icons.get(_icon_name(code, now.hour))
            if icon:
                buf.paste(icon, (ICON_X, ICON_Y), icon)

        # Temperature
        unit_key = cfg.get("unit", "celsius")
        unit_str = "°C" if unit_key == "celsius" else "°F"
        temp_str = f"{temp:.0f}" if temp is not None else "—"
        temp_h   = _th(d, self._f_temp)
        temp_y   = MID_CY - temp_h // 2

        d.text((TEMP_X, temp_y), temp_str, font=self._f_temp, fill=TEXT_PRIMARY)

        # Use the real bounding box to find the actual bottom and left of the glyph
        try:
            temp_bb     = d.textbbox((TEMP_X, temp_y), temp_str, font=self._f_temp)
            temp_left   = temp_bb[0]
            temp_bottom = temp_bb[3]
            num_w       = temp_bb[2] - temp_bb[0]
        except AttributeError:
            temp_left   = TEMP_X
            temp_bottom = temp_y + temp_h
            num_w       = _tw(d, temp_str, self._f_temp)

        # Unit symbol
        unit_x = TEMP_X + num_w + 3
        unit_y = temp_y + 6
        d.text((unit_x, unit_y), unit_str, font=self._f_unit, fill=TEXT_FAINT)

        # Condition — anchored to the actual bottom-left of the temperature glyph
        cond_str = _wmo_label(code) if code is not None else "Loading…"
        cond_y   = temp_bottom + 6
        d.text((temp_left + 4, cond_y), cond_str, font=self._f_cond, fill=TEXT_DIM)

        # Note (conditional — only if a note exists for today)
        if self._note:
            BTM_Y      = H - BTM_H
            # leave room for the Y button already rendered in bg.jpg
            max_note_w = W - PAD_X * 2 - 32
            note_str   = _truncate(d, self._note, self._f_note, max_note_w)
            note_h     = _th(d, self._f_note)
            note_y     = BTM_Y + (BTM_H - note_h) // 2
            d.text((PAD_X, note_y), note_str, font=self._f_note, fill=TEXT_DIM)
