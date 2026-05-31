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
from core.game_actions import clean_game_ui, ensure_auto_mode
from core.special_locations import get_farm_spot_location
from coordinates.ui import CLOSE_X_TEMPLATE, MAP_WINDOW_OPEN_TEMPLATE


MAP_BUTTON = {"x": 2440, "y": 120}
_MAP_WINDOW_THRESHOLD = 0.8

_WIRE_THRESHOLD = 0.8
AUTO_NAVIGATING_TEMPLATE = "templates/ui/common/auto_navigating.png"
_AUTO_NAV_THRESHOLD = 0.70
_AUTO_NAV_TIMEOUT = 180
_AUTO_NAV_POLL_SECONDS = 1
_AUTO_NAV_INITIAL_WAIT = 2
_AUTO_NAV_FINISH_GRACE_SECONDS = 1.5
_AUTO_NAV_MISSES_TO_FINISH = 3
_AUTO_NAV_START_ATTEMPTS = 4


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


def _get_wire_switch_config(map_def):
    wire_config = map_def.get("wire_switch")
    if isinstance(wire_config, dict):
        return wire_config
    legacy = map_def.get("wire")
    if isinstance(legacy, dict):
        return legacy
    return None


def switch_to_wire(map_def, wire_id):
    wire_config = _get_wire_switch_config(map_def)
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


def wait_until_navigation_complete():
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
                log("[NAVIGATION] Auto navigating finished")
                wait(_AUTO_NAV_FINISH_GRACE_SECONDS)
                return True

        wait(_AUTO_NAV_POLL_SECONDS)


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


def open_map_window():
    tap(MAP_BUTTON["x"], MAP_BUTTON["y"])
    if wait_until_map_window_open():
        log("[MAP] Map window open")
        return True
    log("[MAP] Map window open timeout")
    return False


def close_map_window():
    if not Path(CLOSE_X_TEMPLATE).is_file():
        log(f"[MAP] Close X template missing: {CLOSE_X_TEMPLATE}")
        return False

    screen = get_screen()
    close_match = find_template(
        screen,
        CLOSE_X_TEMPLATE,
        threshold=_MAP_WINDOW_THRESHOLD,
    )
    if not close_match:
        log("[MAP] Close X button not found")
        return False

    tap(close_match["center_x"], close_match["center_y"])

    if wait_until_map_window_closed():
        log("[MAP] Map window closed")
        return True

    log("[MAP] Map window close timeout")
    return False


def wait_until_map_loaded(map_def, timeout=None, poll_interval=0.5):
    navigation = map_def.get("navigation", {})
    current_template = navigation.get("current_map_template")
    enter_wait = navigation.get("enter_wait", 8)
    if timeout is None:
        timeout = enter_wait if enter_wait else 10

    if not current_template:
        wait(timeout)
        return True

    start = time.time()
    while time.time() - start < timeout:
        screen = get_screen()
        if find_template(
            screen,
            current_template,
            threshold=0.8,
        ):
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


def _enter_map_modal_enter(map_def, navigation, log_prefix):
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

    wait_until_map_loaded(map_def)
    return True


def _enter_map_direct_teleport(map_def, navigation, log_prefix):
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

    wait_until_map_loaded(map_def)
    return True


def _enter_map_by_behavior(map_def, log_prefix="[NAVIGATION]"):
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
        return _enter_map_direct_teleport(map_def, navigation, log_prefix)

    if behavior == "modal_enter":
        return _enter_map_modal_enter(map_def, navigation, log_prefix)

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

    if not open_map_window():
        return False, map_def

    if not _enter_map_by_behavior(map_def, log_prefix):
        return False, map_def

    if not switch_to_wire(map_def, wire_id):
        return False, map_def

    return True, map_def


def tap_visual_location(x, y, device_id, log_prefix="[NAVIGATION]", label="location"):
    bind_adb_device(device_id)

    if not open_map_window():
        log(f"{log_prefix} Failed to open map window")
        return

    log(f"{log_prefix} Clicking {label} at {x},{y}")
    tap(x, y)

    if not close_map_window():
        log(f"{log_prefix} Failed to close map window")

    wait_until_navigation_complete()


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

    tap_visual_location(
        farm_dest["x"],
        farm_dest["y"],
        device_id,
        label="farm spot",
    )

    legacy_spot = farm_dest.get("legacy_spot")
    post_spot_actions = _filter_post_spot_actions(
        legacy_spot.get("post_spot_actions", []) if legacy_spot else []
    )

    if post_spot_actions:
        run_sequence(post_spot_actions)

    ensure_auto_mode()

    log("[NAVIGATION] Arrived to farm spot")

    return True
