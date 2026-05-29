import re
from pathlib import Path

import cv2
import numpy as np

from core.device_manager import get_device_screenshot
from core.logger import log
from core.path_utils import get_app_root, resource_path
from core.vision import decode_image_bytes, find_template

try:
    import pytesseract
except ImportError:
    pytesseract = None


LEVEL_REGION_TEMPLATE = Path(
    resource_path("templates/ui/common/level_region_reference.png")
)
DEBUG_DIR = get_app_root() / "debug"

USE_FIXED_LEVEL_REGION = True

# Fixed HUD crop for 960x540 (bottom-left: "Level 383 48.7%")
FIXED_LEVEL_REFERENCE_WIDTH = 960
FIXED_LEVEL_REFERENCE_HEIGHT = 540
FIXED_LEVEL_X1 = 0
FIXED_LEVEL_Y1 = 500
FIXED_LEVEL_X2 = 130
FIXED_LEVEL_Y2 = 535

# Template anchor fallback (USE_FIXED_LEVEL_REGION=False)
LEVEL_TEMPLATE_THRESHOLD = 0.75
LEVEL_CROP_LEFT_OFFSET = 35
LEVEL_CROP_RIGHT_OFFSET = 140
LEVEL_CROP_TOP_OFFSET = -5
LEVEL_CROP_BOTTOM_OFFSET = 25

LEVEL_MIN = 1
LEVEL_MAX = 1000
OCR_UPSCALE = 3
TESSERACT_CONFIG = r"--oem 3 --psm 7"
TESSERACT_CONFIG_DIGITS_ONLY = (
    r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789"
)
DEBUG_LEVEL_OCR = False


def _save_level_debug(crop, processed, *, ocr_failed=False):
    if not (DEBUG_LEVEL_OCR or ocr_failed):
        return

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    if crop is not None and crop.size > 0:
        cv2.imwrite(str(DEBUG_DIR / "level_crop_raw.png"), crop)

    if processed is not None and processed.size > 0:
        cv2.imwrite(str(DEBUG_DIR / "level_crop_processed.png"), processed)


def _clamp_region(x1, y1, x2, y2, screen_w, screen_h):
    x1 = max(0, min(int(x1), screen_w))
    x2 = max(0, min(int(x2), screen_w))
    y1 = max(0, min(int(y1), screen_h))
    y2 = max(0, min(int(y2), screen_h))

    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return None

    return {"x": x1, "y": y1, "width": width, "height": height}


def locate_fixed_level_region(screen):
    screen_h, screen_w = screen.shape[:2]
    scale_x = screen_w / FIXED_LEVEL_REFERENCE_WIDTH
    scale_y = screen_h / FIXED_LEVEL_REFERENCE_HEIGHT

    x1 = FIXED_LEVEL_X1 * scale_x
    x2 = FIXED_LEVEL_X2 * scale_x
    y1 = FIXED_LEVEL_Y1 * scale_y
    y2 = FIXED_LEVEL_Y2 * scale_y

    region = _clamp_region(x1, y1, x2, y2, screen_w, screen_h)
    if region:
        region["mode"] = "fixed"
    return region


def locate_level_region_anchor(screen):
    if not LEVEL_REGION_TEMPLATE.exists():
        log(f"[LEVEL] OCR failed: template missing at {LEVEL_REGION_TEMPLATE}")
        return None

    match = find_template(
        screen,
        str(LEVEL_REGION_TEMPLATE),
        threshold=LEVEL_TEMPLATE_THRESHOLD,
    )
    if not match:
        return None

    screen_h, screen_w = screen.shape[:2]
    x1 = match["x"] + LEVEL_CROP_LEFT_OFFSET
    x2 = match["x"] + LEVEL_CROP_RIGHT_OFFSET
    y1 = match["y"] + LEVEL_CROP_TOP_OFFSET
    y2 = match["y"] + LEVEL_CROP_BOTTOM_OFFSET

    region = _clamp_region(x1, y1, x2, y2, screen_w, screen_h)
    if region:
        region["template_confidence"] = match.get("confidence")
        region["mode"] = "anchor"
    return region


