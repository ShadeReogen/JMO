#!/usr/bin/env python3
import time
from PIL import Image, ImageDraw
from displayhatmini import DisplayHATMini
from screens.splash import SplashScreen
from screens.menu import MenuScreen
from screens.settings import SettingsScreen
from screens.daily import DailyScreen

# --- Display setup ---
width = DisplayHATMini.WIDTH
height = DisplayHATMini.HEIGHT
buffer = Image.new("RGB", (width, height))
draw = ImageDraw.Draw(buffer)

display = DisplayHATMini(buffer, backlight_pwm=True)
display.set_backlight(1.0)
display.set_led(0.0, 0.0, 0.0)

# --- App state ---
current_screen = None


def set_screen(screen):
    global current_screen
    current_screen = screen


def main():
    def go_to_menu():
        set_screen(MenuScreen(draw, width, height, display,
                              on_settings=go_to_settings,
                              on_daily=go_to_daily))

    def go_to_settings():
        set_screen(SettingsScreen(draw, width, height, display, on_done=go_to_menu))

    def go_to_daily():
        set_screen(DailyScreen(draw, width, height, display, on_done=go_to_menu))

    set_screen(SplashScreen(draw, width, height, go_to_menu))

    try:
        while True:
            if current_screen:
                current_screen.update()
                current_screen.render()

            display.display()
            time.sleep(1.0 / 30)  # ~30 fps

    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        draw.rectangle((0, 0, width, height), (0, 0, 0))
        display.display()
        display.set_backlight(0.0)
        display.set_led(0.0, 0.0, 0.0)
        print("\nExited cleanly.")


if __name__ == "__main__":
    main()