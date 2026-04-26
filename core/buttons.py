"""
core/buttons.py
---------------
Event-driven button handler for the Display HAT Mini.

Buttons (GPIO BCM numbering):
  A → GPIO 5   (Pin 29)
  B → GPIO 6   (Pin 31)
  X → GPIO 16  (Pin 36)
  Y → GPIO 24  (Pin 18)

Usage:
    buttons = Buttons()
    buttons.on_press(Button.A, my_callback)   # register
    buttons.clear()                            # unregister all (on mode switch)
"""

import threading
from enum import Enum
from gpiozero import Button as GPIOButton


class Button(Enum):
    A = 5
    B = 6
    X = 16
    Y = 24


# Human-readable labels for UI rendering
BUTTON_LABELS = {
    Button.A: "A",
    Button.B: "B",
    Button.X: "X",
    Button.Y: "Y",
}

_DEBOUNCE_MS = 200  # milliseconds


class Buttons:
    """
    Manages all four physical buttons.
    Callbacks are registered per-mode and cleared on mode switch.
    All callbacks run in a daemon thread — keep them short or dispatch work.
    """

    def __init__(self):
        self._callbacks: dict[Button, list] = {b: [] for b in Button}
        self._last_press: dict[Button, float] = {b: 0.0 for b in Button}
        self._lock = threading.Lock()

        # Set up gpiozero buttons with pull-up (hat has external pull-ups too)
        self._gpio: dict[Button, GPIOButton] = {}
        for btn in Button:
            gpio_btn = GPIOButton(btn.value, pull_up=True, bounce_time=_DEBOUNCE_MS / 1000)
            # Capture btn in closure correctly
            gpio_btn.when_pressed = self._make_handler(btn)
            self._gpio[btn] = gpio_btn

    def _make_handler(self, btn: Button):
        def handler():
            with self._lock:
                callbacks = list(self._callbacks[btn])
            for cb in callbacks:
                try:
                    cb(btn)
                except Exception as e:
                    print(f"[Buttons] callback error on {btn}: {e}")
        return handler

    def on_press(self, btn: Button, callback):
        """Register a callback for a button press. Can register multiple."""
        with self._lock:
            self._callbacks[btn].append(callback)

    def off_press(self, btn: Button, callback):
        """Unregister a specific callback."""
        with self._lock:
            try:
                self._callbacks[btn].remove(callback)
            except ValueError:
                pass

    def clear(self, btn: Button = None):
        """Clear all callbacks. Pass a specific Button to clear only that one."""
        with self._lock:
            if btn is None:
                for b in Button:
                    self._callbacks[b] = []
            else:
                self._callbacks[btn] = []

    def close(self):
        """Release GPIO resources."""
        for gpio_btn in self._gpio.values():
            gpio_btn.close()
