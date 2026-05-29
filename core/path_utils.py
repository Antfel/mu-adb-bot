import shutil
import sys
from pathlib import Path


def is_frozen():
    return getattr(sys, "frozen", False)


def get_resource_root():
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_app_root():
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative_path):
    """Read-only bundled asset path (templates, navigation/maps)."""
    return str(get_resource_root() / relative_path)


def data_path(relative_path):
    """Writable directory path next to the app."""
    full = get_app_root() / relative_path
    full.mkdir(parents=True, exist_ok=True)
    return str(full)


def data_file_path(relative_path):
    """Writable file path next to the app; creates parent dirs only."""
    full = get_app_root() / relative_path
    full.parent.mkdir(parents=True, exist_ok=True)
    return str(full)


def ensure_runtime_data():
    """Seed writable data dirs from the bundle on first frozen launch."""
    if not is_frozen():
        return

    app_root = get_app_root()
    bundle_root = get_resource_root()

    for folder in ("profiles", "special_locations"):
        dest = app_root / folder
        if dest.exists():
            continue

        src = bundle_root / folder
        if src.exists():
            shutil.copytree(src, dest)

    (app_root / "debug").mkdir(parents=True, exist_ok=True)
