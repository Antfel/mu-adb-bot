import time
from pathlib import Path

from core.logger import log
from core.adb import bind_adb_device, tap, swipe
from core.actions import wait, run_sequence
from core.screen import get_screen
from core.vision import find_template
from core.ui import find_template_with_scroll
from core.profile import get_current_profile_name, load_profile
from core.navigation_config import (
    IMPLEMENTED_NAVIGATION_BEHAVIORS,
    is_navigation_implemented,
    is_navigation_supported,
    load_map_definition,
    log_unsupported_navigation_behavior,
    navigation_behavior,
)
from core.coordinate_mapping import (
    DEFAULT_ARRIVAL_RADIUS,
    distance_coords,
    location_has_coordinates,
)
from core.coordinate_reader import read_current_coordinates
from core.current_map_detection import is_current_map
from core.game_actions import clean_game_ui, ensure_auto_mode
from core.special_locations import get_farm_spot_location
from states.map_state import resolve_expected_farm_map_id
from core.path_utils import resource_path
from coordinates.ui import CLOSE_BUTTON, CLOSE_X_TEMPLATE, MAP_WINDOW_OPEN_TEMPLATE


MAP_BUTTON = {"x": 2440, "y": 120}
_MAP_WINDOW_THRESHOLD = 0.8
_POST_TELEPORT_MAP_SETTLE_SECONDS = 1.5

_WIRE_THRESHOLD = 0.8
AUTO_NAVIGATING_TEMPLATE = "templates/ui/common/auto_navigating.png"
_AUTO_NAV_THRESHOLD = 0.70
_AUTO_NAV_TIMEOUT = 180
_AUTO_NAV_POLL_SECONDS = 1
_AUTO_NAV_INITIAL_WAIT = 2
_AUTO_NAV_FINISH_GRACE_SECONDS = 1.5
_AUTO_NAV_MISSES_TO_FINISH = 3
_AUTO_NAV_START_ATTEMPTS = 4
_MOVEMENT_CHECK_REGION_REF = {
    "reference_width": 2560,
    "reference_height": 1440,
    "x1": 400,
    "y1": 250,
    "x2": 1600,
    "y2": 1000,
}
_STABILITY_CHECK_TIMEOUT_SECONDS = 10.0

_COMMON_WIRE_SWITCH_DEFAULTS = {
    "enabled": True,
    "hud_detection": True,
    "templates": {
        "switch_button": "templates/wires/common/switch_button.png",
        "popup_open": "templates/wires/common/wire_popup_open.png",
        "enter_button": "templates/wires/common/wire_enter_button.png",
        "selected": "templates/wires/common/wire_selected.png",
    },
    "popup_scroll": {
        "x1": 930,
        "y1": 560,
        "x2": 930,
        "y2": 300,
        "duration": 300,
        "max_attempts": 5,
    },
    "switch_wait": 5,
}


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

    log("[WIRE] Opening wire selector")
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


def _wire_count_from_metadata(map_def):
    wire_value = map_def.get("wire")
    if isinstance(wire_value, bool):
        return None
    if isinstance(wire_value, int) and wire_value > 1:
        return wire_value
    if isinstance(wire_value, str):
        try:
            count = int(wire_value.strip())
            return count if count > 1 else None
        except (TypeError, ValueError):
            return None

    wires = map_def.get("wires")
    if isinstance(wires, dict) and len(wires) > 1:
        return len(wires)

    return None


def _common_wire_template_exists(relative_path):
    return Path(resource_path(relative_path)).is_file()


def _build_inferred_wire_switch_config(map_def):
    wire_count = _wire_count_from_metadata(map_def)
    if not wire_count or wire_count <= 1:
        return None

    options = {}
    hud = {}
    for wire_id in range(1, wire_count + 1):
        option_path = f"templates/wires/common/wire_{wire_id}_option.png"
        if _common_wire_template_exists(option_path):
            options[str(wire_id)] = option_path

        hud_path = f"templates/wires/common/wire_{wire_id}_hud.png"
        if _common_wire_template_exists(hud_path):
            hud[str(wire_id)] = hud_path

    if not options:
        return None

    config = {
        **_COMMON_WIRE_SWITCH_DEFAULTS,
        "available_wires": list(range(1, wire_count + 1)),
        "templates": {
            **_COMMON_WIRE_SWITCH_DEFAULTS["templates"],
            "options": options,
            "hud": hud,
        },
    }
    return config


