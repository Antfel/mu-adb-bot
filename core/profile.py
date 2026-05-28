import json
import os
import shutil

PROFILES_DIR = "profiles"
CURRENT_PROFILE = f"{PROFILES_DIR}/current.json"
CURRENT_PROFILE_POINTER = f"{PROFILES_DIR}/.current_profile_name"


def load_profile(profile_path=CURRENT_PROFILE):
    with open(profile_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_profile(profile_data, profile_path=CURRENT_PROFILE):
    with open(profile_path, "w", encoding="utf-8") as file:
        json.dump(profile_data, file, indent=4)


def list_profiles():
    profiles = []

    for file in os.listdir(PROFILES_DIR):
        if file.endswith(".json") and file != "current.json":
            profiles.append(file)

    return profiles


def _write_current_profile_pointer(profile_name):
    with open(CURRENT_PROFILE_POINTER, "w", encoding="utf-8") as file:
        file.write(profile_name)


def get_current_profile_name():
    if os.path.exists(CURRENT_PROFILE_POINTER):
        with open(CURRENT_PROFILE_POINTER, "r", encoding="utf-8") as file:
            profile_name = file.read().strip()
            if profile_name:
                return profile_name

    profiles = list_profiles()
    if len(profiles) == 1:
        return profiles[0]

    return None


def set_current_profile(profile_name):
    source = f"{PROFILES_DIR}/{profile_name}"

    shutil.copyfile(source, CURRENT_PROFILE)
    _write_current_profile_pointer(profile_name)