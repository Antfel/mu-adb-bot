import re

import cv2
import numpy as np

from core.adb import bind_adb_device
from core.logger import log
from core.screen import get_screen
from core.vision import find_template, probe_template

try:
    import pytesseract
except ImportError:
    pytesseract = None


_MAP_TEMPLATE_THRESHOLD = 0.8
_OCR_UPSCALE = 3
_OCR_CONFIG = r"--oem 3 --psm 7"


def resolve_current_map_threshold(navigation):
    detection = navigation.get("current_map_detection")
    if isinstance(detection, dict) and detection.get("threshold") is not None:
        try:
            return float(detection["threshold"])
        except (TypeError, ValueError):
            pass

    if navigation.get("current_map_threshold") is not None:
        try:
            return float(navigation["current_map_threshold"])
        except (TypeError, ValueError):
            pass

    return _MAP_TEMPLATE_THRESHOLD


def probe_current_map_match(screen, navigation):
    """
    Template current-map check without global threshold.
    Returns (matched, confidence, threshold).
    """
    current_template = navigation.get("current_map_template")
    threshold = resolve_current_map_threshold(navigation)
    if not current_template:
        return False, 0.0, threshold

    confidence, _match = probe_template(screen, current_template)
    return confidence >= threshold, confidence, threshold


def _resolve_detection_method(navigation):
    detection = navigation.get("current_map_detection")
    if not isinstance(detection, dict):
        return "template"
    method = detection.get("method", "template")
    return str(method).strip().lower() if method else "template"


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


def _scale_ocr_region(region, screen_w, screen_h, map_def):
    if not isinstance(region, dict):
        return None

    maintenance = map_def.get("maintenance", {}) if map_def else {}
    ref_w = region.get("reference_width") or maintenance.get("image_width") or 2560
    ref_h = region.get("reference_height") or maintenance.get("image_height") or 1440

    try:
        ref_w = float(ref_w)
        ref_h = float(ref_h)
    except (TypeError, ValueError):
        return None

    if ref_w <= 0 or ref_h <= 0:
        return None

    scale_x = screen_w / ref_w
    scale_y = screen_h / ref_h

    if "x1" in region or "x2" in region or "y1" in region or "y2" in region:
        x1 = region.get("x1", 0)
        y1 = region.get("y1", 0)
        x2 = region.get("x2", x1)
        y2 = region.get("y2", y1)
    else:
        x1 = region.get("x", 0)
        y1 = region.get("y", 0)
        width = region.get("width", 0)
        height = region.get("height", 0)
        x2 = x1 + width
        y2 = y1 + height

    return _clamp_region(
        float(x1) * scale_x,
        float(y1) * scale_y,
        float(x2) * scale_x,
        float(y2) * scale_y,
        screen_w,
        screen_h,
    )


def _preprocess_ocr_crop(crop):
    if crop is None or crop.size == 0:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    upscaled = cv2.resize(
        gray,
        None,
        fx=_OCR_UPSCALE,
        fy=_OCR_UPSCALE,
        interpolation=cv2.INTER_CUBIC,
    )
    _, binary = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _normalize_ocr_text(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _ocr_text_matches(actual, expected):
    actual_n = _normalize_ocr_text(actual)
    expected_n = _normalize_ocr_text(expected)
    if not expected_n:
        return False
    return expected_n in actual_n


def _read_region_text(screen, region, map_def):
    if pytesseract is None:
        log("[MAP] OCR detection unavailable: pytesseract not installed")
        return ""

    screen_h, screen_w = screen.shape[:2]
    scaled = _scale_ocr_region(region, screen_w, screen_h, map_def)
    if not scaled:
        log("[MAP] OCR detection failed: invalid region")
        return ""

    x = scaled["x"]
    y = scaled["y"]
    w = scaled["width"]
    h = scaled["height"]
    crop = screen[y : y + h, x : x + w]
    processed = _preprocess_ocr_crop(crop)
    if processed is None or processed.size == 0:
        log("[MAP] OCR detection failed: empty crop")
        return ""

    try:
        return pytesseract.image_to_string(processed, config=_OCR_CONFIG)
    except pytesseract.TesseractNotFoundError:
        log("[MAP] OCR detection failed: tesseract binary not found")
        return ""
    except Exception as exc:
        log(f"[MAP] OCR detection failed: {exc}")
        return ""


def _is_current_map_template(screen, navigation):
    matched, _confidence, _threshold = probe_current_map_match(screen, navigation)
    return matched


def _is_current_map_ocr(screen, navigation, map_def):
    detection = navigation.get("current_map_detection", {})
    region = detection.get("region")
    expected_text = detection.get("expected_text")

    if not region or not expected_text:
        log("[MAP] OCR detection missing region or expected_text")
        return False

    text = _read_region_text(screen, region, map_def)
    if not text.strip():
        return False

    matched = _ocr_text_matches(text, expected_text)
    if matched:
        log(f"[MAP] OCR current map matched: {expected_text!r}")
    return matched


def is_current_map(device_id, map_def, screen=None):
    """
    Detect whether the screen shows the map defined by map_def.
    Uses template matching by default; OCR when navigation.current_map_detection
    requests it.
    """
    if device_id:
        bind_adb_device(device_id)

    if screen is None:
        screen = get_screen()

    if screen is None:
        return False

    navigation = map_def.get("navigation", {})
    method = _resolve_detection_method(navigation)

    if method == "ocr":
        return _is_current_map_ocr(screen, navigation, map_def)

    if method != "template":
        map_id = map_def.get("id", "?")
        log(f"[MAP] Unknown current_map_detection method {method!r} for {map_id}")
        return _is_current_map_template(screen, navigation)

    return _is_current_map_template(screen, navigation)