def _map_supports_wire_switch(map_def):
    wire_config = _get_wire_switch_config(map_def)
    if not wire_config or not wire_config.get("enabled", False):
        return False

    available_wires = wire_config.get("available_wires", [])
    return len(available_wires) > 1


def _get_wire_switch_config(map_def):
    wire_config = map_def.get("wire_switch")
    if isinstance(wire_config, dict):
        return wire_config
    legacy = map_def.get("wire")
    if isinstance(legacy, dict):
        return legacy
    return _build_inferred_wire_switch_config(map_def)


def switch_to_wire(map_def, wire_id):
    try:
        wire_id = _normalize_wire_id(wire_id)
    except (TypeError, ValueError):
        log(f"[NAVIGATION] Invalid wire id: {wire_id}")
        return False

    log(f"[WIRE] Requested wire: {wire_id}")
    supports_wires = _map_supports_wire_switch(map_def)
    log(f"[WIRE] Current map supports wires: {supports_wires}")

    if wire_id == 1:
        log("[WIRE] Skipping wire switch: wire=1")
        return True

    wire_config = _get_wire_switch_config(map_def)
    if not wire_config:
        log("[NAVIGATION] Wire switching not configured")
        return False

    if not wire_config.get("enabled", False):
        log("[NAVIGATION] Wire switching disabled for this map")
        return False

    available_wires = [
        _normalize_wire_id(w) for w in wire_config.get("available_wires", [])
    ]
    if len(available_wires) <= 1:
        log("[NAVIGATION] Single wire map, skipping wire switch")
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
            log("[WIRE] Wire selection completed")
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
        log(f"[WIRE] Selecting wire {wire_id}")
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
            log("[WIRE] Wire selection completed")
            return True

        log(
            f"[NAVIGATION] HUD did not confirm wire {wire_id} after switch"
        )
        if confirm_ok:
            log("[NAVIGATION] Continuing after successful enter confirmation")
            log("[WIRE] Wire selection completed")
            return True
        return False

    log("[WIRE] Wire selection completed")
    return True


def _is_auto_navigating():
    screen = get_screen()
    return (
        find_template(
            screen,
            AUTO_NAVIGATING_TEMPLATE,
            threshold=_AUTO_NAV_THRESHOLD,
        )
        is not None
    )


def _movement_check_crop(screen):
    if screen is None:
        return None

    screen_h, screen_w = screen.shape[:2]
    ref_w = _MOVEMENT_CHECK_REGION_REF["reference_width"]
    ref_h = _MOVEMENT_CHECK_REGION_REF["reference_height"]
    scale_x = screen_w / ref_w
    scale_y = screen_h / ref_h

    x1 = int(_MOVEMENT_CHECK_REGION_REF["x1"] * scale_x)
    y1 = int(_MOVEMENT_CHECK_REGION_REF["y1"] * scale_y)
    x2 = int(_MOVEMENT_CHECK_REGION_REF["x2"] * scale_x)
    y2 = int(_MOVEMENT_CHECK_REGION_REF["y2"] * scale_y)

    x1 = max(0, min(x1, screen_w))
    x2 = max(0, min(x2, screen_w))
    y1 = max(0, min(y1, screen_h))
    y2 = max(0, min(y2, screen_h))

    if x2 <= x1 or y2 <= y1:
        return screen

    crop = screen[y1:y2, x1:x2]
    return crop if crop.size > 0 else screen


def _region_similarity(region_a, region_b):
    import numpy as np

    if region_a is None or region_b is None or region_a.size == 0 or region_b.size == 0:
        return 0.0

    if region_a.shape != region_b.shape:
        height = min(region_a.shape[0], region_b.shape[0])
        width = min(region_a.shape[1], region_b.shape[1])
        region_a = region_a[:height, :width]
        region_b = region_b[:height, :width]

    diff = np.abs(
        region_a.astype(np.float32) - region_b.astype(np.float32)
    ).mean() / 255.0
    return 1.0 - float(diff)


def _save_stability_debug(region_a, region_b):
    import cv2

    from core.path_utils import get_app_root

    debug_dir = get_app_root() / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    if region_a is not None and region_a.size > 0:
        cv2.imwrite(str(debug_dir / "navigation_stability_a.png"), region_a)
    if region_b is not None and region_b.size > 0:
        cv2.imwrite(str(debug_dir / "navigation_stability_b.png"), region_b)


