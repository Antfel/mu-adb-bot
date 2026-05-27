MAPS = {
    "kalima_1": {
        "name": "Kalima Temple 1",
        "navigation": {
            "map_head_template": "templates/maps/Kalima_temple/mapsui/kalima_temple_head.png",
            "map_option_template": "templates/maps/Kalima_temple/mapsui/kalima_temple_1.png",
            "checked_template": "templates/maps/Kalima_temple/modalui/kalima_1_checked.png",
            "enter_template": "templates/maps/Kalima_temple/modalui/enter_button.png",
            "enter_wait": 8,
            "map_list_swipe": {
                "x1": 530,
                "y1": 708,
                "x2": 530,
                "y2": 600,
                "duration": 250,
            },
            "wire_list_swipe": {
                "x1": 530,
                "y1": 708,
                "x2": 530,
                "y2": 600,
                "duration": 250,
            },
        },
        "wires": {
            1: {
                "name": "Wire 1",
                "wire_template": "templates/maps/kalima_1/wires/wire_1.png",
                "wire_checked_template": "templates/maps/kalima_1/wires/wire_1_checked.png",
                "spots": {
                    "spot_1": {
                        "name": "Spot 1",
                        "spot_click": {"x": 1145, "y": 768},
                        "post_spot_actions": [
                            {"type": "wait", "seconds": 10},
                            {"type": "ensure_auto_mode"},
                        ],
                        "arrival_wait": 20,
                    }
                },
            },
            2: {
                "name": "Wire 2",
                "wire_template": "templates/maps/kalima_1/wires/wire_2.png",
                "wire_checked_template": "templates/maps/kalima_1/wires/wire_2_checked.png",
                "spots": {
                    "spot_1": {
                        "name": "Spot 1",
                        "spot_click": {"x": 1145, "y": 768},
                        "post_spot_actions": [
                            {"type": "wait", "seconds": 10},
                            {"type": "ensure_auto_mode"},
                        ],
                        "arrival_wait": 20,
                    }
                },
            },
            3: {
                "name": "Wire 3",
                "wire_template": "templates/maps/kalima_1/wires/wire_3.png",
                "wire_checked_template": "templates/maps/kalima_1/wires/wire_3_checked.png",
                "spots": {
                    "spot_1": {
                        "name": "Spot 1",
                        "spot_click": {"x": 1145, "y": 768},
                        "post_spot_actions": [
                            {"type": "wait", "seconds": 10},
                            {"type": "ensure_auto_mode"},
                        ],
                        "arrival_wait": 20,
                    }
                },
            },
            4: {
                "name": "Wire 4",
                "wire_template": "templates/maps/kalima_1/wires/wire_4.png",
                "wire_checked_template": "templates/maps/kalima_1/wires/wire_4_checked.png",
                "spots": {
                    "spot_1": {
                        "name": "Spot 1",
                        "spot_click": {"x": 1145, "y": 768},
                        "post_spot_actions": [
                            {"type": "wait", "seconds": 10},
                            {"type": "ensure_auto_mode"},
                        ],
                        "arrival_wait": 20,
                    }
                },
            },
            5: {
                "name": "Wire 5",
                "wire_template": "templates/maps/kalima_1/wires/wire_5.png",
                "wire_checked_template": "templates/maps/kalima_1/wires/wire_5_checked.png",
                "spots": {
                    "spot_1": {
                        "name": "Spot 1",
                        "spot_click": {"x": 1145, "y": 768},
                        "post_spot_actions": [
                            {"type": "wait", "seconds": 10},
                            {"type": "ensure_auto_mode"},
                        ],
                        "arrival_wait": 20,
                    }
                },
            },
        },
    }
}


def normalize_wire_id(wire):
    return int(wire)


def get_map_data(map_id):
    if map_id not in MAPS:
        raise KeyError(f"Map not configured: {map_id}")
    return MAPS[map_id]


def get_wire_ids(map_id):
    return list(get_map_data(map_id)["wires"].keys())


def get_wire_data(map_id, wire_id):
    map_data = get_map_data(map_id)
    wire_id = normalize_wire_id(wire_id)

    if wire_id not in map_data["wires"]:
        raise KeyError(f"Wire {wire_id} not configured for map {map_id}")

    return map_data["wires"][wire_id]


def get_spot_ids(map_id, wire_id):
    return list(get_wire_data(map_id, wire_id)["spots"].keys())


def resolve_farm_target(profile):
    map_id = profile["map"]
    wire_id = normalize_wire_id(profile["wire"])
    spot_id = profile["spot"]

    map_data = get_map_data(map_id)
    wire_data = get_wire_data(map_id, wire_id)

    if spot_id not in wire_data["spots"]:
        raise KeyError(
            f"Spot {spot_id} not configured for map {map_id} wire {wire_id}"
        )

    spot_data = wire_data["spots"][spot_id]

    return map_data, wire_data, spot_data
