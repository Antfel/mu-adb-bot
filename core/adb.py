import subprocess
import time
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


def _format_adb_command(command):
    return " ".join(str(part) for part in command)


def run_adb(args, capture_output=True):
    if not DEVICE_ID:
        raise RuntimeError("[ADB] No device selected")

    command = ["adb", "-s", DEVICE_ID] + args
    cmd_label = _format_adb_command(command)
    console = hidden_console_kwargs()
    start = time.monotonic()

    log(f"[ADB-CALL] cmd={cmd_label}")

    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=False,
            startupinfo=console["startupinfo"],
            creationflags=console["creationflags"],
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        log(
            f"[ADB-TIMEOUT] cmd={cmd_label} duration={duration:.2f}s"
        )
        raise RuntimeError(f"ADB timeout: {cmd_label}") from exc
    except OSError as exc:
        duration = time.monotonic() - start
        log(f"[ADB-ERROR] cmd={cmd_label} duration={duration:.2f}s error={exc}")
        raise RuntimeError(f"ADB error: {exc}") from exc

    duration = time.monotonic() - start
    log(f"[ADB-TIME] cmd={cmd_label} duration={duration:.2f}s")

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="ignore").strip()
        log(
            f"[ADB-ERROR] cmd={cmd_label} returncode={result.returncode} "
            f"stderr={error or 'none'}"
        )
        raise RuntimeError(f"ADB error: {error}")

    log(f"[ADB-OK] cmd={cmd_label}")
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
