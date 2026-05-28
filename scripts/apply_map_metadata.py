#!/usr/bin/env python3
"""One-shot metadata migration: order, min_level, legacy renames."""

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = ROOT / "navigation" / "maps"
TEMPLATES_DIR = ROOT / "templates" / "maps"

# Official order, canonical group display name, min_level
GROUP_CATALOG = [
    (1, "VIP Domain", 40),
    (2, "Lorencia", 1),
    (3, "Noria", 1),
    (4, "Elbeland", 1),
    (5, "Devias", 20),
    (6, "Dungeon", 30),
    (7, "Lost Tower", 40),
    (8, "Atlans", 60),
    (9, "Tarkan", 100),
    (10, "Aida", 150),
    (11, "Icarus", 170),
    (12, "Kanturu Ruins", 200),
    (13, "Kanturu Relics", 250),
    (14, "Raklion", 300),
    (15, "Divine Realm", 300),
    (16, "High Heaven", 300),
    (17, "Purgatory of Misery", 300),
    (18, "Endless Abyss", 300),
    (19, "Corridor of Agony", 300),
    (20, "Swamp of Peace", 350),
    (21, "Temple of Kalima", 350),
    (22, "Plain of Four Winds", 400),
    (23, "Corrupted Lands", 450),
    (24, "Land of Demons", 450),
    (25, "Eversong Forest", 500),
    (26, "Foggy Forest", 500),
    (27, "Ferea", 550),
    (28, "Abyssal Ferea", 550),
    (29, "Nixies Lake", 600),
    (30, "Dissimilated Nixies Lake", 600),
    (31, "Swamp of Darkness", 700),
    (32, "Swamp of Abyss", 700),
]

GROUP_LOOKUP = {name.lower(): (order, name, min_level) for order, name, min_level in GROUP_CATALOG}
GROUP_LOOKUP["rakion"] = GROUP_LOOKUP["raklion"]

LEGACY_GROUP_ALIASES = {
    "purgatory of misery": "purgatory of misery",
    "corridor of agony": "corridor of agony",
    "swamp of peace": "swamp of peace",
    "temple of kalima": "temple of kalima",
}


def normalize_group_key(group):
    return (group or "").strip().lower()


def resolve_group_meta(group):
    key = normalize_group_key(group)
    if key in GROUP_LOOKUP:
        return GROUP_LOOKUP[key]
    return None


def display_name(map_id, canonical_group, submap):
    if re.search(r"_\d+$", map_id):
        return f"{canonical_group} {submap}"
    return canonical_group


def fix_map_id_legacy(map_id):
    if map_id.startswith("rakion_"):
        return "raklion_" + map_id[len("rakion_") :]
    if map_id.startswith("pain_of_four_winds"):
        return "plain_of_four_winds" + map_id[len("pain_of_four_winds") :]
    return map_id


def fix_path_legacy(path):
    if not path:
        return path
    path = path.replace("/Rakion/", "/Raklion/")
    path = path.replace("/Pain_of_four_winds/", "/Plain_of_four_winds/")
    path = path.replace("rakion_", "raklion_")
    path = path.replace("pain_of_four_winds", "plain_of_four_winds")
    return path


