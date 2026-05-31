import copy
import json
import os
import re
import shutil
import unicodedata

from core.path_utils import data_file_path, data_path
from core.special_locations import (
    delete_profile_locations,
    duplicate_profile_locations,
    get_elf_buff_location,
)

MIN_DISPLAY_NAME_LENGTH = 3

DEFAULT_BOT_MODE = "farm"

DEFAULT_GENERAL_CONFIG = {
    "enable_elf_buff": True,
}

DEFAULT_FARM_CONFIG = {
    "enabled": True,
}

DEFAULT_KILL_BOSSES_CONFIG = {
    "enabled": False,
    "maps": [],
    "include_golden_mobs": False,
}

NEW_PROFILE_TEMPLATE = {
    "display_name": "",
    "character_level": None,
    "bot_mode": DEFAULT_BOT_MODE,
    "hp_potion_stacks": 10,
    "mp_potion_stacks": 10,
    "enable_potion_recovery": True,
    "enable_death_recovery": True,
    "enable_auto_attack": True,
    "general_config": dict(DEFAULT_GENERAL_CONFIG),
    "farm_config": dict(DEFAULT_FARM_CONFIG),
    "kill_bosses_config": {
        "enabled": False,
        "maps": [],
        "include_golden_mobs": False,
    },
}

DEFAULT_PROFILE_TEMPLATE = dict(NEW_PROFILE_TEMPLATE)
DEFAULT_PROFILE_TEMPLATE.update(
    {
        "map": "",
        "wire": 1,
        "spot": "spot_1",
    }
)

BOT_MODE_LABEL_BY_VALUE = {
    "farm": "Farm",
    "kill_bosses": "Kill Bosses",
}
BOT_MODE_VALUE_BY_LABEL = {label: value for value, label in BOT_MODE_LABEL_BY_VALUE.items()}


def _profiles_dir():
    return data_path("profiles")


def _profile_file_path(profile_name):
    if profile_name.startswith("profiles/"):
        return data_file_path(profile_name)
    if profile_name.endswith(".json"):
        return data_file_path(f"profiles/{profile_name}")
    return data_file_path(f"profiles/{profile_name}.json")


def _current_profile_path():
    return data_file_path("profiles/current.json")


def _pointer_path():
    return data_file_path("profiles/.current_profile_name")


def profile_file_stem(profile_filename):
    name = str(profile_filename).strip()
    if name.endswith(".json"):
        return name[:-5]
    return name


def get_display_name(profile_data, profile_filename):
    display = profile_data.get("display_name") if profile_data else None
    if display is not None and str(display).strip():
        return str(display).strip()
    return profile_file_stem(profile_filename)


def slugify_profile_filename(display_name):
    normalized = unicodedata.normalize("NFKD", str(display_name).strip())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug or "perfil"


def make_safe_profile_filename(display_name, *, with_extension=True):
    stem = slugify_profile_filename(display_name)
    return f"{stem}.json" if with_extension else stem


def display_name_exists(display_name, exclude_filename=None):
    normalized = str(display_name).strip().casefold()
    if not normalized:
        return False

    exclude = None
    if exclude_filename:
        exclude = (
            exclude_filename
            if exclude_filename.endswith(".json")
            else f"{exclude_filename}.json"
        )

    for entry in list_profile_entries():
        if exclude and entry["filename"] == exclude:
            continue
        if entry["display_name"].casefold() == normalized:
            return True
    return False


def validate_display_name(display_name, exclude_filename=None):
    text = str(display_name).strip()
    if not text:
        raise ValueError("El nombre no puede estar vacío.")
    if len(text) < MIN_DISPLAY_NAME_LENGTH:
        raise ValueError(
            f"El nombre debe tener al menos {MIN_DISPLAY_NAME_LENGTH} caracteres."
        )
    if display_name_exists(text, exclude_filename):
        raise ValueError("Ya existe un perfil con ese nombre visible.")
    return text


def build_new_profile_data(display_name):
    profile_data = copy.deepcopy(NEW_PROFILE_TEMPLATE)
    profile_data["display_name"] = display_name
    profile_data["character_level"] = None
    return normalize_profile_data(profile_data)


def generate_unique_profile_filename(display_name):
    base = slugify_profile_filename(display_name)
    candidate = f"{base}.json"
    if not os.path.exists(_profile_file_path(candidate)):
        return candidate

    index = 2
    while True:
        candidate = f"{base}_{index}.json"
        if not os.path.exists(_profile_file_path(candidate)):
            return candidate
        index += 1