def wait_for_screen_stability(
    device_id,
    samples=3,
    interval=1.0,
    threshold=0.98,
    timeout=None,
):
    if device_id:
        bind_adb_device(device_id)

    if timeout is None:
        timeout = _STABILITY_CHECK_TIMEOUT_SECONDS

    stable_count = 0
    start = time.time()
    last_region_a = None
    last_region_b = None

    while time.time() - start < timeout:
        screen_a = get_screen()
        wait(interval)
        screen_b = get_screen()

        region_a = _movement_check_crop(screen_a)
        region_b = _movement_check_crop(screen_b)
        last_region_a = region_a
        last_region_b = region_b

        similarity = _region_similarity(region_a, region_b)
        if similarity >= threshold:
            stable_count += 1
            if stable_count >= samples:
                log("[NAVIGATION] Screen stable; navigation complete")
                return True
        else:
            stable_count = 0

    _save_stability_debug(last_region_a, last_region_b)
    return False


def wait_until_navigation_complete(device_id=None):
    log("[NAVIGATION] Waiting for auto navigation to start")
    wait(_AUTO_NAV_INITIAL_WAIT)

    tracking = False
    for attempt in range(1, _AUTO_NAV_START_ATTEMPTS + 1):
        if _is_auto_navigating():
            log("[NAVIGATION] Auto navigating detected")
            tracking = True
            break
        if attempt < _AUTO_NAV_START_ATTEMPTS:
            wait(_AUTO_NAV_POLL_SECONDS)

    if not tracking:
        log(
            "[NAVIGATION] Auto navigation template not detected "
            "after start attempts"
        )
        wait_for_screen_stability(
            device_id,
            samples=2,
            interval=0.5,
            threshold=0.98,
            timeout=5.0,
        )
        return True

    start = time.time()
    misses = 0

    while True:
        if time.time() - start > _AUTO_NAV_TIMEOUT:
            log("[NAVIGATION] Navigation wait timeout")
            return False

        if _is_auto_navigating():
            misses = 0
        else:
            misses += 1
            log(
                f"[NAVIGATION] Auto navigating miss "
                f"{misses}/{_AUTO_NAV_MISSES_TO_FINISH}"
            )
            if misses >= _AUTO_NAV_MISSES_TO_FINISH:
                if wait_for_screen_stability(device_id):
                    wait(_AUTO_NAV_FINISH_GRACE_SECONDS)
                    return True

                log(
                    "[NAVIGATION] Auto navigating text lost but "
                    "movement continues"
                )
                misses = 0

        wait(_AUTO_NAV_POLL_SECONDS)


def wait_until_arrives_at_coord(
    device_id,
    location,
    map_def,
    timeout=120,
    poll_interval=0.5,
):
    if not location_has_coordinates(location):
        log("[NAVIGATION] Location has no target coordinates")
        return False

    target = (int(location["coord_x"]), int(location["coord_y"]))
    arrival_radius = int(location.get("arrival_radius", DEFAULT_ARRIVAL_RADIUS))
    log(
        f"[NAVIGATION] Waiting for coordinates target={target} "
        f"radius={arrival_radius}"
    )

    start = time.time()
    while time.time() - start < timeout:
        current = read_current_coordinates(device_id, map_def=map_def)
        if current is None:
            log("[NAVIGATION] Coordinate read failed; retrying")
            wait(poll_interval)
            continue

        dist = distance_coords(current, target)
        log(
            f"[NAVIGATION] Current=({current[0]},{current[1]}) "
            f"distance={dist}"
        )

        if dist <= arrival_radius:
            log("[NAVIGATION] Arrived to target coordinates")
            return True

        wait(poll_interval)

    log("[NAVIGATION] Coordinate arrival timeout")
    return False


def _is_map_window_open():
    screen = get_screen()
    return (
        find_template(
            screen,
            MAP_WINDOW_OPEN_TEMPLATE,
            threshold=_MAP_WINDOW_THRESHOLD,
        )
        is not None
    )


def wait_until_map_window_open(timeout=5, poll_interval=0.3):
    start = time.time()
    while time.time() - start < timeout:
        if _is_map_window_open():
            return True
        wait(poll_interval)
    return False


