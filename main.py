#!/usr/bin/env python3
"""
main.py
-------
Entry point for pi-frame.

Responsibilities:
  - Boot sequence (splash → menu)
  - Own the Display and Buttons singletons
  - Run the mode state machine
  - Host the NightModeWatcher
  - Handle clean shutdown on SIGINT / SIGTERM
"""

import os
import signal
import sys
import time
import logging

_LOG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "piframe.log")

_handlers = [logging.StreamHandler(sys.stdout)]
try:
    os.makedirs(_LOG_DIR, exist_ok=True)
    _handlers.append(logging.FileHandler(_LOG_FILE))
except OSError as _e:
    pass  # log dir not writable; stdout only

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger("main")
if len(_handlers) > 1:
    logger.info(f"Logging to {_LOG_FILE}")
else:
    logger.warning(f"Cannot write log file ({_LOG_FILE}); stdout only")

from core.display   import Display
from core.buttons   import Buttons
from core.config    import config
from core.night_mode import NightModeWatcher

# Import all modes
from modes.splash   import SplashMode
from modes.menu     import MenuMode
from modes.daily    import DailyMode
from modes.frame    import FrameMode
from modes.mood     import MoodMode
from modes.settings import SettingsMode
from modes.night    import NightScreen


TARGET_FPS = 10
FRAME_TIME = 1.0 / TARGET_FPS


class App:
    """
    Central application object.
    Passed into every mode so they can call self.app.switch_mode().
    """

    def __init__(self):
        self.display  = Display()
        self.buttons  = Buttons()
        self._running = False

        # Build mode registry
        kwargs = dict(display=self.display, buttons=self.buttons, app=self)
        self._modes: dict[str, object] = {
            "splash":   SplashMode(**kwargs),
            "menu":     MenuMode(**kwargs),
            "daily":    DailyMode(**kwargs),
            "frame":    FrameMode(**kwargs),
            "mood":     MoodMode(**kwargs),
            "settings": SettingsMode(**kwargs),
            "night":    NightScreen(**kwargs),
        }

        self._current_mode      = None
        self._pre_night_mode    = "menu"   # restore after night mode ends
        self._night_watcher     = NightModeWatcher(
            config,
            on_enter=self._enter_night,
            on_exit=self._exit_night,
        )

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def switch_mode(self, name: str):
        if name not in self._modes:
            logger.error(f"Unknown mode: {name}")
            return

        if self._current_mode is not None:
            logger.info(f"Stopping mode: {self._current_mode.name}")
            self._current_mode.stop()

        logger.info(f"Starting mode: {name}")
        self._current_mode = self._modes[name]
        self._current_mode.start()

    # ------------------------------------------------------------------
    # Night mode callbacks (called from watcher thread)
    # ------------------------------------------------------------------

    def _enter_night(self):
        logger.info("Night mode: entering")
        # Remember which mode we were in (but not 'night' itself)
        if self._current_mode and self._current_mode is not self._modes["night"]:
            for k, v in self._modes.items():
                if v is self._current_mode:
                    self._pre_night_mode = k
                    break
        night_brightness = config.get("night_mode", "brightness", default=10)
        self.display.set_brightness(night_brightness)
        self.switch_mode("night")

    def _exit_night(self):
        logger.info("Night mode: exiting")
        normal_brightness = config.get("brightness", default=80)
        self.display.set_brightness(normal_brightness)
        self.switch_mode(self._pre_night_mode)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        self._running = True

        # Wire up clean shutdown
        signal.signal(signal.SIGINT,  self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        # Boot sequence: splash first, then menu
        self.switch_mode("splash")
        self._night_watcher.start()

        while self._running:
            t0 = time.monotonic()
            try:
                if self._current_mode:
                    self._current_mode.update()
            except Exception as e:
                logger.exception(f"Error in mode update: {e}")

            elapsed = time.monotonic() - t0
            sleep   = FRAME_TIME - elapsed
            if sleep > 0:
                time.sleep(sleep)

        self._cleanup()

    def _shutdown(self, *_):
        logger.info("Shutdown signal received")
        self._running = False

    def _cleanup(self):
        self._night_watcher.stop()
        if self._current_mode:
            self._current_mode.stop()
        self.display.clear()
        self.display.set_brightness(0)
        self.buttons.close()
        logger.info("Goodbye.")


if __name__ == "__main__":
    App().run()
