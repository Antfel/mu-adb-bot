from core.logger import log
from core.profile import get_current_profile_name
from core.special_locations import get_elf_buff_location
from core.actions import wait
from core.adb import bind_adb_device
from states.navigation_state import (
    go_to_active_farm_spot,
    navigate_to_map_and_wire,
    tap_visual_location,
)


def go_to_elf_buff(device_id):
    bind_adb_device(device_id)

    profile_name = get_current_profile_name()
    if not profile_name:
        log("[ELF] Current profile name unavailable")
        return False

    elf_location = get_elf_buff_location(profile_name)
    if not elf_location:
        log("[ELF] No elf buff location configured")
        return False

    map_id = elf_location["map"]
    wire_id = int(elf_location["wire"])
    x = elf_location["x"]
    y = elf_location["y"]

    log(
        f"[ELF] Going to elf buff: {map_id} wire {wire_id} "
        f"({x},{y})"
    )

    nav_ok, map_def = navigate_to_map_and_wire(
        map_id, wire_id, device_id, log_prefix="[ELF]"
    )
    if not nav_ok:
        log("[ELF] Failed to navigate to elf buff map/wire")
        return False

    if not tap_visual_location(
        x,
        y,
        device_id,
        log_prefix="[ELF]",
        label="elf buff",
        location=elf_location,
        map_def=map_def,
    ):
        log("[ELF] Failed to reach elf buff location")
        return False

    wait(5)
    log("[ELF] Elf buff route completed")
    return True


def go_to_elf_buff_and_return(device_id):
    bind_adb_device(device_id)

    if not go_to_elf_buff(device_id):
        log("[ELF] Elf buff route failed; skipping return to farm spot")
        return False

    if not go_to_active_farm_spot(device_id):
        log("[ELF] Return to farm spot failed after elf buff")
        return False

    log("[ELF] Elf buff and return to farm spot completed")
    return True
