from core.adb import (
    begin_bot_screen_cycle,
    clear_screenshot_cache,
    get_screenshot_cache,
    run_adb,
    set_screenshot_cache,
)
from core.vision import decode_image_bytes


def get_screen():
    cached = get_screenshot_cache()
    if cached is not None:
        return decode_image_bytes(cached)

    image_bytes = run_adb(["exec-out", "screencap", "-p"])
    set_screenshot_cache(image_bytes)
    return decode_image_bytes(image_bytes)


__all__ = [
    "begin_bot_screen_cycle",
    "clear_screenshot_cache",
    "get_screen",
]