def wait_until_map_window_closed(timeout=5, poll_interval=0.3):
    start = time.time()
    while time.time() - start < timeout:
        if not _is_map_window_open():
            return True
        wait(poll_interval)
    return False


def _save_map_open_debug_screenshot(attempt):
    import cv2

    from core.path_utils import get_app_root

    debug_dir = get_app_root() / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    screen = get_screen()
    if screen is not None:
        cv2.imwrite(
            str(debug_dir / f"map_open_failed_attempt_{attempt}.png"),
            screen,
        )


def _close_x_template_path():
    path = Path(resource_path(CLOSE_X_TEMPLATE))
    return path if path.is_file() else None


def _tap_close_window(*, allow_fallback=True):
    template_path = _close_x_template_path()
    if template_path:
        screen = get_screen()
        close_match = find_template(
            screen,
            str(template_path),
            threshold=_MAP_WINDOW_THRESHOLD,
        )
        if close_match:
            log("[UI] Closing window using close template")
            tap(close_match["center_x"], close_match["center_y"])
            return True

    if not allow_fallback:
        return False

    log("[UI] Close template not found, using fallback coordinates")
    tap(CLOSE_BUTTON["x"], CLOSE_BUTTON["y"])
    return True


def _try_dismiss_visible_popup():
    if not _close_x_template_path():
        return

    screen = get_screen()
    close_match = find_template(
        screen,
        str(_close_x_template_path()),
        threshold=_MAP_WINDOW_THRESHOLD,
    )
    if not close_match:
        return

    tap(close_match["center_x"], close_match["center_y"])
    wait(0.5)
    log("[MAP] Dismissed popup before opening map")


def open_map_window(device_id=None, retries=3, timeout=5, *, post_teleport_settle=False):
    if device_id:
        bind_adb_device(device_id)

    if post_teleport_settle:
        wait(_POST_TELEPORT_MAP_SETTLE_SECONDS)

    _try_dismiss_visible_popup()

    for attempt in range(1, retries + 1):
        tap(MAP_BUTTON["x"], MAP_BUTTON["y"])
        if wait_until_map_window_open(timeout=timeout):
            log("[MAP] Map window open")
            return True

        log(f"[MAP] Map window open attempt {attempt} failed")
        _save_map_open_debug_screenshot(attempt)
        if attempt < retries:
            wait(1)

    log("[MAP] Map window open failed after retries")
    return False


def close_map_window():
    if not _tap_close_window():
        log("[MAP] Close X button not found")
        return False

    if wait_until_map_window_closed():
        log("[MAP] Map window closed")
        return True

    log("[MAP] Map window close timeout")
    return False


def wait_until_map_loaded(map_def, device_id=None, timeout=None, poll_interval=0.5):
    navigation = map_def.get("navigation", {})
    enter_wait = navigation.get("enter_wait", 8)
    if timeout is None:
        timeout = enter_wait if enter_wait else 10

    detection = navigation.get("current_map_detection")
    has_template = bool(navigation.get("current_map_template"))
    has_ocr = (
        isinstance(detection, dict)
        and detection.get("method") == "ocr"
        and detection.get("region")
        and detection.get("expected_text")
    )

    if not has_template and not has_ocr:
        wait(timeout)
        return True

    start = time.time()
    while time.time() - start < timeout:
        if is_current_map(device_id, map_def):
            log("[NAVIGATION] Map loaded confirmed")
            return True
        wait(poll_interval)

    log("[NAVIGATION] Map load timeout; continuing")
    return False


def _filter_post_spot_actions(actions):
    filtered = []
    for action in actions:
        action_type = action.get("type")
        if action_type in ("wait", "ensure_auto_mode"):
            continue
        filtered.append(action)
    return filtered


def _navigation_behavior(navigation):
    behavior = navigation.get("behavior", "modal_enter")
    return str(behavior).strip() if behavior else "modal_enter"


