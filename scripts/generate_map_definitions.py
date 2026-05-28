#!/usr/bin/env python3
"""Generate navigation/maps/*.json from maintenance reference images."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = ROOT / "navigation" / "maps"
TEMPLATES_DIR = ROOT / "templates" / "maps"


def friendly_words(text):
    return " ".join(word.capitalize() for word in text.split("_"))


def normalize_legacy_map_id(map_id):
    if map_id.startswith("rakion_"):
        return "raklion_" + map_id[len("rakion_") :]
    if map_id.startswith("pain_of_four_winds"):
        return "plain_of_four_winds" + map_id[len("pain_of_four_winds") :]
    return map_id


def normalize_legacy_folder(folder_name):
    if folder_name == "Rakion":
        return "Raklion"
    if folder_name == "Pain_of_four_winds":
        return "Plain_of_four_winds"
    return folder_name


def parse_map_id(filename):
    map_id = filename.replace("_map_open_reference.png", "")
    return normalize_legacy_map_id(map_id)


def parse_submap(map_id):
    match = re.search(r"_(\d+)$", map_id)
    return int(match.group(1)) if match else 1


def parse_name(map_id, group):
    match = re.search(r"_(\d+)$", map_id)
    if match:
        base = map_id[: match.start()]
        base_friendly = friendly_words(base) if base else group
        return f"{base_friendly} {match.group(1)}".strip()
    return friendly_words(map_id)


def normalize_legacy_rel_path(rel_path):
    rel_path = rel_path.replace("/Rakion/", "/Raklion/").replace(
        "/Pain_of_four_winds/", "/Plain_of_four_winds/"
    )
    return rel_path.replace("rakion_", "raklion_").replace(
        "pain_of_four_winds", "plain_of_four_winds"
    )


def build_base_entry(map_id, folder_name, image_path):
    folder_name = normalize_legacy_folder(folder_name)
    group = friendly_words(folder_name)
    submap = parse_submap(map_id)
    name = parse_name(map_id, group)

    rel_path = normalize_legacy_rel_path(image_path.relative_to(ROOT).as_posix())

    return {
        "id": map_id,
        "name": name,
        "group": group,
        "submap": submap,
        "requirements": {"min_level": 0},
        "maintenance": {
            "map_ui_image": rel_path,
            "image_width": 2560,
            "image_height": 1440,
        },
    }


def merge_entry(existing, base):
    merged = dict(existing)
    changed = False

    for key in ("id", "name", "group", "submap", "requirements", "maintenance"):
        if key not in merged:
            merged[key] = base[key]
            changed = True
            continue

        if key == "requirements":
            if "min_level" not in merged.get("requirements", {}):
                merged.setdefault("requirements", {})["min_level"] = 0
                changed = True

    if merged.get("id") is None:
        merged["id"] = base["id"]
        changed = True

    if not merged.get("name"):
        merged["name"] = base["name"]
        changed = True

    return merged, changed


def main():
    MAPS_DIR.mkdir(parents=True, exist_ok=True)

    created = []
    updated = []
    skipped = []
    seen_ids = set()

    for image_path in sorted(TEMPLATES_DIR.glob("*/maintenance/*_map_open_reference.png")):
        folder_name = normalize_legacy_folder(image_path.parent.parent.name)
        map_id = parse_map_id(image_path.name)

        if map_id in seen_ids:
            continue
        seen_ids.add(map_id)

        base = build_base_entry(map_id, folder_name, image_path)
        json_path = MAPS_DIR / f"{map_id}.json"

        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as file:
                existing = json.load(file)

            merged, changed = merge_entry(existing, base)

            if changed:
                with json_path.open("w", encoding="utf-8") as file:
                    json.dump(merged, file, indent=2)
                    file.write("\n")
                updated.append(map_id)
            else:
                skipped.append(map_id)
        else:
            with json_path.open("w", encoding="utf-8") as file:
                json.dump(base, file, indent=2)
                file.write("\n")
            created.append(map_id)

    print(f"JSON creados ({len(created)}):")
    for map_id in created:
        print(f"  - {map_id}.json")

    print(f"\nJSON actualizados ({len(updated)}):")
    for map_id in updated:
        print(f"  - {map_id}.json")

    print(f"\nJSON omitidos ({len(skipped)}):")
    for map_id in skipped:
        print(f"  - {map_id}.json")


if __name__ == "__main__":
    main()
