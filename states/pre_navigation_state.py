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
    log("[PRE] Starting pre_navigation_checks")
    navigated_to_farm = False

    log("[PRE] death check handled outside pre_navigation_checks (startup/recovery)")

    potions_empty = is_any_potion_empty()
    log(f"[PRE] potion check result={potions_empty}")
    if potions_empty:
        log("[PRE] decision=handle empty potions")
        log("[PRE] Pociones agotadas; validando compra")
        if not handle_empty_potions(device_id):
            log("[PRE] Compra de pociones falló")
            log("[PRE] Finished pre_navigation_checks success=False navigated_to_farm=False")
            return False, False
        on_farm_after_potions = is_in_configured_map()
        log(f"[PRE] on farm after potions={on_farm_after_potions}")
        if on_farm_after_potions:
            navigated_to_farm = True
            log("[PRE] En mapa de farm tras compra de pociones")

    elf_enabled = session_state.session_elf_buff_enabled
    if elf_enabled:
        has_buff = has_elf_buff()
        log(f"[PRE] elf buff check enabled={elf_enabled} has_buff={has_buff}")
    else:
        has_buff = True
        log(f"[PRE] elf buff check enabled={elf_enabled} has_buff=skipped")
    if elf_enabled and not has_buff:
        log("[PRE] decision=search elf buff")
        log("[PRE] Elf buff no activo; buscando buff")
        if not go_to_elf_buff_and_return(device_id):
            log("[PRE] Falló búsqueda de elf buff")
            log(
                f"[PRE] Finished pre_navigation_checks success=False "
                f"navigated_to_farm={navigated_to_farm}"
            )
            return False, navigated_to_farm
        navigated_to_farm = True
        log("[PRE] Elf buff completado; ya en farm spot")

    log(
        f"[PRE] Finished pre_navigation_checks success=True "
        f"navigated_to_farm={navigated_to_farm}"
    )
    log("[PRE] decision=continue startup/navigation")
    return True, navigated_to_farm