def _enter_map_modal_enter(map_def, navigation, log_prefix, device_id=None):
    head = find_template_with_scroll(
        navigation["map_head_template"],
        threshold=0.8,
        swipe_coords=navigation.get("map_list_swipe"),
    )

    if not head:
        log(f"{log_prefix} Map head not found")
        return False

    tap(head["center_x"], head["center_y"])
    wait(2)

    map_option = find_template_with_scroll(
        navigation["map_option_template"],
        threshold=0.8,
        swipe_coords=navigation.get("map_list_swipe"),
    )

    if not map_option:
        log(f"{log_prefix} Map option not found")
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
        log(f"{log_prefix} Map option not checked")
        return False

    log(f"{log_prefix} Map option checked")

    screen = get_screen()

    enter = find_template(
        screen,
        navigation["enter_template"],
        threshold=0.8,
    )

    if not enter:
        log(f"{log_prefix} Enter button not found")
        return False

    tap(enter["center_x"], enter["center_y"])

    log(f"{log_prefix} Entering map")

    wait_until_map_loaded(map_def, device_id=device_id)
    return True


def _enter_map_direct_teleport(map_def, navigation, log_prefix, device_id=None):
    head_template = navigation.get("map_head_template")
    if head_template:
        head = find_template_with_scroll(
            head_template,
            threshold=0.8,
            swipe_coords=navigation.get("map_list_swipe"),
        )

        if not head:
            log(f"{log_prefix} Map head not found")
            return False

        tap(head["center_x"], head["center_y"])
        wait(2)
        log(f"{log_prefix} Map head selected")

    map_option = find_template_with_scroll(
        navigation["map_option_template"],
        threshold=0.8,
        swipe_coords=navigation.get("map_list_swipe"),
    )

    if not map_option:
        log(f"{log_prefix} Map option not found")
        return False

    tap(map_option["center_x"], map_option["center_y"])
    log(f"{log_prefix} Direct teleport selected")

    wait_until_map_loaded(map_def, device_id=device_id)
    return True


def _enter_map_by_behavior(map_def, log_prefix="[NAVIGATION]", device_id=None):
    navigation = map_def["navigation"]
    behavior = _navigation_behavior(navigation)

    if not is_navigation_supported(map_def):
        log_unsupported_navigation_behavior(map_def)
        return False

    if not is_navigation_implemented(map_def):
        map_id = map_def.get("id", "?")
        log(
            f"{log_prefix} Navigation behavior {behavior!r} not implemented "
            f"for map {map_id}"
        )
        return False

    if behavior == "direct_teleport":
        return _enter_map_direct_teleport(
            map_def, navigation, log_prefix, device_id=device_id
        )

    if behavior == "modal_enter":
        return _enter_map_modal_enter(
            map_def, navigation, log_prefix, device_id=device_id
        )

    log(
        f"{log_prefix} Navigation behavior {behavior!r} not in "
        f"{sorted(IMPLEMENTED_NAVIGATION_BEHAVIORS)}"
    )
    return False


def navigate_to_map_and_wire(map_id, wire_id, device_id, log_prefix="[NAVIGATION]"):
    bind_adb_device(device_id)

    if map_id == "divine_realm_1":
        log("[MAP] Entering divine_realm_1")

    map_def = load_map_definition(map_id)
    navigation = map_def.get("navigation")
    if not navigation:
        log(f"{log_prefix} Map {map_id} has no navigation config")
        return False, map_def

    if map_id == "divine_realm_1":
        log("[MAP] divine_realm_1 navigation ready")

    wire_id = _normalize_wire_id(wire_id)

    behavior = navigation_behavior(map_def) or _navigation_behavior(navigation)
    log(
        f"{log_prefix} Going to: {map_def['name']} | "
        f"wire {wire_id} | behavior {behavior}"
    )

    log(f"{log_prefix} Cleaning UI before navigation")
    clean_game_ui(device_id)

    if not open_map_window(device_id):
        return False, map_def

    if not _enter_map_by_behavior(map_def, log_prefix, device_id=device_id):
        return False, map_def

    if not switch_to_wire(map_def, wire_id):
        return False, map_def

    return True, map_def


def tap_visual_location(
    x,
    y,
    device_id,
    log_prefix="[NAVIGATION]",
    label="location",
    location=None,
    map_def=None,
):
    bind_adb_device(device_id)

    if not open_map_window(
        device_id,
        retries=3,
        timeout=5,
        post_teleport_settle=True,
    ):
        log("[NAVIGATION] Failed to open map window")
        return False

    log(f"{log_prefix} Clicking {label} at {x},{y}")
    tap(x, y)

    if not close_map_window():
        log(f"{log_prefix} Failed to close map window")
        return False

    if location_has_coordinates(location):
        if map_def is None and location.get("map"):
            try:
                map_def = load_map_definition(location["map"])
            except FileNotFoundError:
                map_def = None

        if not wait_until_arrives_at_coord(device_id, location, map_def):
            log(f"{log_prefix} Navigation to {label} did not complete")
            return False
    elif not wait_until_navigation_complete(device_id):
        log(f"{log_prefix} Navigation to {label} did not complete")
        return False

    return True


