import json
import os
import shutil

from core.path_utils import data_file_path, data_path


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
