#!/usr/bin/env python3
"""
screens/memory_lane.py

Memory Lane — browse memories by date.
Reads memories.json where keys are "YYYY-MM-DD" and values are:
  {"type": "text",  "content": "..."}
  {"type": "image", "url": "https://..."}

View mode:   A → calendar  |  Y → back to menu
Calendar:    A ← month  |  X → month  |  B: cycle day  |  Y: confirm
"""

import io
import json
import calendar
import threading
import urllib.request
from datetime import date

from PIL import Image, ImageDraw, ImageFont
from displayhatmini import DisplayHATMini

BUTTON_NAMES = {
    DisplayHATMini.BUTTON_A: "A",
    DisplayHATMini.BUTTON_B: "B",
    DisplayHATMini.BUTTON_X: "X",
    DisplayHATMini.BUTTON_Y: "Y",
}

MEMORIES_FILE = "memories.json"

_BG       = (10,  10,  20)
_TITLE    = (0,  200, 255)
_TEXT     = (200, 200, 220)
_DIM      = (80,  80, 110)
_SEL      = (255, 255, 255)
_SEL_BG   = (40,  40,  90)
_HINT     = (60,  60, 100)
_NONE     = (120,  60,  60)
_ACCENT   = (255, 160,  60)
_WEEKEND  = (200, 100,  80)


