import numpy as np

from core.logger import log


DEFAULT_ARRIVAL_RADIUS = 5
DEFAULT_FARM_RADIUS = 20
DEFAULT_LOST_RADIUS = 35


def has_coordinate_mapping(map_def):
    mapping = map_def.get("coordinate_mapping") if map_def else None
    if not isinstance(mapping, dict):
        return False
    if mapping.get("type") != "affine":
        return False
    transform = mapping.get("transform")
    if not isinstance(transform, dict):
        return False
    coord_x = transform.get("coord_x")
    coord_y = transform.get("coord_y")
    return (
        isinstance(coord_x, (list, tuple))
        and len(coord_x) == 3
        and isinstance(coord_y, (list, tuple))
        and len(coord_y) == 3
    )


def _normalize_pixel_for_mapping(map_def, pixel_x, pixel_y):
    mapping = map_def.get("coordinate_mapping", {})
    source = mapping.get("source_image_size", {})
    maintenance = map_def.get("maintenance", {})

    source_w = source.get("width") or maintenance.get("image_width") or 2560
    source_h = source.get("height") or maintenance.get("image_height") or 1440
    maint_w = maintenance.get("image_width") or source_w
    maint_h = maintenance.get("image_height") or source_h

    try:
        source_w = float(source_w)
        source_h = float(source_h)
        maint_w = float(maint_w)
        maint_h = float(maint_h)
    except (TypeError, ValueError):
        return float(pixel_x), float(pixel_y)

    if maint_w <= 0 or maint_h <= 0:
        return float(pixel_x), float(pixel_y)

    scaled_x = float(pixel_x) * (source_w / maint_w)
    scaled_y = float(pixel_y) * (source_h / maint_h)
    return scaled_x, scaled_y


def pixel_to_map_coord(map_def, pixel_x, pixel_y):
    if not has_coordinate_mapping(map_def):
        map_id = (map_def or {}).get("id", "?")
        log(f"[COORD] No coordinate mapping for map {map_id}")
        return None

    transform = map_def["coordinate_mapping"]["transform"]
    a, b, c = (float(v) for v in transform["coord_x"])
    d, e, f = (float(v) for v in transform["coord_y"])

    px, py = _normalize_pixel_for_mapping(map_def, pixel_x, pixel_y)
    coord_x = round(a * px + b * py + c)
    coord_y = round(d * px + e * py + f)
    return int(coord_x), int(coord_y)


def distance_coords(a, b, method="manhattan"):
    ax, ay = int(a[0]), int(a[1])
    bx, by = int(b[0]), int(b[1])

    if method == "euclidean":
        return int(round(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5))

    return abs(ax - bx) + abs(ay - by)


def is_within_radius(current, target, radius):
    return distance_coords(current, target, method="manhattan") <= int(radius)


def location_has_coordinates(location):
    if not isinstance(location, dict):
        return False
    coord_x = location.get("coord_x")
    coord_y = location.get("coord_y")
    if coord_x is None or coord_y is None:
        return False
    try:
        int(coord_x)
        int(coord_y)
    except (TypeError, ValueError):
        return False
    return True


def get_location_target_coord(location):
    if not location_has_coordinates(location):
        return None
    return int(location["coord_x"]), int(location["coord_y"])


def apply_coordinate_defaults(location):
    if not location_has_coordinates(location):
        return location

    location.setdefault("arrival_radius", DEFAULT_ARRIVAL_RADIUS)
    location.setdefault("farm_radius", DEFAULT_FARM_RADIUS)
    location.setdefault("lost_radius", DEFAULT_LOST_RADIUS)
    return location


def compute_affine_transform(points):
    """
    Compute affine transform coefficients from 3 calibration point pairs.

    points: [
      {"pixel": [px, py], "coord": [cx, cy]},
      ...
    ]
    """
    if len(points) != 3:
        raise ValueError("Affine transform requires exactly 3 point pairs")

    matrix = []
    target_x = []
    target_y = []

    for point in points:
        pixel = point.get("pixel")
        coord = point.get("coord")
        if (
            not isinstance(pixel, (list, tuple))
            or len(pixel) != 2
            or not isinstance(coord, (list, tuple))
            or len(coord) != 2
        ):
            raise ValueError("Each point must include pixel [x,y] and coord [x,y]")

        px, py = float(pixel[0]), float(pixel[1])
        cx, cy = float(coord[0]), float(coord[1])
        matrix.append([px, py, 1.0])
        target_x.append(cx)
        target_y.append(cy)

    A = np.array(matrix, dtype=np.float64)
    bx = np.array(target_x, dtype=np.float64)
    by = np.array(target_y, dtype=np.float64)

    coord_x = np.linalg.solve(A, bx).tolist()
    coord_y = np.linalg.solve(A, by).tolist()

    return {
        "coord_x": coord_x,
        "coord_y": coord_y,
    }


def _manual_self_test():
    points = [
        {"pixel": [0, 0], "coord": [100, 200]},
        {"pixel": [100, 0], "coord": [110, 200]},
        {"pixel": [0, 100], "coord": [100, 210]},
    ]
    transform = compute_affine_transform(points)
    map_def = {
        "id": "test_map",
        "coordinate_mapping": {
            "type": "affine",
            "version": 1,
            "source_image_size": {"width": 2560, "height": 1440},
            "transform": transform,
        },
        "maintenance": {"image_width": 2560, "image_height": 1440},
    }
    assert has_coordinate_mapping(map_def)
    assert pixel_to_map_coord(map_def, 0, 0) == (100, 200)
    assert pixel_to_map_coord(map_def, 100, 0) == (110, 200)
    assert is_within_radius((100, 200), (102, 201), 5)
    log("[COORD] coordinate_mapping self-test passed")


if __name__ == "__main__":
    _manual_self_test()
