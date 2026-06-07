import re

import cv2
import numpy as np

from core.adb import bind_adb_device
from core.device_manager import get_device_screenshot
from core.logger import log
from core.path_utils import get_app_root
from core.screen import get_screen

try:
    import pytesseract
except ImportError:
    pytesseract = None


DEBUG_DIR = get_app_root() / "debug"
DEBUG_COORD_OCR = False

COORD_REGION_REF = {
    "reference_width": 2560,
    "reference_height": 1440,
    "x1": 2435,
    "y1": 250,
    "x2": 2550,
    "y2": 285,
}

OCR_UPSCALE = 3
TESSERACT_CONFIG = (
    r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789(), "
)


def _scale_coord_region(screen):
    if screen is None:
        return None

    screen_h, screen_w = screen.shape[:2]
    ref_w = COORD_REGION_REF["reference_width"]
    ref_h = COORD_REGION_REF["reference_height"]
    scale_x = screen_w / ref_w
    scale_y = screen_h / ref_h

    x1 = int(COORD_REGION_REF["x1"] * scale_x)
    y1 = int(COORD_REGION_REF["y1"] * scale_y)
    x2 = int(COORD_REGION_REF["x2"] * scale_x)
    y2 = int(COORD_REGION_REF["y2"] * scale_y)

    x1 = max(0, min(x1, screen_w))
    x2 = max(0, min(x2, screen_w))
    y1 = max(0, min(y1, screen_h))
    y2 = max(0, min(y2, screen_h))

    if x2 <= x1 or y2 <= y1:
        return None

    crop = screen[y1:y2, x1:x2]
    return crop if crop.size > 0 else None


def _preprocess_coord_crop(crop):
    if crop is None or crop.size == 0:
        return None

    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop.copy()

    upscaled = cv2.resize(
        gray,
        None,
        fx=OCR_UPSCALE,
        fy=OCR_UPSCALE,
        interpolation=cv2.INTER_CUBIC,
    )
    blurred = cv2.GaussianBlur(upscaled, (3, 3), 0)
    _, thresholded = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    return thresholded


def _save_coord_debug(crop, processed, *, ocr_failed=False):
    if not (DEBUG_COORD_OCR or ocr_failed):
        return

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    if crop is not None and crop.size > 0:
        cv2.imwrite(str(DEBUG_DIR / "coord_crop_raw.png"), crop)
    if processed is not None and processed.size > 0:
        cv2.imwrite(str(DEBUG_DIR / "coord_crop_processed.png"), processed)


def _parse_coordinates(raw_text):
    text = raw_text or ""
    log(f"[COORD] OCR raw text: {text!r}")

    paren_match = re.search(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)", text)
    if paren_match:
        return int(paren_match.group(1)), int(paren_match.group(2))

    comma_match = re.search(r"(\d+)\s*,\s*(\d+)", text)
    if comma_match:
        return int(comma_match.group(1)), int(comma_match.group(2))

    numbers = re.findall(r"\d+", text)
    if len(numbers) >= 2:
        return int(numbers[0]), int(numbers[1])

    return None


def read_current_coordinates(device_id):
    if device_id:
        bind_adb_device(device_id)

    screen = get_screen()
    if screen is None:
        try:
            screen = get_device_screenshot(device_id)
        except Exception as exc:
            log(f"[COORD] Failed to read coordinates: screenshot unavailable ({exc})")
            return None

    if screen is None:
        log("[COORD] Failed to read coordinates")
        return None

    log("[COORD] Crop region: (2435,250)-(2550,285)")

    crop = _scale_coord_region(screen)
    if crop is None:
        log("[COORD] Failed to read coordinates")
        return None

    processed = _preprocess_coord_crop(crop)
    if processed is None:
        log("[COORD] Failed to read coordinates")
        _save_coord_debug(crop, processed, ocr_failed=True)
        return None

    if pytesseract is None:
        log("[COORD] Failed to read coordinates: pytesseract not installed")
        _save_coord_debug(crop, processed, ocr_failed=True)
        return None

    try:
        raw_text = pytesseract.image_to_string(processed, config=TESSERACT_CONFIG)
    except pytesseract.TesseractNotFoundError:
        log("[COORD] Failed to read coordinates: tesseract binary not found")
        _save_coord_debug(crop, processed, ocr_failed=True)
        return None
    except Exception as exc:
        log(f"[COORD] Failed to read coordinates: {exc}")
        _save_coord_debug(crop, processed, ocr_failed=True)
        return None

    parsed = _parse_coordinates(raw_text)
    if parsed is None:
        log("[COORD] Failed to read coordinates")
        _save_coord_debug(crop, processed, ocr_failed=True)
        return None

    if DEBUG_COORD_OCR:
        _save_coord_debug(crop, processed, ocr_failed=False)

    log(f"[COORD] Current coordinates: ({parsed[0]},{parsed[1]})")
    return parsed