class MemoryLaneScreen:
    def __init__(self, draw, width, height, display, on_exit):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.display = display
        self.on_exit = on_exit

        self._prev = {btn: False for btn in BUTTON_NAMES}
        self._font_md = self._load_font(14)
        self._font_sm = self._load_font(11)

        self._memories = self._load_memories()

        self._mode      = "view"
        self._selected  = date.today()
        self._cal_year  = self._selected.year
        self._cal_month = self._selected.month
        self._cal_day   = self._selected.day

        self._photo:    Image.Image | None = None
        self._loading   = False
        self._photo_err = False
        self._lock      = threading.Lock()

        self._current_memory = self._memories.get(self._selected.strftime("%Y-%m-%d"))
        self._maybe_load_photo()

    # ── Fonts & text helpers ───────────────────────────────────────────────────

    def _load_font(self, size):
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

    def _ctext(self, y, text, font, color):
        x = (self.width - self._tw(text, font)) // 2
        self.draw.text((x, y), text, font=font, fill=color)

    # ── Data ───────────────────────────────────────────────────────────────────

    def _load_memories(self):
        try:
            with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print("[MemoryLane] memories.json not found.")
            return {}
        except Exception as e:
            print(f"[MemoryLane] Could not load memories.json: {e}")
            return {}

    def _maybe_load_photo(self):
        m = self._current_memory
        with self._lock:
            self._photo     = None
            self._photo_err = False
        if m and m.get("type") == "image":
            self._loading = True
            threading.Thread(
                target=self._fetch_photo, args=(m["url"],), daemon=True
            ).start()
        else:
            self._loading = False

    def _fetch_photo(self, url: str):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                raw = resp.read()
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img = self._fit(img)
            with self._lock:
                self._photo = img
        except Exception as e:
            print(f"[MemoryLane] Image fetch error: {e}")
            with self._lock:
                self._photo_err = True
        finally:
            self._loading = False

    def _fit(self, img: Image.Image) -> Image.Image:
        tw, th = self.width, self.height
        iw, ih = img.size
        scale = max(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img  = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - tw) // 2
        top  = (nh - th) // 2
        return img.crop((left, top, left + tw, top + th))

    # ── Input ──────────────────────────────────────────────────────────────────

    def update(self):
        for btn, name in BUTTON_NAMES.items():
            pressed = self.display.read_button(btn)
            if pressed and not self._prev[btn]:
                self._on_press(name)
            self._prev[btn] = pressed

    def _on_press(self, name):
        if self._mode == "view":
            self._press_view(name)
        else:
            self._press_cal(name)

    def _press_view(self, name):
        if name == "Y":
            self.on_exit()
        elif name == "A":
            self._cal_year  = self._selected.year
            self._cal_month = self._selected.month
            self._cal_day   = self._selected.day
            self._mode = "calendar"

    def _press_cal(self, name):
        today = date.today()
        # Earliest allowed: 2 months back
        min_m = today.month - 2
        min_y = today.year
        if min_m <= 0:
            min_m += 12
            min_y -= 1

        if name == "A":
            if (self._cal_year, self._cal_month) <= (min_y, min_m):
                return
            if self._cal_month == 1:
                self._cal_month, self._cal_year = 12, self._cal_year - 1
            else:
                self._cal_month -= 1
            self._clamp_day()

        elif name == "X":
            if (self._cal_year, self._cal_month) >= (today.year, today.month):
                return
            if self._cal_month == 12:
                self._cal_month, self._cal_year = 1, self._cal_year + 1
            else:
                self._cal_month += 1
            self._clamp_day()

        elif name == "B":
            max_day = calendar.monthrange(self._cal_year, self._cal_month)[1]
            self._cal_day = (self._cal_day % max_day) + 1

        elif name == "Y":
            self._selected = date(self._cal_year, self._cal_month, self._cal_day)
            self._current_memory = self._memories.get(self._selected.strftime("%Y-%m-%d"))
            self._maybe_load_photo()
            self._mode = "view"

    def _clamp_day(self):
        max_day = calendar.monthrange(self._cal_year, self._cal_month)[1]
        if self._cal_day > max_day:
            self._cal_day = max_day

    # ── Render ─────────────────────────────────────────────────────────────────

    def render(self):
        if self._mode == "view":
            self._render_view()
        else:
            self._render_cal()

    def _render_view(self):
        w, h = self.width, self.height
        m    = self._current_memory

        if m and m.get("type") == "image":
            with self._lock:
                photo = self._photo

            if photo:
                self.draw._image.paste(photo, (0, 0))
                strip = Image.new("RGBA", (w, 24), (0, 0, 0, 160))
                self.draw._image.paste(strip, (0, 0), strip)
            elif self._loading:
                self.draw.rectangle((0, 0, w, h), fill=_BG)
                self._ctext(h // 2 - 6, "Loading image...", self._font_sm, _DIM)
            else:
                self.draw.rectangle((0, 0, w, h), fill=(25, 10, 10))
                self._ctext(h // 2 - 6, "Could not load image", self._font_sm, _NONE)
        else:
            self.draw.rectangle((0, 0, w, h), fill=_BG)

        # Date header
        self.draw.text((8, 5), self._selected.strftime("%B %d, %Y"),
                       font=self._font_md, fill=_TITLE)

        # Content
        if m is None:
            self._ctext(h // 2 - 14, "Nothing here yet.", self._font_md, _DIM)
            self._ctext(h // 2 + 4,  "Press A to pick a date.", self._font_sm, _HINT)
        elif m.get("type") == "text":
            self._draw_wrapped(m.get("content", ""), 10, 30, w - 20, self._font_md)

        # Hint bar
        self.draw.rectangle((0, h - 16, w, h), fill=(0, 0, 0))
        self.draw.text((6, h - 14), "A:calendar",
                       font=self._font_sm, fill=_HINT)
        lbl = "Y:back"
        self.draw.text((w - self._tw(lbl, self._font_sm) - 6, h - 14),
                       lbl, font=self._font_sm, fill=_HINT)

    def _render_cal(self):
        w, h = self.width, self.height
        self.draw.rectangle((0, 0, w, h), fill=_BG)

        # Month/year header
        header = f"{calendar.month_name[self._cal_month]} {self._cal_year}"
        self._ctext(5, header, self._font_md, _TITLE)
        self.draw.text((4, 6), "<A", font=self._font_sm, fill=_HINT)
        nav = "X>"
        self.draw.text((w - self._tw(nav, self._font_sm) - 4, 6),
                       nav, font=self._font_sm, fill=_HINT)

        # Day-of-week labels
        dow = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        cell_w = w // 7
        for i, lbl in enumerate(dow):
            lw  = self._tw(lbl, self._font_sm)
            col = _WEEKEND if i >= 5 else _DIM
            self.draw.text((i * cell_w + (cell_w - lw) // 2, 24),
                           lbl, font=self._font_sm, fill=col)

        # Day grid
        weeks  = calendar.monthcalendar(self._cal_year, self._cal_month)
        y0     = 38
        cell_h = (h - 16 - y0) // max(len(weeks), 1)

        for ri, week in enumerate(weeks):
            for ci, day in enumerate(week):
                if day == 0:
                    continue
                x   = ci * cell_w
                y   = y0 + ri * cell_h
                key = date(self._cal_year, self._cal_month, day).strftime("%Y-%m-%d")

                if day == self._cal_day:
                    self.draw.rectangle(
                        (x + 1, y, x + cell_w - 2, y + cell_h - 3), fill=_SEL_BG
                    )
                    col = _SEL
                elif key in self._memories:
                    col = _ACCENT
                else:
                    col = _TEXT

                lbl = str(day)
                self.draw.text(
                    (x + (cell_w - self._tw(lbl, self._font_sm)) // 2, y + 2),
                    lbl, font=self._font_sm, fill=col,
                )

        # Hint bar
        self.draw.rectangle((0, h - 16, w, h), fill=(0, 0, 0))
        self.draw.text((6, h - 14), "B:day", font=self._font_sm, fill=_HINT)
        confirm = "Y:confirm"
        self.draw.text((w - self._tw(confirm, self._font_sm) - 6, h - 14),
                       confirm, font=self._font_sm, fill=_HINT)

    def _draw_wrapped(self, text, x, y, max_w, font):
        words  = text.split()
        line   = ""
        cy     = y
        line_h = self._th(font) + 3

        for word in words:
            test = (line + " " + word).strip()
            if self._tw(test, font) <= max_w:
                line = test
            else:
                if line:
                    self.draw.text((x, cy), line, font=font, fill=_TEXT)
                    cy += line_h
                line = word
                if cy + line_h > self.height - 20:
                    break
        if line:
            self.draw.text((x, cy), line, font=font, fill=_TEXT)