def locate_level_region(screen):
    if USE_FIXED_LEVEL_REGION:
        return locate_fixed_level_region(screen)
    return locate_level_region_anchor(screen)


def preprocess_level_image(image):
    if image is None or image.size == 0:
        return None

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

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

    sharpen_kernel = np.array(
        [[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]],
        dtype=np.float32,
    )
    sharpened = cv2.filter2D(thresholded, -1, sharpen_kernel)
    return sharpened


def _parse_level_fallback_numbers(text):
    scrubbed = re.sub(r"\d+\.\d+%?", " ", text)
    scrubbed = re.sub(r"%", " ", scrubbed)
    scrubbed = re.sub(r"[^\d\s]", " ", scrubbed)
    scrubbed = " ".join(scrubbed.split())

    number_strings = re.findall(r"\d+", scrubbed)
    if not number_strings:
        return None

    in_range = []
    for num_str in number_strings:
        try:
            value = int(num_str)
        except ValueError:
            continue
        if LEVEL_MIN <= value <= LEVEL_MAX:
            in_range.append((len(num_str), value))

    if not in_range:
        return None

    multi_digit = [item for item in in_range if 2 <= item[0] <= 4]
    if multi_digit:
        multi_digit.sort(key=lambda item: (-item[0], -item[1]))
        for digit_len, value in multi_digit:
            if 10 <= value <= LEVEL_MAX:
                return value
        return multi_digit[0][1]

    if len(in_range) == 1 and in_range[0][0] == 1:
        return in_range[0][1]

    return None


def _parse_level_from_raw_text(raw_text):
    text = raw_text or ""
    log(f"[LEVEL] OCR raw text: {text!r}")

    level_match = re.search(r"Level\s*(\d{1,4})", text, re.IGNORECASE)
    if level_match:
        level = int(level_match.group(1))
        if LEVEL_MIN <= level <= LEVEL_MAX:
            return level

    return _parse_level_fallback_numbers(text)


def extract_level_text(image):
    if image is None:
        return None

    if pytesseract is None:
        log("[LEVEL] OCR failed: pytesseract not installed")
        return None

    ocr_config = TESSERACT_CONFIG if USE_FIXED_LEVEL_REGION else TESSERACT_CONFIG_DIGITS_ONLY

    try:
        raw_text = pytesseract.image_to_string(image, config=ocr_config)
    except pytesseract.TesseractNotFoundError:
        log("[LEVEL] OCR failed: tesseract binary not found")
        return None
    except Exception as exc:
        log(f"[LEVEL] OCR failed: tesseract error ({exc})")
        return None

    level = _parse_level_from_raw_text(raw_text)
    if level is None:
        log("[LEVEL] OCR failed: could not parse valid level from raw text")
        return None

    return level


def read_character_level(device_id):
    if not device_id:
        log("[LEVEL] OCR failed: no device selected")
        return None

    png_bytes = get_device_screenshot(device_id)
    if not png_bytes:
        log("[LEVEL] OCR failed: screenshot unavailable")
        return None

    try:
        screen = decode_image_bytes(png_bytes)
    except RuntimeError as exc:
        log(f"[LEVEL] OCR failed: {exc}")
        return None

    region = locate_level_region(screen)
    if not region:
        log("[LEVEL] OCR failed: level region not located")
        return None

    mode = region.get("mode", "unknown")
    log(f"[LEVEL] Using level region mode: {mode}")

    x = region["x"]
    y = region["y"]
    w = region["width"]
    h = region["height"]
    crop = screen[y : y + h, x : x + w]
    if crop.size == 0:
        log("[LEVEL] OCR failed: empty level crop")
        return None

    processed = preprocess_level_image(crop)
    if processed is None:
        log("[LEVEL] OCR failed: preprocess returned empty image")
        _save_level_debug(crop, processed, ocr_failed=True)
        return None

    level = extract_level_text(processed)
    if level is None:
        _save_level_debug(crop, processed, ocr_failed=True)
        log("[LEVEL] OCR failed: could not parse level digits")
        return None

    if DEBUG_LEVEL_OCR:
        _save_level_debug(crop, processed, ocr_failed=False)

    log(f"[LEVEL] Character level detected: {level}")
    log("[LEVEL] OCR success")
    return level
