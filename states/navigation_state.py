from core.logger import log
from core.adb import tap, swipe
from core.actions import wait, run_sequence
from core.screen import get_screen
from core.vision import find_template
from core.ui import find_template_with_scroll
from core.profile import load_profile
from core.navigation_config import load_map_definition
from core.game_actions import clean_game_ui


MAP_BUTTON = {"x": 2440, "y": 120}

_WIRE_THRESHOLD = 0.8


def _normalize_wire_id(wire_id):
    return int(wire_id)


def _find_template(template_path, threshold=_WIRE_THRESHOLD, region=None):
    if not template_path:
        return None

    log(f"[VISION] Searching template: {template_path}")

    screen = get_screen()
    return find_template(
        screen,
        template_path,
        threshold=threshold,
        region=region,
    )


def _wire_row_region(wire_match):
    return {
        "x": max(0, wire_match["x"] - 40),
        "y": max(0, wire_match["y"] - 30),
        "width": wire_match["width"] + 300,
        "height": wire_match["height"] + 80,
    }


def _get_hud_template(wire_config, wire_id):
    templates = wire_config.get("templates", {})
    return templates.get("hud", {}).get(str(_normalize_wire_id(wire_id)))


def _get_option_template(wire_config, wire_id):
    templates = wire_config.get("templates", {})
    return templates.get("options", {}).get(str(_normalize_wire_id(wire_id)))


def _open_wire_popup(wire_config):
    templates = wire_config.get("templates", {})

    switch_button = _find_template(templates.get("switch_button"))
    if not switch_button:
        log("[NAVIGATION] Wire switch button not found")
        return False

    log("[NAVIGATION] Opening wire popup")
    tap(switch_button["center_x"], switch_button["center_y"])
    wait(1)

    popup_open = _find_template(templates.get("popup_open"))
    if not popup_open:
        log("[NAVIGATION] Wire popup did not open")
        return False

    log("[NAVIGATION] Wire popup open")
    return True


def _find_wire_option_with_scroll(wire_config, wire_id):
    option_template = _get_option_template(wire_config, wire_id)
    if not option_template:
        log(f"[NAVIGATION] Wire option template not configured for wire {wire_id}")
        return None

    scroll = wire_config.get("popup_scroll", {})
    max_attempts = scroll.get("max_attempts", 5)

    for attempt in range(max_attempts):
        wire_match = _find_template(option_template)
        if wire_match:
            log(f"[NAVIGATION] Wire option found (attempt {attempt + 1})")
            return wire_match

        if attempt < max_attempts - 1 and scroll:
            log(f"[NAVIGATION] Wire option not visible. Scroll #{attempt + 1}")
            swipe(
                scroll["x1"],
                scroll["y1"],
                scroll["x2"],
                scroll["y2"],
                scroll.get("duration", 300),
            )
            wait(1)

    log(f"[NAVIGATION] Wire option not found for wire {wire_id}")
    return None


def _is_wire_row_selected(wire_config, wire_match):
    templates = wire_config.get("templates", {})
    selected_template = templates.get("selected")
    if not selected_template:
        return False

    region = _wire_row_region(wire_match)
    return _find_template(selected_template, region=region) is not None


def _confirm_wire_switch(wire_config):
    templates = wire_config.get("templates", {})
    enter_button = _find_template(templates.get("enter_button"))
    if not enter_button:
        log("[NAVIGATION] Wire enter button not found")
        return False

    log("[NAVIGATION] Confirming wire switch")
    tap(enter_button["center_x"], enter_button["center_y"])
    wait(wire_config.get("switch_wait", 5))
    return True


