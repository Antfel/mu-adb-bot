from dataclasses import dataclass

from core.logger import log
from core.navigation_config import load_map_definition
from core.special_locations import get_elf_buff_location, get_farm_spot_location


@dataclass
class LevelValidationResult:
    can_start: bool
    farm_blocked_message: str | None = None
    elf_buff_enabled: bool = False
    elf_buff_status: str = "No configurado"
    show_elf_warning: bool = False


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


def _validate_elf_buff_level(character_level, elf_buff):
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


def validate_level_for_profile(profile_name, character_level):
    farm_spot = get_farm_spot_location(profile_name)
    elf_buff = get_elf_buff_location(profile_name)

    if not farm_spot:
        log("[LEVEL] No active farm spot configured for level validation")
        return _validate_elf_buff_level(character_level, elf_buff)

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

    return _validate_elf_buff_level(character_level, elf_buff)
