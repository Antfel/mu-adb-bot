import cv2
import numpy as np


def find_template(screen, template_path, threshold=0.85):
    template = cv2.imread(template_path)

    if template is None:
        raise Exception(f"No se pudo cargar template: {template_path}")

    result = cv2.matchTemplate(
        screen,
        template,
        cv2.TM_CCOEFF_NORMED
    )

    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    print("Confidence:", max_val)

    if max_val < threshold:
        return None

    h, w = template.shape[:2]

    return {
        "x": max_loc[0],
        "y": max_loc[1],
        "width": w,
        "height": h,
        "confidence": max_val,
        "center_x": max_loc[0] + w // 2,
        "center_y": max_loc[1] + h // 2
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