from core.logger import log
from core.adb import tap
from core.actions import wait, run_sequence
from core.screen import get_screen
from core.vision import find_template
from core.ui import find_template_with_scroll
from core.profile import load_profile
from coordinates.spots import resolve_farm_target


MAP_BUTTON = {"x": 2440, "y": 120}


def switch_to_wire(map_data, wire_id):
    log(f"[NAVIGATION] Wire switch placeholder - requested wire: {wire_id}")
    return True


def go_to_active_farm_spot():
    profile = load_profile()
    map_data, wire_data, spot = resolve_farm_target(profile)
    navigation = map_data["navigation"]

    log(
        f"[NAVIGATION] Going to: {map_data['name']} | "
        f"{wire_data.get('name', profile['wire'])} | {spot['name']}"
    )

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

    if not switch_to_wire(map_data, profile["wire"]):
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
