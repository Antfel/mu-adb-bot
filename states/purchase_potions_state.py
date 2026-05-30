from core.adb import bind_adb_device
from core.game_actions import (
    buy_potions,
    ensure_auto_mode,
    tap_empty_potion_slot,
    accept_potion_teleport_popup,
    wait_for_potion_entry_result,
    wait_for_shop_open,
)
from core.logger import log
from core.actions import wait
from core.adb import tap
from core.profile import load_profile
from core.session_state import get_current_bot_state, set_current_bot_state
from states.navigation_state import go_to_active_farm_spot
from states.potion_state import is_hp_potion_empty, is_mana_potion_empty


def _restore_bot_state(previous_state):
    if previous_state in ("FARMING", "NAVIGATING", "STARTING", "BUYING_POTIONS"):
        set_current_bot_state(previous_state)
    else:
        set_current_bot_state("ERROR")


def _close_shop():
    tap(2520, 45)
    wait(1)


def handle_empty_potions(device_id):
    bind_adb_device(device_id)

    profile = load_profile()
    hp_stacks = profile["hp_potion_stacks"]
    mp_stacks = profile["mp_potion_stacks"]

    previous_state = get_current_bot_state()
    set_current_bot_state("BUYING_POTIONS")

    log("[POTION] Iniciando recuperación de pociones")

    hp_empty = is_hp_potion_empty()
    mp_empty = is_mana_potion_empty()

    if not hp_empty and not mp_empty:
        log("[POTION] No hay pociones agotadas")
        _restore_bot_state(previous_state)
        return False

    if not tap_empty_potion_slot():
        log("[POTION] Potion purchase failed")
        _restore_bot_state(previous_state)
        return False

    wait(1)
    entry = wait_for_potion_entry_result(device_id)

    if entry is None:
        log("[POTION] Potion purchase failed")
        _restore_bot_state(previous_state)
        return False

    if entry == "teleport_popup":
        if not accept_potion_teleport_popup():
            log("[POTION] Potion purchase failed")
            _restore_bot_state(previous_state)
            return False

        if not wait_for_shop_open(timeout=10):
            log("[POTION] Shop did not open after teleport")
            log("[POTION] Potion purchase failed")
            _restore_bot_state(previous_state)
            return False

    elif entry != "shop_open":
        log("[POTION] Potion purchase failed")
        _restore_bot_state(previous_state)
        return False

    buy_potions(
        hp_amount=hp_stacks if hp_empty else 0,
        mp_amount=mp_stacks if mp_empty else 0,
    )

    log("[POTION] Compra terminada. Cerrando tienda")
    _close_shop()

    if entry == "teleport_popup":
        log("[POTION] Teleport purchase completed; navigating back to farm spot")
        if not go_to_active_farm_spot(device_id):
            log("[POTION] Potion purchase failed")
            _restore_bot_state(previous_state)
            return False

        if not ensure_auto_mode():
            log("[POTION] Potion purchase failed")
            _restore_bot_state(previous_state)
            return False
    elif entry == "shop_open":
        log("[POTION] Direct shop purchase completed; staying at current spot")
        if not ensure_auto_mode():
            log("[POTION] Potion purchase failed")
            _restore_bot_state(previous_state)
            return False
    else:
        log("[POTION] Potion purchase failed")
        _restore_bot_state(previous_state)
        return False

    set_current_bot_state("FARMING")
    return True
