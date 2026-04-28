"""
modes/menu.py
-------------
Main menu. Displays the pre-rendered menu image (assets/main_menu.jpg).

During development only Settings (Y) is wired up.
"""

import os
from PIL import Image
from modes.base_mode import BaseMode
from core.buttons import Button


_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_MENU_IMAGE = os.path.join(_ASSETS_DIR, "main_menu.jpg")


class MenuMode(BaseMode):
    name = "Menu"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._img = None

    def start(self):
        self.buttons.on_press(Button.Y, lambda _: self.switch_to("settings"))

    def stop(self):
        self.buttons.clear()

    def update(self):
        if self._img is None:
            self._img = Image.open(_MENU_IMAGE).convert("RGB")
        self.display.show(self._img)
