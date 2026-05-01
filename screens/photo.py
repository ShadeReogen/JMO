#!/usr/bin/env python3
"""
screens/photo.py

Fetches a random photo from Supabase, displays it full-screen.
Photo refreshes according to config photo_interval_hours.
Any button press exits back to the menu.
"""
import io
import time
import threading
import urllib.request

from PIL import Image, ImageDraw, ImageFont
from displayhatmini import DisplayHATMini

import config


BUTTON_NAMES = {
    DisplayHATMini.BUTTON_A: "A",
    DisplayHATMini.BUTTON_B: "B",
    DisplayHATMini.BUTTON_X: "X",
    DisplayHATMini.BUTTON_Y: "Y",
}


class PhotoScreen:
    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        display: DisplayHATMini,
        on_exit,          # callback → back to menu
    ):
        self.draw    = draw
        self.width   = width
        self.height  = height
        self.display = display
        self.on_exit = on_exit

        self._prev_buttons = {btn: False for btn in BUTTON_NAMES}
        self._photo: Image.Image | None = None   # current displayed photo
        self._loading  = False
        self._error    = False
        self._last_fetch: float = 0.0            # epoch of last successful fetch

        # Show a placeholder immediately and start the first fetch
        self._show_loading_frame()
        self._fetch_async()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _interval_seconds(self) -> float:
        hours = config.get("photo_interval_hours", 24)
        return float(hours) * 3600

    def _supabase_url(self) -> str:
        return config.get("supabase", {}).get("url", "").rstrip("/")

    def _supabase_key(self) -> str:
        return config.get("supabase", {}).get("publishable_key", "")

    def _show_loading_frame(self):
        """Draw a dark frame so the screen isn't blank while fetching."""
        self.draw.rectangle((0, 0, self.width, self.height), fill=(15, 15, 25))

    def _fetch_async(self):
        """Kick off a background thread so the display loop never blocks."""
        if self._loading:
            return
        self._loading = True
        t = threading.Thread(target=self._fetch_photo, daemon=True)
        t.start()

    def _fetch_photo(self):
        """Called from background thread: hit edge function, download image."""
        base = self._supabase_url()
        key  = self._supabase_key()

        if not base or not key:
            print("[PhotoFrame] Supabase URL or key missing in config.json")
            self._error   = True
            self._loading = False
            return

        endpoint = f"{base}/functions/v1/random-photo"

        try:
            # 1. Ask the edge function for a signed URL
            req = urllib.request.Request(
                endpoint,
                headers={"Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                import json
                data = json.loads(resp.read())

            signed_url = data.get("url")
            if not signed_url:
                raise ValueError("No URL in response")

            # 2. Download the actual image
            with urllib.request.urlopen(signed_url, timeout=30) as img_resp:
                raw = img_resp.read()

            photo = Image.open(io.BytesIO(raw)).convert("RGB")

            # 3. Fit to display: scale down keeping aspect ratio, then centre-crop
            photo = self._fit(photo)

            self._photo      = photo
            self._last_fetch = time.time()
            self._error      = False
            print(f"[PhotoFrame] Loaded: {data.get('filename', '?')}")

        except Exception as e:
            print(f"[PhotoFrame] Fetch error: {e}")
            self._error = True

        finally:
            self._loading = False

    def _fit(self, img: Image.Image) -> Image.Image:
        """Scale-then-centre-crop to exactly (width × height)."""
        tw, th = self.width, self.height
        iw, ih = img.size

        scale = max(tw / iw, th / ih)
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        img   = img.resize((new_w, new_h), Image.LANCZOS)

        left = (new_w - tw) // 2
        top  = (new_h - th) // 2
        return img.crop((left, top, left + tw, top + th))

    # ── Screen interface ───────────────────────────────────────────────────────

    def update(self):
        # Button edge detection — any press exits
        for btn in BUTTON_NAMES:
            pressed = self.display.read_button(btn)
            if pressed and not self._prev_buttons[btn]:
                self.on_exit()
                return
            self._prev_buttons[btn] = pressed

        # Time-based refresh
        if (
            not self._loading
            and not self._error
            and self._last_fetch > 0
            and (time.time() - self._last_fetch) >= self._interval_seconds()
        ):
            self._fetch_async()

        # If there was an error, retry after 60 s
        if (
            self._error
            and not self._loading
            and (time.time() - self._last_fetch) >= 60
        ):
            self._last_fetch = time.time()   # prevent retry storm
            self._fetch_async()

    def render(self):
        w, h = self.width, self.height

        if self._photo:
            # Fast path: paste pre-fitted photo directly into the buffer
            self.draw._image.paste(self._photo, (0, 0))

        elif self._loading:
            # Pulsing dark screen with a small "…" indicator
            self.draw.rectangle((0, 0, w, h), fill=(15, 15, 25))
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            except Exception:
                font = ImageFont.load_default()
            msg = "Loading photo..."
            try:
                bb = self.draw.textbbox((0, 0), msg, font=font)
                tw = bb[2] - bb[0]
            except AttributeError:
                tw, _ = self.draw.textsize(msg, font=font)
            self.draw.text(
                ((w - tw) // 2, h // 2 - 6),
                msg, font=font, fill=(100, 100, 130))

        else:
            # Error state
            self.draw.rectangle((0, 0, w, h), fill=(25, 10, 10))
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            except Exception:
                font = ImageFont.load_default()
            msg = "Could not load photo"
            try:
                bb = self.draw.textbbox((0, 0), msg, font=font)
                tw = bb[2] - bb[0]
            except AttributeError:
                tw, _ = self.draw.textsize(msg, font=font)
            self.draw.text(
                ((w - tw) // 2, h // 2 - 6),
                msg, font=font, fill=(200, 80, 80))