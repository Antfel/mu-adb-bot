import os

import cv2
import numpy as np

from core.logger import log
from core.path_utils import resource_path


def _resolve_template_path(template_path):
    if os.path.isabs(template_path):
        return template_path
    return resource_path(template_path)


def decode_image_bytes(image_bytes):
    if image_bytes is None:
        raise RuntimeError("[VISION] Empty image bytes from screenshot")

    if len(image_bytes) == 0:
        raise RuntimeError("[VISION] Empty image bytes from screenshot")

    image_array = np.frombuffer(image_bytes, np.uint8)
    screen = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if screen is None:
        raise RuntimeError("[VISION] Failed to decode screenshot bytes")

    return screen


def find_template(screen, template_path, threshold=0.85, region=None):
    if screen is None:
        raise RuntimeError("[VISION] Empty screen from screenshot")

    template_path = _resolve_template_path(template_path)
    template = cv2.imread(template_path)

    if template is None:
        raise RuntimeError(f"[VISION] Failed to load template: {template_path}")

    search_screen = screen
    offset_x = 0
    offset_y = 0

    template_h, template_w = template.shape[:2]

    if region is not None:
        screen_h, screen_w = screen.shape[:2]
        offset_x = max(0, min(int(region["x"]), screen_w))
        offset_y = max(0, min(int(region["y"]), screen_h))
        region_w = max(0, int(region["width"]))
        region_h = max(0, int(region["height"]))
        region_w = min(region_w, screen_w - offset_x)
        region_h = min(region_h, screen_h - offset_y)

        if region_w <= 0 or region_h <= 0:
            return None

        search_screen = screen[offset_y:offset_y + region_h, offset_x:offset_x + region_w]

    search_h, search_w = search_screen.shape[:2]
    if search_h < template_h or search_w < template_w:
        return None

    try:
        result = cv2.matchTemplate(
            search_screen,
            template,
            cv2.TM_CCOEFF_NORMED,
        )
    except Exception:
        log(f"[VISION] matchTemplate failed for: {template_path}")
        log(f"[VISION] region={region}")
        log(f"[VISION] screen size={search_screen.shape[:2]}")
        log(f"[VISION] template size={template.shape[:2]}")
        raise

    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    print("Confidence:", max_val)

    if max_val < threshold:
        return None

    match_x = max_loc[0] + offset_x
    match_y = max_loc[1] + offset_y

    return {
        "x": match_x,
        "y": match_y,
        "width": template_w,
        "height": template_h,
        "confidence": max_val,
        "center_x": match_x + template_w // 2,
        "center_y": match_y + template_h // 2
    }


def probe_template(screen, template_path, region=None):
    """Return max confidence and match metadata without applying a threshold."""
    if screen is None:
        raise RuntimeError("[VISION] Empty screen from screenshot")

    template_path = _resolve_template_path(template_path)
    template = cv2.imread(template_path)

    if template is None:
        raise RuntimeError(f"[VISION] Failed to load template: {template_path}")

    search_screen = screen
    offset_x = 0
    offset_y = 0
    template_h, template_w = template.shape[:2]

    if region is not None:
        screen_h, screen_w = screen.shape[:2]
        offset_x = max(0, min(int(region["x"]), screen_w))
        offset_y = max(0, min(int(region["y"]), screen_h))
        region_w = max(0, int(region["width"]))
        region_h = max(0, int(region["height"]))
        region_w = min(region_w, screen_w - offset_x)
        region_h = min(region_h, screen_h - offset_y)

        if region_w <= 0 or region_h <= 0:
            return 0.0, None

        search_screen = screen[offset_y : offset_y + region_h, offset_x : offset_x + region_w]

    search_h, search_w = search_screen.shape[:2]
    if search_h < template_h or search_w < template_w:
        return 0.0, None

    result = cv2.matchTemplate(
        search_screen,
        template,
        cv2.TM_CCOEFF_NORMED,
    )
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    match_x = max_loc[0] + offset_x
    match_y = max_loc[1] + offset_y

    return float(max_val), {
        "x": match_x,
        "y": match_y,
        "width": template_w,
        "height": template_h,
        "confidence": float(max_val),
        "center_x": match_x + template_w // 2,
        "center_y": match_y + template_h // 2,
    }


def draw_match(screen, match):
    debug = screen.copy()

    x = match["x"]
    y = match["y"]
    w = match["width"]
    h = match["height"]

    cv2.rectangle(
        debug,
        (x, y),
        (x + w, y + h),
        (0, 255, 0),
        2
    )

    return debug