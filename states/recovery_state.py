from core.logger import log
from core.game_actions import revive_if_dead as revive_character


def recover_if_dead(device_id):
    """Revive only; navigation is handled by the main loop after pre-navigation checks."""
    log("[RECOVERY] Validando si está vivo")

    revived = revive_character()

    if not revived:
        log("[RECOVERY] No se pudo revivir")
        return False

    log("[RECOVERY] Personaje revivido")
    return True