def _resolve_farm_destination(active_farm_spot, spot_id, map_def):
    if active_farm_spot:
        log(
            f"[NAVIGATION] Visual farm spot found: "
            f"{active_farm_spot.get('id')} "
            f"({active_farm_spot['x']},{active_farm_spot['y']})"
        )
        legacy_spot = map_def.get("spots", {}).get(spot_id) if spot_id else None
        return {
            "x": active_farm_spot["x"],
            "y": active_farm_spot["y"],
            "source": "visual",
            "legacy_spot": legacy_spot,
        }

    log("[NAVIGATION] Visual farm spot not found; using legacy destination")

    if not spot_id:
        return None

    legacy_spot = map_def.get("spots", {}).get(spot_id)
    if not legacy_spot or not legacy_spot.get("spot_click"):
        return None

    spot_click = legacy_spot["spot_click"]
    return {
        "x": spot_click["x"],
        "y": spot_click["y"],
        "source": "legacy",
        "legacy_spot": legacy_spot,
    }


def go_to_active_farm_spot(device_id):
    bind_adb_device(device_id)

    profile = load_profile()
    profile_name = get_current_profile_name()
    spot_id = profile.get("spot")

    active_farm_spot = None
    if profile_name:
        active_farm_spot = get_farm_spot_location(profile_name)
    else:
        log(
            "[NAVIGATION] Current profile name unavailable; "
            "using profile map/wire and legacy farm spot"
        )

    expected_map_id, expected_source = resolve_expected_farm_map_id(profile, profile_name)
    profile_map_id = profile.get("map")
    active_farm_map = active_farm_spot.get("map") if active_farm_spot else None

    log(f"[NAVIGATION] active farm map = {active_farm_map or 'none'}")
    log(f"[NAVIGATION] validation map = {expected_map_id}")
    if profile_map_id and expected_map_id and profile_map_id != expected_map_id:
        log(
            "[MAP_CHECK] WARNING: profile.map "
            f"({profile_map_id}) != expected farm map ({expected_map_id}) "
            f"source={expected_source}"
        )

    if active_farm_spot:
        map_id = active_farm_spot["map"]
        wire_id = _normalize_wire_id(active_farm_spot["wire"])
        log(
            f"[NAVIGATION] Using active farm location config: "
            f"{map_id} wire {wire_id}"
        )
    else:
        map_id = profile["map"]
        wire_id = _normalize_wire_id(profile["wire"])
        log(
            f"[NAVIGATION] Using profile map/wire config: "
            f"{map_id} wire {wire_id}"
        )

    nav_ok, map_def = navigate_to_map_and_wire(
        map_id, wire_id, device_id, log_prefix="[NAVIGATION]"
    )
    if not nav_ok:
        return False

    farm_dest = _resolve_farm_destination(active_farm_spot, spot_id, map_def)
    if not farm_dest:
        log("[NAVIGATION] No visual or legacy farm spot configured")
        return False

    if farm_dest["source"] == "visual":
        log(
            f"[NAVIGATION] Using visual farm spot: "
            f"{farm_dest['x']},{farm_dest['y']}"
        )
    else:
        log(f"[NAVIGATION] Using legacy spot: {spot_id}")

    visual_location = (
        active_farm_spot if farm_dest["source"] == "visual" else None
    )
    if not tap_visual_location(
        farm_dest["x"],
        farm_dest["y"],
        device_id,
        label="farm spot",
        location=visual_location,
        map_def=map_def,
    ):
        log("[NAVIGATION] Failed to reach visual farm spot")
        return False

    legacy_spot = farm_dest.get("legacy_spot")
    post_spot_actions = _filter_post_spot_actions(
        legacy_spot.get("post_spot_actions", []) if legacy_spot else []
    )

    if post_spot_actions:
        run_sequence(post_spot_actions)

    ensure_auto_mode()

    log("[NAVIGATION] Arrived to farm spot")

    return True
