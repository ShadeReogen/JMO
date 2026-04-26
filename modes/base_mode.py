"""
modes/base_mode.py
------------------
Abstract base class every mode inherits from.

Lifecycle:
  start()   → called once when entering the mode
  stop()    → called once when leaving the mode
  update()  → called in the render loop (~10 fps); draw to display here

The app (main.py) drives the loop and calls these methods.
Modes must NOT block in update() — keep it under ~50ms.
"""

from abc import ABC, abstractmethod
from core.display import Display
from core.buttons import Buttons


class BaseMode(ABC):

    #: Human-readable name shown in the menu
    name: str = "Unnamed Mode"

    #: Icon filename (relative to assets/icons/) shown in the menu
    icon: str = ""

    def __init__(self, display: Display, buttons: Buttons, app):
        """
        display : core.display.Display
        buttons : core.buttons.Buttons
        app     : main.App  (for triggering mode switches)
        """
        self.display = display
        self.buttons = buttons
        self.app     = app

    # ------------------------------------------------------------------
    # Lifecycle — override these
    # ------------------------------------------------------------------

    def start(self):
        """
        Called once when the mode becomes active.
        Register button callbacks, initialise state, start background threads.
        """
        pass

    def stop(self):
        """
        Called once when the mode is deactivated.
        Clear button callbacks, stop threads, release resources.
        """
        self.buttons.clear()

    @abstractmethod
    def update(self):
        """
        Called repeatedly in the render loop.
        Draw the current frame to self.display.
        """
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def switch_to(self, mode_name: str):
        """Ask the app to switch to another mode by name."""
        self.app.switch_mode(mode_name)
