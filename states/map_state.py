from core.adb import bind_adb_device
from core.current_map_detection import (
    _resolve_detection_method,
    is_current_map,
    probe_current_map_match,
)
from core.logger import log
from core.screen import get_screen
from core.profile import get_current_profile_name, load_profile
from core.navigation_config import load_all_map_definitions, load_map_definition
from core.special_locations import get_farm_spot_location

DEBUG_PROFILE_MAP_MISMATCH = False


def resolve_expected_farm_map_id(profile=None, profile_name=None):
    """
    Single source of truth for the farm target map.
    Matches go_to_active_farm_spot(): active farm location first, then profile.map.
    Returns (map_id, source).
    """
    if profile is None:
        profile = load_profile()
    if profile_name is None:
        profile_name = get_current_profile_name()

    active_farm_spot = get_farm_spot_location(profile_name) if profile_name else None
    if active_farm_spot and active_farm_spot.get("map"):
        return active_farm_spot["map"], "active_farm_location"

    profile_map = profile.get("map")
    if profile_map:
        return profile_map, "profile.map"

    return None, "none"


def is_expected_map_loaded(device_id, expected_map_id):
    """
    Valida solo el mapa esperado (template/OCR de ese map_def).
    No usa detección global ni compite con mapas de templates parecidos.
    """
    if not expected_map_id:
        return False

    try:
        map_def = load_map_definition(expected_map_id)
    except FileNotFoundError:
        log(f"[MAP] Expected map definition not found: {expected_map_id}")
        return False

    navigation = map_def.get("navigation", {})
    if not navigation:
        log(f"[MAP] Expected map {expected_map_id} has no navigation config")
        return False

    has_template = bool(navigation.get("current_map_template"))
    detection = navigation.get("current_map_detection")
    has_ocr = (
        isinstance(detection, dict)
        and detection.get("method") == "ocr"
        and detection.get("region")
        and detection.get("expected_text")
    )
    if not has_template and not has_ocr:
        log(f"[MAP] Expected map {expected_map_id} has no current map detection")
        return False

    if device_id:
        bind_adb_device(device_id)

    method = _resolve_detection_method(navigation)
    if method == "template" and has_template:
        template_path = navigation.get("current_map_template")
        log(f"[MAP] current_map_template={template_path}")

        screen = get_screen()
        if screen is None:
            log("[MAP] Final result=False (screen unavailable)")
            return False

        matched, confidence, resolved_threshold = probe_current_map_match(screen, navigation)
        log(f"[MAP] threshold={resolved_threshold}")
        log(
            f"[MAP_CHECK] expected={expected_map_id} "
            f"confidence={confidence:.3f} threshold={resolved_threshold}"
        )
        log(f"[MAP] Final result={matched}")
        return matched

    result = is_current_map(device_id, map_def)
    log(f"[MAP] Final result={result}")
    return result


def detect_current_map(device_id=None, *, log_match=True):
    """
    Detección global: primer mapa cuyo template/OCR coincida.
    Solo para diagnóstico o uso general; no usar para validar farm spot.
    """
    return get_current_map(device_id=device_id, log_match=log_match)


def get_current_map(device_id=None, *, log_match=True):
    """
    Recorre MAPS y devuelve el map_id cuyo método de detección configurado
    coincida en pantalla. Si ninguno coincide, devuelve None.
    """
    screen = get_screen()
    if screen is None:
        log("[MAP] Unable to capture screen for current map detection")
        return None

    map_definitions = load_all_map_definitions()

    for map_id, map_data in map_definitions.items():
        navigation = map_data.get("navigation", {})
        if not navigation:
            continue

        has_template = bool(navigation.get("current_map_template"))
        detection = navigation.get("current_map_detection")
        has_ocr = (
            isinstance(detection, dict)
            and detection.get("method") == "ocr"
            and detection.get("region")
            and detection.get("expected_text")
        )
        if not has_template and not has_ocr:
            continue

        if is_current_map(device_id, map_data, screen=screen):
            if log_match:
                log(f"[MAP] Detected current map: {map_id}")
            return map_id

    if log_match:
        log("[MAP] No configured current map detection matched")
    return None


def is_in_configured_map(device_id=None):
    """
    Confirma si el personaje está en el mapa objetivo de farm.
    Usa solo is_expected_map_loaded(); la detección global es diagnóstico.
    """
    profile = load_profile()
    profile_name = get_current_profile_name()
    expected_map_id, source = resolve_expected_farm_map_id(profile, profile_name)
    profile_map_id = profile.get("map")

    log(f"[MAP_CHECK] expected_map_id={expected_map_id}")
    log(f"[MAP_CHECK] source={source}")

    if (
        DEBUG_PROFILE_MAP_MISMATCH
        and profile_map_id
        and expected_map_id
        and profile_map_id != expected_map_id
    ):
        log(
            "[MAP_CHECK] WARNING: profile.map "
            f"({profile_map_id}) != expected farm map ({expected_map_id})"
        )

    if not expected_map_id:
        log("[MAP] No expected farm map configured")
        return False

    if is_expected_map_loaded(device_id, expected_map_id):
        log(f"[MAP] Expected map confirmed: {expected_map_id}")
        log("[MAP] Final is_in_configured_map=True")
        return True

    detected = detect_current_map(device_id, log_match=False)
    log(f"[MAP] Current map {detected} != configured {expected_map_id}")
    log("[MAP] Final is_in_configured_map=False")
    return False
