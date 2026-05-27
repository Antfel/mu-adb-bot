from core.logger import log
from core.game_actions import ensure_inventory_closed, ensure_auto_mode
from core.actions import wait
from states.death_state import is_dead


def run_farming_state():
    log("[STATE] FARMING")

    if is_dead():
        log("[FARMING] Personaje muerto. Pendiente lógica de revive")
        return False
    
    ui_ok = ensure_inventory_closed()
    if not ui_ok:
        log("[FARMING] No se pudo cerrar/validar inventario")
        return False

    auto_ok = ensure_auto_mode()
    if not auto_ok:
        log("[FARMING] No se pudo activar/validar auto")
        return False

    log("[FARMING] Personaje farmeando correctamente")

    wait(3)

    return True