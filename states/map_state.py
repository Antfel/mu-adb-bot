from core.logger import log
from core.screen import get_screen
from core.vision import find_template
from core.profile import load_profile
from core.navigation_config import load_all_map_definitions


def get_current_map():
    """
    Recorre MAPS y devuelve el map_id cuyo navigation.current_map_template
    esté presente en pantalla. Si ninguno coincide, devuelve None.
    """
    screen = get_screen()

    map_definitions = load_all_map_definitions()

    for map_id, map_data in map_definitions.items():
        navigation = map_data.get("navigation", {})
        current_template = navigation.get("current_map_template")

        if not current_template:
            continue

        match = find_template(
            screen,
            current_template,
            threshold=0.8,
        )

        if match:
            log(f"[MAP] Detected current map: {map_id}")
            return map_id

    log("[MAP] No configured current_map_template matched")
    return None


def is_in_configured_map():
    """
    Compara el mapa actual detectado con el configurado en el perfil.
    Si no se puede detectar mapa actual, devuelve False (forzar navegación).
    """
    profile = load_profile()
    configured_map = profile.get("map")

    if not configured_map:
        log("[MAP] No configured map in profile")
        return False

    current_map = get_current_map()

    if current_map is None:
        log("[MAP] Unable to detect current map")
        return False

    if current_map != configured_map:
        log(f"[MAP] Current map {current_map} != configured {configured_map}")
        return False

    log(f"[MAP] Current map matches configured: {configured_map}")
    return True

