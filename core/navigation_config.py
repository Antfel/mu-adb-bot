import json
from pathlib import Path

from core.logger import log
from core.path_utils import resource_path


_CACHE = None


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
    return _CACHE


def list_available_maps():
    defs = load_all_map_definitions()
    return sorted(defs.keys())


def get_map_wires(map_id):
    definition = load_map_definition(map_id)
    return sorted(definition.get("wires", {}).keys())


def get_map_spots(map_id):
    definition = load_map_definition(map_id)
    return definition.get("spots", {})

