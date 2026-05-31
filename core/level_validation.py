from dataclasses import dataclass

from core.logger import log
from core.navigation_config import load_map_definition
from core.profile import get_bot_mode, load_profile, normalize_profile_data
from core.special_locations import get_elf_buff_location, get_farm_spot_location


@dataclass
class LevelValidationResult:
    can_start: bool
    farm_blocked_message: str | None = None
    elf_buff_enabled: bool = False
    elf_buff_status: str = "No configurado"
    show_elf_warning: bool = False


def _elf_buff_enabled_in_profile(profile_data):
    general_config = profile_data.get("general_config")
    if isinstance(general_config, dict):
        return bool(general_config.get("enable_elf_buff", True))
    return True


def get_map_min_level(map_id):
    map_def = load_map_definition(map_id)
    return int(map_def.get("requirements", {}).get("min_level", 0))


def get_map_display_name(map_id):
    map_def = load_map_definition(map_id)
    return map_def.get("name", map_id)


def parse_character_level(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    text = str(value).strip()
    if not text:
        return None

    try:
        level = int(text)
    except (TypeError, ValueError):
        return None

    return level if level > 0 else None


def _validate_elf_buff_level(character_level, elf_buff, *, profile_elf_buff_enabled=True):
    if not profile_elf_buff_enabled:
        return LevelValidationResult(
            can_start=True,
            elf_buff_enabled=False,
            elf_buff_status="Desactivado",
        )

    if not elf_buff:
        return LevelValidationResult(
            can_start=True,
            elf_buff_enabled=False,
            elf_buff_status="No configurado",
        )

    elf_map_id = elf_buff.get("map")
    elf_min_level = get_map_min_level(elf_map_id)

    if character_level < elf_min_level:
        log("[LEVEL] Elf buff disabled by level requirement")
        return LevelValidationResult(
            can_start=True,
            elf_buff_enabled=False,
            elf_buff_status="Desactivado por nivel",
            show_elf_warning=True,
        )

    return LevelValidationResult(
        can_start=True,
        elf_buff_enabled=True,
        elf_buff_status="Activo",
    )


def _validate_kill_bosses_maps(profile_data, character_level, profile_name):
    kill_bosses_config = profile_data.get("kill_bosses_config", {})
    map_ids = kill_bosses_config.get("maps") or []
    if not isinstance(map_ids, list) or not map_ids:
        return LevelValidationResult(
            can_start=False,
            farm_blocked_message=(
                "Seleccione al menos un mapa en la configuración de Kill Bosses."
            ),
        )

    blocked_maps = []
    for map_id in map_ids:
        min_level = get_map_min_level(map_id)
        if character_level < min_level:
            blocked_maps.append(
                f"{get_map_display_name(map_id)} (nivel requerido: {min_level})"
            )

    if blocked_maps:
        lines = "\n".join(f"• {name}" for name in blocked_maps)
        message = (
            f"El personaje nivel {character_level} no puede ingresar a los "
            f"siguientes mapas seleccionados:\n\n{lines}"
        )
        log("[LEVEL] Kill Bosses maps blocked by level requirement")
        return LevelValidationResult(
            can_start=False,
            farm_blocked_message=message,
        )

    elf_buff = get_elf_buff_location(profile_name)
    return _validate_elf_buff_level(
        character_level,
        elf_buff,
        profile_elf_buff_enabled=_elf_buff_enabled_in_profile(profile_data),
    )


def _validate_farm_mode(profile_name, character_level, profile_data):
    farm_spot = get_farm_spot_location(profile_name)
    elf_buff = get_elf_buff_location(profile_name)
    profile_elf_buff_enabled = _elf_buff_enabled_in_profile(profile_data)

    if not farm_spot:
        log("[LEVEL] No active farm spot configured for level validation")
        return _validate_elf_buff_level(
            character_level,
            elf_buff,
            profile_elf_buff_enabled=profile_elf_buff_enabled,
        )

    farm_map_id = farm_spot.get("map")
    farm_min_level = get_map_min_level(farm_map_id)
    farm_map_name = get_map_display_name(farm_map_id)

    if character_level < farm_min_level:
        message = (
            f"El personaje nivel {character_level} no puede ingresar al mapa de "
            f"farmeo {farm_map_name}. Nivel requerido: {farm_min_level}."
        )
        log("[LEVEL] Farm map blocked by level requirement")
        return LevelValidationResult(
            can_start=False,
            farm_blocked_message=message,
            elf_buff_enabled=False,
            elf_buff_status="Desactivado por nivel",
        )

    return _validate_elf_buff_level(
        character_level,
        elf_buff,
        profile_elf_buff_enabled=profile_elf_buff_enabled,
    )


def validate_level_for_profile(profile_name, character_level, profile_data=None):
    if profile_data is None:
        profile_data = normalize_profile_data(
            load_profile(f"profiles/{profile_name}"),
            profile_name,
        )

    if get_bot_mode(profile_data) == "kill_bosses":
        return _validate_kill_bosses_maps(profile_data, character_level, profile_name)

    return _validate_farm_mode(profile_name, character_level, profile_data)
