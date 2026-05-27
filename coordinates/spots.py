"""
Legacy module. Navigation definitions now live in navigation/maps/*.json
"""

from core.navigation_config import load_all_map_definitions, load_map_definition


# Backward-compatible export. Prefer using core.navigation_config directly.
MAPS = load_all_map_definitions()


def normalize_wire_id(wire):
    return int(wire)


def get_map_data(map_id):
    return load_map_definition(map_id)


def get_wire_ids(map_id):
    return list(get_map_data(map_id)["wires"].keys())


def get_wire_data(map_id, wire_id):
    map_data = get_map_data(map_id)
    wire_id = normalize_wire_id(wire_id)

    if wire_id not in map_data["wires"]:
        raise KeyError(f"Wire {wire_id} not configured for map {map_id}")

    return map_data["wires"][wire_id]


def get_spot_ids(map_id, wire_id):
    wire_data = get_wire_data(map_id, wire_id)
    spots = wire_data.get("spots", [])
    if isinstance(spots, dict):
        return list(spots.keys())
    return list(spots)


def resolve_farm_target(profile):
    map_id = profile["map"]
    wire_id = normalize_wire_id(profile["wire"])
    spot_id = profile["spot"]

    map_data = get_map_data(map_id)
    wire_data = get_wire_data(map_id, wire_id)

    # New map definitions store spots at top-level: map_data["spots"][spot_id].
    # Old shape kept them under wire_data["spots"][spot_id].
    if "spots" in map_data and spot_id in map_data["spots"]:
        spot_data = map_data["spots"][spot_id]
    else:
        wire_spots = wire_data.get("spots", {})
        if isinstance(wire_spots, dict) and spot_id in wire_spots:
            spot_data = wire_spots[spot_id]
        else:
            raise KeyError(
                f"Spot {spot_id} not configured for map {map_id} wire {wire_id}"
            )

    return map_data, wire_data, spot_data