def _infer_enable_elf_buff(profile_data, profile_filename=None):
    general_config = profile_data.get("general_config")
    if isinstance(general_config, dict) and "enable_elf_buff" in general_config:
        return bool(general_config["enable_elf_buff"])

    if profile_filename:
        elf_buff = get_elf_buff_location(profile_filename)
        if elf_buff and elf_buff.get("map"):
            return True

    return True


def normalize_profile_data(profile_data, profile_filename=None):
    if not isinstance(profile_data, dict):
        profile_data = {}

    mode = profile_data.get("bot_mode", DEFAULT_BOT_MODE)
    if mode not in BOT_MODE_LABEL_BY_VALUE:
        mode = DEFAULT_BOT_MODE
    profile_data["bot_mode"] = mode

    general_config = profile_data.get("general_config")
    if not isinstance(general_config, dict):
        general_config = dict(DEFAULT_GENERAL_CONFIG)
    general_config.setdefault(
        "enable_elf_buff",
        _infer_enable_elf_buff(profile_data, profile_filename),
    )
    profile_data["general_config"] = general_config

    farm_config = profile_data.get("farm_config")
    if not isinstance(farm_config, dict):
        farm_config = dict(DEFAULT_FARM_CONFIG)
    farm_config.setdefault("enabled", DEFAULT_FARM_CONFIG["enabled"])
    profile_data["farm_config"] = farm_config

    kill_bosses_config = profile_data.get("kill_bosses_config")
    if not isinstance(kill_bosses_config, dict):
        kill_bosses_config = dict(DEFAULT_KILL_BOSSES_CONFIG)
    kill_bosses_config.setdefault("enabled", DEFAULT_KILL_BOSSES_CONFIG["enabled"])
    maps = kill_bosses_config.get("maps")
    if not isinstance(maps, list):
        maps = []
    kill_bosses_config["maps"] = [str(map_id) for map_id in maps]
    kill_bosses_config.setdefault("include_golden_mobs", False)
    profile_data["kill_bosses_config"] = kill_bosses_config

    return profile_data


def get_bot_mode(profile_data):
    return normalize_profile_data(profile_data)["bot_mode"]


def get_bot_mode_display_label(profile_data):
    mode = get_bot_mode(profile_data)
    return BOT_MODE_LABEL_BY_VALUE.get(mode, BOT_MODE_LABEL_BY_VALUE[DEFAULT_BOT_MODE])


def bot_mode_from_label(label):
    return BOT_MODE_VALUE_BY_LABEL.get(label, DEFAULT_BOT_MODE)


def _config_mode_enabled(config):
    if not isinstance(config, dict):
        return False
    enabled = config.get("enabled")
    if enabled is None:
        return False
    return bool(enabled)


def get_available_bot_mode_labels(profile_data=None, profile_filename=None):
    """
    Build main-screen bot type options from farm_config/kill_bosses_config.enabled.
    bot_mode is only a fallback when no enabled flags are set (legacy profiles).
    """
    data = profile_data if isinstance(profile_data, dict) else {}

    if profile_filename:
        try:
            data = load_profile(f"profiles/{profile_filename}")
        except (OSError, ValueError, json.JSONDecodeError):
            return [BOT_MODE_LABEL_BY_VALUE[DEFAULT_BOT_MODE]]

    labels = []
    if _config_mode_enabled(data.get("farm_config")):
        labels.append(BOT_MODE_LABEL_BY_VALUE["farm"])
    if _config_mode_enabled(data.get("kill_bosses_config")):
        labels.append(BOT_MODE_LABEL_BY_VALUE["kill_bosses"])

    if not labels:
        normalized = normalize_profile_data(data, profile_filename)
        mode = normalized.get("bot_mode", DEFAULT_BOT_MODE)
        if mode not in BOT_MODE_LABEL_BY_VALUE:
            mode = DEFAULT_BOT_MODE
        labels.append(BOT_MODE_LABEL_BY_VALUE[mode])

    return labels


def get_profile_display_name(profile_filename):
    if not profile_filename or not str(profile_filename).strip():
        return "-"

    name = str(profile_filename).strip()
    if not name.endswith(".json"):
        name = f"{name}.json"

    try:
        profile_data = load_profile(f"profiles/{name}")
    except (OSError, ValueError, json.JSONDecodeError):
        return profile_file_stem(name)

    return get_display_name(profile_data, name)


def list_profile_entries():
    entries = []
    for filename in list_profiles():
        profile_data = load_profile(f"profiles/{filename}")
        entries.append(
            {
                "filename": filename,
                "display_name": get_display_name(profile_data, filename),
            }
        )
    entries.sort(key=lambda item: item["display_name"].casefold())
    return entries


