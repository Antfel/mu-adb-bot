import subprocess
from pathlib import Path

from core.logger import log
from core.subprocess_utils import hidden_console_kwargs


DEVICE_ID = None


def set_device(device_id):
    global DEVICE_ID
    DEVICE_ID = device_id


def get_device():
    return DEVICE_ID


def bind_adb_device(device_id):
    if not device_id or not str(device_id).strip():
        raise RuntimeError("[ADB] No device selected")
    device_id = str(device_id).strip()
    set_device(device_id)
    log(f"[ADB] Using device: {device_id}")
    return device_id


def run_adb(args, capture_output=True):
    if not DEVICE_ID:
        raise RuntimeError("[ADB] No device selected")

    command = ["adb", "-s", DEVICE_ID] + args
    console = hidden_console_kwargs()

    result = subprocess.run(
        command,
        capture_output=capture_output,
        text=False,
        startupinfo=console["startupinfo"],
        creationflags=console["creationflags"],
    )

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"ADB error: {error}")

    return result.stdout


def tap(x, y):
    run_adb(["shell", "input", "tap", str(x), str(y)], capture_output=False)


def swipe(x1, y1, x2, y2, duration=500):
    run_adb([
        "shell", "input", "swipe",
        str(x1), str(y1),
        str(x2), str(y2),
        str(duration)
    ], capture_output=False)


def keyevent(keycode):
    run_adb(["shell", "input", "keyevent", str(keycode)], capture_output=False)


def press_back():
    keyevent(4)


def screenshot(path="screenshots/current.png"):
    Path("screenshots").mkdir(exist_ok=True)

    image_data = run_adb(["exec-out", "screencap", "-p"])

    with open(path, "wb") as f:
        f.write(image_data)

    return path