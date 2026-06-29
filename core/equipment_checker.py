from core.adb import bind_adb_device
from core.game_actions import ensure_inventory_open
from core.logger import log
from core.screen import get_screen
from core.vision import find_template

GUARDIAN_ANGEL_TEMPLATE = "templates/equipment/guardian_angel_equipped.png"
GUARDIAN_ANGEL_THRESHOLD = 0.80
GUARDIAN_SLOT_EMPTY_TEMPLATE = "templates/equipment/guardian_angel_inventory_empty.png"
GUARDIAN_SLOT_OCCUPIED_TEMPLATE = "templates/equipment/guardian_angel_inventory.png"

GUARDIAN_ANGEL_SLOT_REGION_REF = {
    "reference_width": 2560,
    "reference_height": 1440,
    "x1": 1017,
    "y1": 171,
    "x2": 1170,
    "y2": 365,
}


def _scale_guardian_angel_slot_region(screen):
    if screen is None:
        return None

    screen_h, screen_w = screen.shape[:2]
    ref_w = GUARDIAN_ANGEL_SLOT_REGION_REF["reference_width"]
    ref_h = GUARDIAN_ANGEL_SLOT_REGION_REF["reference_height"]
    scale_x = screen_w / ref_w
    scale_y = screen_h / ref_h

    x1 = int(GUARDIAN_ANGEL_SLOT_REGION_REF["x1"] * scale_x)
    y1 = int(GUARDIAN_ANGEL_SLOT_REGION_REF["y1"] * scale_y)
    x2 = int(GUARDIAN_ANGEL_SLOT_REGION_REF["x2"] * scale_x)
    y2 = int(GUARDIAN_ANGEL_SLOT_REGION_REF["y2"] * scale_y)

    x1 = max(0, min(x1, screen_w))
    x2 = max(0, min(x2, screen_w))
    y1 = max(0, min(y1, screen_h))
    y2 = max(0, min(y2, screen_h))

    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return None

    return {"x": x1, "y": y1, "width": width, "height": height}


def is_guardian_angel_equipped(device_id):
    if device_id:
        bind_adb_device(device_id)

    if not ensure_inventory_open():
        log("[EQUIPMENT] Guardian Angel missing")
        return False

    screen = get_screen()
    if screen is None:
        log("[EQUIPMENT] Guardian Angel missing")
        return False

    region = _scale_guardian_angel_slot_region(screen)
    match = None
    if region is not None:
        match = find_template(
            screen,
            GUARDIAN_ANGEL_TEMPLATE,
            threshold=GUARDIAN_ANGEL_THRESHOLD,
            region=region,
        )

    if match is None:
        match = find_template(
            screen,
            GUARDIAN_ANGEL_TEMPLATE,
            threshold=GUARDIAN_ANGEL_THRESHOLD,
        )

    if match is not None:
        log("[EQUIPMENT] Guardian Angel equipped")
        return True

    log("[EQUIPMENT] Guardian Angel missing")
    return False

def test_guardian_slot_templates(device_id):
    if device_id:
        bind_adb_device(device_id)

    ensure_inventory_open()

    screen = get_screen()
    region = _scale_guardian_angel_slot_region(screen)

    empty_match = find_template(
        screen,
        GUARDIAN_SLOT_EMPTY_TEMPLATE,
        threshold=0.50,
        region=region,
    )

    occupied_match = find_template(
        screen,
        GUARDIAN_SLOT_OCCUPIED_TEMPLATE,
        threshold=0.50,
        region=region,
    )

    import os
    import cv2

    os.makedirs("debug", exist_ok=True)

    if region is not None:
        x = region["x"]
        y = region["y"]
        w = region["width"]
        h = region["height"]
        region_crop = screen[y:y + h, x:x + w]
        cv2.imwrite("debug/guardian_slot_region.png", region_crop)
        print("REGION:", region)
        print("DEBUG:", "debug/guardian_slot_region.png")
    else:
        cv2.imwrite("debug/guardian_slot_full.png", screen)
        print("REGION: None")
        print("DEBUG:", "debug/guardian_slot_full.png")

    if empty_match is not None:
        x = empty_match["x"]
        y = empty_match["y"]
        w = empty_match["width"]
        h = empty_match["height"]
        crop = screen[y:y + h, x:x + w]
        cv2.imwrite("debug/guardian_slot_empty_match.png", crop)

    if occupied_match is not None:
        x = occupied_match["x"]
        y = occupied_match["y"]
        w = occupied_match["width"]
        h = occupied_match["height"]
        crop = screen[y:y + h, x:x + w]
        cv2.imwrite("debug/guardian_slot_occupied_match.png", crop)

    print("EMPTY:", empty_match)
    print("OCCUPIED:", occupied_match)