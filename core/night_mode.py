"""
core/night_mode.py
------------------
Background daemon thread that watches the clock and triggers night mode.

Night mode:
  - Dims the backlight to the configured low level
  - Signals the app to switch to the night screen
  - On exit, restores the previous mode and brightness
"""

import threading
import time
from datetime import datetime


def _time_in_range(start_str: str, end_str: str, now: datetime) -> bool:
    """
    Returns True if `now` is within [start, end).
    Handles overnight ranges like 23:00 → 08:00.
    """
    def parse(s):
        h, m = map(int, s.split(":"))
        return h * 60 + m

    now_min   = now.hour * 60 + now.minute
    start_min = parse(start_str)
    end_min   = parse(end_str)

    if start_min <= end_min:
        # Same-day range e.g. 02:00 → 08:00
        return start_min <= now_min < end_min
    else:
        # Overnight range e.g. 23:00 → 08:00
        return now_min >= start_min or now_min < end_min


class NightModeWatcher:
    """
    Poll interval: 30 seconds.
    Calls on_enter() / on_exit() exactly once per transition.
    """

    def __init__(self, config, on_enter, on_exit):
        """
        config    : core.config.Config singleton
        on_enter  : callable() — called when night mode should start
        on_exit   : callable() — called when night mode should end
        """
        self._config   = config
        self._on_enter = on_enter
        self._on_exit  = on_exit
        self._active   = False     # is night mode currently on?
        self._running  = False
        self._thread   = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def is_active(self) -> bool:
        return self._active

    def _loop(self):
        while self._running:
            self._check()
            time.sleep(30)

    def _check(self):
        cfg = self._config
        if not cfg.get("night_mode", "enabled"):
            if self._active:
                self._active = False
                self._on_exit()
            return

        start = cfg.get("night_mode", "start", default="23:00")
        end   = cfg.get("night_mode", "end",   default="08:00")
        now   = datetime.now()

        should_be_night = _time_in_range(start, end, now)

        if should_be_night and not self._active:
            self._active = True
            self._on_enter()
        elif not should_be_night and self._active:
            self._active = False
            self._on_exit()
