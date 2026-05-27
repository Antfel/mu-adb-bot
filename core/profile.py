import json
import os
import shutil

PROFILES_DIR = "profiles"
CURRENT_PROFILE = f"{PROFILES_DIR}/current.json"


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


def set_current_profile(profile_name):
    source = f"{PROFILES_DIR}/{profile_name}"

    shutil.copyfile(source, CURRENT_PROFILE)