import core.session_state as session_state
from core.logger import log
from states.elf_buff_check_state import has_elf_buff
from states.elf_buff_state import go_to_elf_buff_and_return
from states.map_state import is_in_configured_map
from states.potion_state import is_any_potion_empty
from states.purchase_potions_state import handle_empty_potions


def run_pre_navigation_checks(device_id):
    """
    Potion recovery and elf buff before farm navigation.
    Returns (success, already_at_farm_spot).
    already_at_farm_spot is True when potion/elf flow already returned to the farm spot.
    """
    navigated_to_farm = False

    if is_any_potion_empty():
        log("[PRE] Pociones agotadas; validando compra")
        if not handle_empty_potions(device_id):
            log("[PRE] Compra de pociones falló")
            return False, False
        if is_in_configured_map():
            navigated_to_farm = True
            log("[PRE] En mapa de farm tras compra de pociones")

    if session_state.session_elf_buff_enabled and not has_elf_buff():
        log("[PRE] Elf buff no activo; buscando buff")
        if not go_to_elf_buff_and_return(device_id):
            log("[PRE] Falló búsqueda de elf buff")
            return False, navigated_to_farm
        navigated_to_farm = True
        log("[PRE] Elf buff completado; ya en farm spot")

    return True, navigated_to_farm