def list_profiles_with_display_names():
    entries = list_profile_entries()
    filename_to_display_name = {}
    display_name_to_filename = {}
    display_names = []
    seen_display_keys = {}

    for entry in entries:
        filename = entry["filename"]
        display_name = entry["display_name"]
        filename_to_display_name[filename] = display_name

        display_key = display_name.casefold()
        if display_key in seen_display_keys:
            combo_label = f"{display_name} ({profile_file_stem(filename)})"
        else:
            combo_label = display_name
            seen_display_keys[display_key] = filename

        display_name_to_filename[combo_label] = filename
        display_names.append(combo_label)

    return {
        "entries": entries,
        "display_names": display_names,
        "filename_to_display_name": filename_to_display_name,
        "display_name_to_filename": display_name_to_filename,
    }


def _clear_current_profile_pointer():
    pointer = _pointer_path()
    if os.path.exists(pointer):
        os.remove(pointer)


def create_profile(display_name, template_data=None):
    display_name = validate_display_name(display_name)
    filename = generate_unique_profile_filename(display_name)

    if template_data is None:
        profile_data = build_new_profile_data(display_name)
    else:
        profile_data = normalize_profile_data(copy.deepcopy(template_data))
        profile_data["display_name"] = display_name

    save_profile(profile_data, f"profiles/{filename}")
    return filename


def duplicate_profile(source_filename, new_display_name):
    source_filename = str(source_filename).strip()
    if not source_filename.endswith(".json"):
        source_filename = f"{source_filename}.json"

    source_path = _profile_file_path(source_filename)
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Perfil no encontrado: {source_filename}")

    new_display_name = validate_display_name(new_display_name)
    source_data = normalize_profile_data(
        load_profile(f"profiles/{source_filename}"),
        source_filename,
    )

    profile_data = copy.deepcopy(source_data)
    profile_data["display_name"] = new_display_name

    filename = generate_unique_profile_filename(new_display_name)
    save_profile(profile_data, f"profiles/{filename}")
    duplicate_profile_locations(source_filename, filename)
    return filename


def delete_profile(filename):
    filename = str(filename).strip()
    if not filename.endswith(".json"):
        filename = f"{filename}.json"

    profile_path = _profile_file_path(filename)
    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Perfil no encontrado: {filename}")

    current_name = get_current_profile_name()
    remaining_before_delete = [p for p in list_profiles() if p != filename]

    print("[PROFILE_UI] before delete_profile_locations", flush=True)
    delete_profile_locations(filename)
    print("[PROFILE_UI] after delete_profile_locations", flush=True)

    print(f"[PROFILE_UI] before os.remove({profile_path})", flush=True)
    os.remove(profile_path)
    print("[PROFILE_UI] after os.remove", flush=True)

    if current_name == filename:
        if remaining_before_delete:
            set_current_profile(remaining_before_delete[0])
        else:
            _clear_current_profile_pointer()

    return filename


def load_profile(profile_path=None):
    if profile_path is None:
        resolved = _current_profile_path()
    elif profile_path.startswith("profiles/") or not os.path.isabs(profile_path):
        resolved = (
            _profile_file_path(profile_path.replace("profiles/", ""))
            if profile_path.startswith("profiles/")
            else _profile_file_path(profile_path)
        )
    else:
        resolved = profile_path

    with open(resolved, "r", encoding="utf-8") as file:
        return json.load(file)


def save_profile(profile_data, profile_path=None):
    if profile_path is None:
        resolved = _current_profile_path()
    elif profile_path.startswith("profiles/") or not os.path.isabs(profile_path):
        resolved = (
            _profile_file_path(profile_path.replace("profiles/", ""))
            if profile_path.startswith("profiles/")
            else _profile_file_path(profile_path)
        )
    else:
        resolved = profile_path

    with open(resolved, "w", encoding="utf-8") as file:
        json.dump(profile_data, file, indent=4)


def list_profiles():
    profiles = []
    profiles_dir = _profiles_dir()

    for file in os.listdir(profiles_dir):
        if file.endswith(".json") and file != "current.json":
            profiles.append(file)

    return profiles


def _write_current_profile_pointer(profile_name):
    with open(_pointer_path(), "w", encoding="utf-8") as file:
        file.write(profile_name)


def get_current_profile_name():
    pointer = _pointer_path()
    if os.path.exists(pointer):
        with open(pointer, "r", encoding="utf-8") as file:
            profile_name = file.read().strip()
            if profile_name:
                return profile_name

    profiles = list_profiles()
    if len(profiles) == 1:
        return profiles[0]

    return None


def set_current_profile(profile_name):
    source = _profile_file_path(profile_name)
    shutil.copyfile(source, _current_profile_path())
    _write_current_profile_pointer(profile_name)
