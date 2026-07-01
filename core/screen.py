import cv2
import numpy as np

from core.adb import (
    begin_bot_screen_cycle,
    clear_screenshot_cache,
    get_screenshot_cache,
    run_adb,
    set_screenshot_cache,
)
from core.logger import log
from core.vision import decode_image_bytes


def _log_decode_diagnostics(image_bytes):
    image_array = np.frombuffer(image_bytes, np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    log(f"[SCREEN] cv2.imdecode success={decoded is not None}")
    if decoded is not None:
        log(f"[SCREEN] image shape={decoded.shape}")


def get_screen():
    cached = get_screenshot_cache()
    if cached is not None:
        log("[SCREEN] Using cached screencap bytes")
        log(f"[SCREEN] bytes received={len(cached)}")
        image_bytes = cached
    else:
        log("[SCREEN] Starting screencap")
        image_bytes = run_adb(["exec-out", "screencap", "-p"])
        log(f"[SCREEN] bytes received={len(image_bytes) if image_bytes else 0}")
        set_screenshot_cache(image_bytes)

    _log_decode_diagnostics(image_bytes)
    screen = decode_image_bytes(image_bytes)
    log("[SCREEN] returning image")
    return screen


__all__ = [
    "begin_bot_screen_cycle",
    "clear_screenshot_cache",
    "get_screen",
]