def rename_legacy_assets():
    renamed = []

    rakion_dir = TEMPLATES_DIR / "Rakion"
    raklion_dir = TEMPLATES_DIR / "Raklion"
    if rakion_dir.exists() and not raklion_dir.exists():
        shutil.move(str(rakion_dir), str(raklion_dir))
        renamed.append(f"folder: Rakion -> Raklion")

    if raklion_dir.exists():
        for png in sorted(raklion_dir.rglob("rakion_*")):
            target = png.with_name(png.name.replace("rakion_", "raklion_", 1))
            if png != target:
                shutil.move(str(png), str(target))
                renamed.append(f"png: {png.name} -> {target.name}")

    pain_dir = TEMPLATES_DIR / "Pain_of_four_winds"
    plain_dir = TEMPLATES_DIR / "Plain_of_four_winds"
    if pain_dir.exists() and not plain_dir.exists():
        shutil.move(str(pain_dir), str(plain_dir))
        renamed.append("folder: Pain_of_four_winds -> Plain_of_four_winds")

    if plain_dir.exists():
        for png in sorted(plain_dir.rglob("pain_of_four_winds*")):
            target = png.with_name(png.name.replace("pain_of_four_winds", "plain_of_four_winds", 1))
            if png != target:
                shutil.move(str(png), str(target))
                renamed.append(f"png: {png.name} -> {target.name}")

    for old_id in ("rakion_1", "rakion_2", "rakion_3"):
        old_path = MAPS_DIR / f"{old_id}.json"
        new_id = fix_map_id_legacy(old_id)
        new_path = MAPS_DIR / f"{new_id}.json"
        if old_path.exists():
            with old_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            data["id"] = new_id
            data["group"] = "Raklion"
            data["name"] = display_name(new_id, "Raklion", data.get("submap", 1))
            maint = data.get("maintenance", {})
            if maint.get("map_ui_image"):
                maint["map_ui_image"] = fix_path_legacy(maint["map_ui_image"])
            data["maintenance"] = maint
            with new_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            if new_path != old_path:
                old_path.unlink()
            renamed.append(f"json: {old_id}.json -> {new_id}.json")

    return renamed


def update_json_metadata():
    updated = []
    missing_group = []
    ids_seen = {}

    for path in sorted(MAPS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        map_id = fix_map_id_legacy(data.get("id") or path.stem)
        if map_id != data.get("id"):
            data["id"] = map_id

        group = data.get("group", "")
        meta = resolve_group_meta(group)
        if meta is None:
            meta = resolve_group_meta(fix_map_id_legacy(group))
        if meta is None:
            missing_group.append((path.name, group))
            continue

        order, canonical_group, min_level = meta
        submap = data.get("submap", 1)

        data["group"] = canonical_group
        data["name"] = display_name(map_id, canonical_group, submap)
        data["order"] = order
        data.setdefault("requirements", {})["min_level"] = min_level

        if "maintenance" in data and data["maintenance"].get("map_ui_image"):
            data["maintenance"]["map_ui_image"] = fix_path_legacy(
                data["maintenance"]["map_ui_image"]
            )

        if "navigation" in data:
            nav = data["navigation"]
            for key in nav:
                if isinstance(nav[key], str) and nav[key].startswith("templates/"):
                    nav[key] = fix_path_legacy(nav[key])

        new_path = MAPS_DIR / f"{map_id}.json"
        with new_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        if new_path != path and path.exists():
            path.unlink()

        if map_id in ids_seen:
            ids_seen[map_id].append(str(new_path))
        else:
            ids_seen[map_id] = [str(new_path)]

        updated.append(path.name if new_path == path else f"{path.name} -> {new_path.name}")

    dupes = {k: v for k, v in ids_seen.items() if len(v) > 1}
    return updated, missing_group, dupes


def audit():
    no_min = []
    no_order = []
    for path in sorted(MAPS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        req = data.get("requirements") or {}
        if "min_level" not in req:
            no_min.append(path.name)
        if "order" not in data:
            no_order.append(path.name)
    return no_min, no_order


def main():
    renamed = rename_legacy_assets()
    updated, missing_group, dupes = update_json_metadata()
    no_min, no_order = audit()

    print("Archivos renombrados:")
    for item in renamed:
        print(f"  - {item}")

    print(f"\nJSON actualizados ({len(updated)}):")
    for item in updated:
        print(f"  - {item}")

    if missing_group:
        print("\nMapas sin metadata de grupo (revisar group):")
        for name, group in missing_group:
            print(f"  - {name}: group={group!r}")

    if dupes:
        print("\nIDs duplicados:")
        for map_id, paths in dupes.items():
            print(f"  - {map_id}: {paths}")

    print("\nMapas sin min_level:")
    print(f"  {no_min or '(ninguno)'}")

    print("\nMapas sin order:")
    print(f"  {no_order or '(ninguno)'}")


if __name__ == "__main__":
    main()
