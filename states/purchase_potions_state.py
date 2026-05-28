from core.logger import log
from core.actions import wait
from core.adb import tap
from core.game_actions import teleport_to_potion_store, buy_potions
from states.navigation_state import go_to_active_farm_spot
from core.profile import load_profile
from states.potion_state import is_hp_potion_empty, is_mana_potion_empty


def handle_empty_potions(device_id):

    profile = load_profile()

    hp_stacks = profile["hp_potion_stacks"]
    mp_stacks = profile["mp_potion_stacks"]
    
    log("[POTION] Iniciando recuperación de pociones")

    # detectar ANTES de ir a tienda
    hp_empty = is_hp_potion_empty()
    mp_empty = is_mana_potion_empty()

    if not hp_empty and not mp_empty:
        log("[POTION] No hay pociones agotadas")
        return False

    if not teleport_to_potion_store():
        log("[POTION] No se pudo llegar a tienda")
        return False

    buy_potions(
        hp_amount=hp_stacks if hp_empty else 0,
        mp_amount=mp_stacks if mp_empty else 0
    )

    log("[POTION] Compra terminada. Cerrando tienda")

    tap(2520, 45)
    wait(1)

    log("[POTION] Tienda Cerrada. Volviendo al spot")

    return go_to_active_farm_spot(device_id)