from core.logger import log
from core.game_actions import revive_if_dead
from states.navigation_state import go_to_active_farm_spot


def recover_if_dead(device_id):
    log("[RECOVERY] Validando si está vivo")

    revived = revive_if_dead()

    if not revived:
        log("[RECOVERY] No se pudo revivir")
        return False

    log("[RECOVERY] Vivo. Regresando al spot")

    return go_to_active_farm_spot(device_id)