def switch_to_wire(map_def, wire_id):
    wire_config = map_def.get("wire")
    if not wire_config:
        log("[NAVIGATION] Wire switching not configured")
        return True

    if not wire_config.get("enabled", False):
        log("[NAVIGATION] Wire switching disabled for this map")
        return True

    available_wires = [
        _normalize_wire_id(w) for w in wire_config.get("available_wires", [])
    ]
    if len(available_wires) <= 1:
        log("[NAVIGATION] Single wire map, skipping wire switch")
        return True

    try:
        wire_id = _normalize_wire_id(wire_id)
    except (TypeError, ValueError):
        log(f"[NAVIGATION] Invalid wire id: {wire_id}")
        return False

    if wire_id not in available_wires:
        log(
            f"[NAVIGATION] Wire {wire_id} not in available_wires: {available_wires}"
        )
        return False

    log(f"[NAVIGATION] Switching to wire {wire_id}")

    if wire_config.get("hud_detection", False):
        hud_template = _get_hud_template(wire_config, wire_id)
        if hud_template and _find_template(hud_template):
            log(f"[NAVIGATION] Already on wire {wire_id} (HUD)")
            return True

    if not _open_wire_popup(wire_config):
        return False

    wire_match = _find_wire_option_with_scroll(wire_config, wire_id)
    if not wire_match:
        return False

    confirm_ok = False

    if _is_wire_row_selected(wire_config, wire_match):
        log(f"[NAVIGATION] Wire {wire_id} already selected in popup")
        confirm_ok = _confirm_wire_switch(wire_config)
        if not confirm_ok:
            return False
    else:
        log(f"[NAVIGATION] Selecting wire {wire_id}")
        tap(wire_match["center_x"], wire_match["center_y"])
        wait(1)

        if not _is_wire_row_selected(wire_config, wire_match):
            log(f"[NAVIGATION] Wire {wire_id} selection not confirmed in row")
        else:
            log(f"[NAVIGATION] Wire {wire_id} row selected")

        confirm_ok = _confirm_wire_switch(wire_config)
        if not confirm_ok:
            return False

    if wire_config.get("hud_detection", False):
        hud_template = _get_hud_template(wire_config, wire_id)
        if hud_template and _find_template(hud_template):
            log(f"[NAVIGATION] Wire {wire_id} confirmed via HUD")
            return True

        log(
            f"[NAVIGATION] HUD did not confirm wire {wire_id} after switch"
        )
        if confirm_ok:
            log("[NAVIGATION] Continuing after successful enter confirmation")
            return True
        return False

    return True


def go_to_active_farm_spot():
    profile = load_profile()
    map_id = profile["map"]
    wire_id = profile["wire"]
    spot_id = profile["spot"]

    map_def = load_map_definition(map_id)
    navigation = map_def["navigation"]
    spot = map_def["spots"][spot_id]

    log(
        f"[NAVIGATION] Going to: {map_def['name']} | "
        f"{wire_id} | {spot['name']}"
    )

    log("[NAVIGATION] Cleaning UI before navigation")
    clean_game_ui()

    tap(MAP_BUTTON["x"], MAP_BUTTON["y"])
    wait(2)

    head = find_template_with_scroll(
        navigation["map_head_template"],
        threshold=0.8,
        swipe_coords=navigation.get("map_list_swipe"),
    )

    if not head:
        log("[NAVIGATION] Map head not found")
        return False

    tap(head["center_x"], head["center_y"])
    wait(2)

    map_option = find_template_with_scroll(
        navigation["map_option_template"],
        threshold=0.8,
        swipe_coords=navigation.get("map_list_swipe"),
    )

    if not map_option:
        log("[NAVIGATION] Map option not found")
        return False

    tap(map_option["center_x"], map_option["center_y"])
    wait(2)

    screen = get_screen()

    checked = find_template(
        screen,
        navigation["checked_template"],
        threshold=0.8,
    )

    if not checked:
        log("[NAVIGATION] Map option not checked")
        return False

    log("[NAVIGATION] Map option checked")

    screen = get_screen()

    enter = find_template(
        screen,
        navigation["enter_template"],
        threshold=0.8,
    )

    if not enter:
        log("[NAVIGATION] Enter button not found")
        return False

    tap(enter["center_x"], enter["center_y"])

    log("[NAVIGATION] Entering map")

    wait(navigation.get("enter_wait", 8))

    if not switch_to_wire(map_def, wire_id):
        return False

    log("[NAVIGATION] Opening map inside target map")

    tap(MAP_BUTTON["x"], MAP_BUTTON["y"])
    wait(2)

    spot_click = spot["spot_click"]

    log("[NAVIGATION] Clicking farm spot")

    tap(spot_click["x"], spot_click["y"])

    log("[NAVIGATION] Closing map")

    tap(MAP_BUTTON["x"], MAP_BUTTON["y"])
    wait(1)

    run_sequence(spot.get("post_spot_actions", []))

    wait(spot.get("arrival_wait", 20))

    log("[NAVIGATION] Arrived to farm spot")

    return True
