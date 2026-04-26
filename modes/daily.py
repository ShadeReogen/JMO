"""
modes/daily.py
--------------
Smart Daily Screen.

Shows:
  - Current time (large)
  - Date
  - Weather (fetched from Open-Meteo, cached)
  - Today's note from notes.json (if any)

Buttons:
  Y → back to menu
"""

import time
import threading
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from modes.base_mode import BaseMode
from core.buttons    import Button
from core.config     import config

WEATHER_REFRESH_SECS = 600  # re-fetch every 10 min
WMO_CODES = {
    0: "Clear ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫️", 48: "Icy fog 🌫️",
    51: "Light drizzle 🌦️", 53: "Drizzle 🌦️", 55: "Heavy drizzle 🌧️",
    61: "Light rain 🌧️", 63: "Rain 🌧️", 65: "Heavy rain 🌧️",
    71: "Light snow 🌨️", 73: "Snow 🌨️", 75: "Heavy snow ❄️",
    80: "Showers 🌦️", 81: "Showers 🌧️", 82: "Heavy showers 🌧️",
    95: "Thunderstorm ⛈️",
}


class DailyMode(BaseMode):
    name = "Daily"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._weather: dict  = {}
        self._last_weather   = 0.0
        self._last_minute    = -1
        self._fetching       = False

    def start(self):
        self._last_minute = -1
        self.buttons.on_press(Button.Y, lambda _: self.switch_to("menu"))
        self._fetch_weather_async()

    def stop(self):
        self.buttons.clear()

    def update(self):
        now = datetime.now()

        # Refresh weather in background
        if time.monotonic() - self._last_weather > WEATHER_REFRESH_SECS:
            self._fetch_weather_async()

        # Only redraw on minute change
        if now.minute == self._last_minute:
            return
        self._last_minute = now.minute

        self._render(now)

    def _render(self, now: datetime):
        W, H = self.display.width, self.display.height
        img  = Image.new("RGB", (W, H), (10, 12, 25))
        draw = ImageDraw.Draw(img)

        try:
            font_time   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
            font_date   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            font_detail = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            font_note   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        except IOError:
            font_time = font_date = font_detail = font_note = ImageFont.load_default()

        # ── Time ─────────────────────────────────────────────────────
        time_str = now.strftime("%H:%M")
        bbox = draw.textbbox((0, 0), time_str, font=font_time)
        tw   = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 10), time_str, font=font_time, fill=(240, 220, 255))

        # ── Date ─────────────────────────────────────────────────────
        date_str = now.strftime("%A, %d %B %Y")
        bbox = draw.textbbox((0, 0), date_str, font=font_date)
        dw   = bbox[2] - bbox[0]
        draw.text(((W - dw) // 2, 76), date_str, font=font_date, fill=(160, 150, 190))

        # ── Divider ──────────────────────────────────────────────────
        draw.line([(20, 100), (W - 20, 100)], fill=(50, 50, 80), width=1)

        # ── Weather ──────────────────────────────────────────────────
        if self._weather:
            temp  = self._weather.get("temp", "?")
            desc  = self._weather.get("desc", "")
            unit  = "°C" if config.get("weather", "unit") == "celsius" else "°F"
            w_str = f"{temp}{unit}  {desc}"
            bbox  = draw.textbbox((0, 0), w_str, font=font_detail)
            ww    = bbox[2] - bbox[0]
            draw.text(((W - ww) // 2, 112), w_str, font=font_detail, fill=(130, 200, 255))
        else:
            draw.text((20, 112), "Fetching weather…", font=font_detail, fill=(80, 80, 110))

        # ── Today's note ─────────────────────────────────────────────
        note = config.today_note()
        if note:
            # Pink pill background
            bbox = draw.textbbox((0, 0), note, font=font_note)
            nw   = bbox[2] - bbox[0]
            nx   = (W - nw - 20) // 2
            ny   = H - 45
            draw.rounded_rectangle([nx - 6, ny - 4, nx + nw + 6, ny + 20],
                                    radius=8, fill=(60, 20, 35))
            draw.text((nx, ny), note, font=font_note, fill=(255, 170, 190))

        # ── Y-button hint ─────────────────────────────────────────────
        draw.text((W - 55, H - 18), "Y: Menu", font=font_detail, fill=(60, 60, 80))

        self.display.show(img)

    def _fetch_weather_async(self):
        if self._fetching:
            return
        self._fetching = True
        t = threading.Thread(target=self._fetch_weather, daemon=True)
        t.start()

    def _fetch_weather(self):
        try:
            lat  = config.get("weather", "lat", default=47.37)
            lon  = config.get("weather", "lon", default=8.54)
            unit = "celsius" if config.get("weather", "unit") == "celsius" else "fahrenheit"
            url  = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&current_weather=true&temperature_unit={unit}"
            )
            r    = requests.get(url, timeout=10)
            data = r.json().get("current_weather", {})
            self._weather = {
                "temp": round(data.get("temperature", 0)),
                "desc": WMO_CODES.get(data.get("weathercode", 0), ""),
            }
            self._last_weather = time.monotonic()
            self._last_minute  = -1   # force redraw
        except Exception as e:
            print(f"[Daily] Weather fetch failed: {e}")
        finally:
            self._fetching = False
