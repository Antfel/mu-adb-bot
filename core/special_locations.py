import json
import re
from pathlib import Path

from core.logger import log
from core.path_utils import data_file_path


_LOCATIONS_PATH = Path(data_file_path("special_locations/user_locations.json"))
_ACTIVE_SINGLE_TYPES = ("farm_spot", "elf_buff")


def _ensure_file():
    _LOCATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _LOCATIONS_PATH.exists():
        save_special_locations({"locations": []})


def normalize_profile_name(profile_name):
    if not profile_name:
        return None
    name = str(profile_name).strip()
    if not name:
        return None
    if not name.endswith(".json"):
        name = f"{name}.json"
    return name


def load_special_locations():
    _ensure_file()
    with _LOCATIONS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_special_locations(data):
    _LOCATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCATIONS_PATH.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def list_locations(location_type=None):
    data = load_special_locations()
    locations = data.get("locations", [])

    if location_type is None:
        return locations

    return [loc for loc in locations if loc.get("type") == location_type]


def get_location(location_id):
    for location in list_locations():
        if location.get("id") == location_id:
            return location
    return None


def get_active_location(profile_name, location_type):
    profile = normalize_profile_name(profile_name)
    if not profile:
        return None

    for location in list_locations(location_type):
        if normalize_profile_name(location.get("profile")) == profile:
            return location

    return None


def get_farm_spot_location(profile_name):
    location = get_active_location(profile_name, "farm_spot")
    if location:
        log(
            f"[LOCATIONS] Active farm spot for {normalize_profile_name(profile_name)}: "
            f"{location.get('id')}"
        )
    else:
        log(
            f"[LOCATIONS] No active farm spot for profile "
            f"{normalize_profile_name(profile_name)!r}"
        )
    return location


def get_elf_buff_location(profile_name):
    location = get_active_location(profile_name, "elf_buff")
    if location:
        log(
            f"[LOCATIONS] Active elf buff for {normalize_profile_name(profile_name)}: "
            f"{location.get('id')}"
        )
    else:
        log(
            f"[LOCATIONS] No active elf buff for profile "
            f"{normalize_profile_name(profile_name)!r}"
        )
    return location


def upsert_location(location):
    data = load_special_locations()
    locations = data.get("locations", [])

    location_type = location.get("type")
    profile = normalize_profile_name(location.get("profile"))

    if location_type in _ACTIVE_SINGLE_TYPES:
        if not profile:
            raise ValueError(f"profile is required for {location_type}")

        location["profile"] = profile
        location["id"] = make_location_id(profile, location_type)

        locations = [
            loc
            for loc in locations
            if not (
                loc.get("type") == location_type
                and normalize_profile_name(loc.get("profile")) == profile
            )
        ]
        locations.append(location)
        data["locations"] = locations
        save_special_locations(data)
        log(
            f"[LOCATIONS] Replaced active {location_type} for {profile}: "
            f"{location['id']}"
        )
        return location

    location_id = location.get("id")
    if not location_id:
        raise ValueError("Location id is required")

    updated = False
    for index, existing in enumerate(locations):
        if existing.get("id") == location_id:
            locations[index] = location
            updated = True
            break

    if not updated:
        locations.append(location)

    data["locations"] = locations
    save_special_locations(data)
    log(f"[LOCATIONS] Saved location: {location_id}")
    return location


def delete_location(location_id):
    data = load_special_locations()
    locations = data.get("locations", [])
    new_locations = [loc for loc in locations if loc.get("id") != location_id]

    if len(new_locations) == len(locations):
        return False

    data["locations"] = new_locations
    save_special_locations(data)
    log(f"[LOCATIONS] Deleted location: {location_id}")
    return True


def make_location_id(profile_name, location_type, name=None):
    profile_key = normalize_profile_name(profile_name).replace(".json", "")
    if location_type in _ACTIVE_SINGLE_TYPES:
        return f"{profile_key}_{location_type}"

    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", (name or "").strip().lower()).strip("_")
    if not safe_name:
        safe_name = "unnamed"
    return f"{profile_key}_{location_type}_{safe_name}"
