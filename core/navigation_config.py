import json
from pathlib import Path

from core.logger import log
from core.path_utils import resource_path


_CACHE = None

SUPPORTED_NAVIGATION_BEHAVIORS = frozenset({
    "direct_teleport",
    "modal_enter",
    "event_ticket_npc_enter",
    "event_list_enter",
    "event_list_npc_enter",
})

IMPLEMENTED_NAVIGATION_BEHAVIORS = frozenset({
    "direct_teleport",
    "modal_enter",
})

NAVIGATION_REQUIRED_KEYS = (
    "behavior",
    "current_map_template",
    "map_option_template",
)


def _definitions_dir():
    return Path(resource_path("navigation/maps"))


def _normalize_map_definition(raw):
    """
    Normaliza tipos (p.ej. keys de wires en JSON) para que el runtime use ints.
    Mantiene el resto del shape para compatibilidad.
    """
    if not isinstance(raw, dict):
        raise ValueError("Map definition must be a JSON object")

    map_id = raw.get("id")
    if not map_id:
        raise ValueError("Map definition missing required field: id")

    wires_raw = raw.get("wires", {})
    wires = {}
    for k, v in wires_raw.items():
        try:
            wire_id = int(k)
        except Exception:
            raise ValueError(f"Invalid wire id: {k!r} in map {map_id}")
        wires[wire_id] = v

    normalized = dict(raw)
    normalized["wires"] = wires
    return normalized


def load_map_definition(map_id):
    path = _definitions_dir() / f"{map_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Map definition not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    definition = _normalize_map_definition(raw)
    return definition


def load_all_map_definitions(force_reload=False):
    global _CACHE

    if _CACHE is not None and not force_reload:
        return _CACHE

    maps_dir = _definitions_dir()
    if not maps_dir.exists():
        log(f"[NAVCFG] Maps directory not found: {maps_dir}")
        _CACHE = {}
        return _CACHE

    definitions = {}
    for path in sorted(maps_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            definition = _normalize_map_definition(raw)
            definitions[definition["id"]] = definition
        except Exception as e:
            log(f"[NAVCFG] Failed to load {path.name}: {e}")

    _CACHE = definitions
    return definitions


def _navigation_block(map_def):
    navigation = map_def.get("navigation")
    if not isinstance(navigation, dict):
        return None
    return navigation


def navigation_behavior(map_def):
    navigation = _navigation_block(map_def)
    if not navigation:
        return None
    behavior = navigation.get("behavior")
    if behavior is None:
        return None
    behavior = str(behavior).strip()
    return behavior or None


def log_unsupported_navigation_behavior(map_def):
    behavior = navigation_behavior(map_def) or "?"
    map_id = map_def.get("id", "?")
    log(f"[NAVIGATION] Unsupported behavior: {behavior} for map {map_id}")


def is_navigation_supported(map_def):
    behavior = navigation_behavior(map_def)
    if not behavior:
        return False
    return behavior in SUPPORTED_NAVIGATION_BEHAVIORS


def is_navigation_implemented(map_def):
    behavior = navigation_behavior(map_def)
    if not behavior:
        return False
    return behavior in IMPLEMENTED_NAVIGATION_BEHAVIORS


def _has_required_navigation_templates(map_def):
    navigation = _navigation_block(map_def)
    if not navigation:
        return False
    return all(navigation.get(key) for key in NAVIGATION_REQUIRED_KEYS)


def is_map_navigable(map_def):
    """
    Map usable by farm spot, elf buff, and runtime navigation today:
    supported + implemented behavior with required navigation templates.
    """
    navigation = _navigation_block(map_def)
    if not navigation:
        return False

    behavior = navigation_behavior(map_def)
    if not behavior:
        return False

    if behavior not in SUPPORTED_NAVIGATION_BEHAVIORS:
        log_unsupported_navigation_behavior(map_def)
        return False

    if not is_navigation_implemented(map_def):
        return False

    return _has_required_navigation_templates(map_def)


def _map_sort_key(map_def):
    order = map_def.get("order")
    try:
        order = int(order) if order is not None else 9999
    except (TypeError, ValueError):
        order = 9999

    submap = map_def.get("submap", 1)
    try:
        submap = int(submap)
    except (TypeError, ValueError):
        submap = 1

    name = map_def.get("name") or map_def.get("id", "")
    return (order, submap, name)


def _collect_navigation_maps(*, predicate, include_map_ids=None):
    defs = load_all_map_definitions()
    include_ids = {str(map_id) for map_id in (include_map_ids or []) if map_id}

    collected = []
    seen = set()

    for map_id in include_ids:
        map_def = defs.get(map_id)
        if map_def and predicate(map_def) and map_id not in seen:
            collected.append(map_def)
            seen.add(map_id)

    for map_def in defs.values():
        map_id = map_def["id"]
        if map_id in seen:
            continue
        if predicate(map_def):
            collected.append(map_def)
            seen.add(map_id)

    return sorted(collected, key=_map_sort_key)


def list_supported_navigation_maps(*, include_map_ids=None):
    return _collect_navigation_maps(
        predicate=is_navigation_supported,
        include_map_ids=include_map_ids,
    )


def list_implemented_navigation_maps(*, include_map_ids=None):
    return _collect_navigation_maps(
        predicate=is_map_navigable,
        include_map_ids=include_map_ids,
    )


def list_navigable_maps(*, include_map_ids=None):
    """Alias: maps the bot can navigate today (implemented behaviors + templates)."""
    return list_implemented_navigation_maps(include_map_ids=include_map_ids)


def list_available_maps():
    return [map_def["id"] for map_def in list_implemented_navigation_maps()]


def list_maps_for_kill_boss_ui(*, include_map_ids=None):
    return [
        {
            "id": map_def["id"],
            "name": map_def.get("name") or map_def["id"],
        }
        for map_def in list_implemented_navigation_maps(include_map_ids=include_map_ids)
    ]


def get_map_wires(map_id):
    definition = load_map_definition(map_id)
    return sorted(definition.get("wires", {}).keys())


def get_map_spots(map_id):
    definition = load_map_definition(map_id)
    return definition.get("spots", {})
