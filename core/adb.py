import subprocess
import threading
import time
from pathlib import Path

from core.logger import log
from core.subprocess_utils import hidden_console_kwargs

DEVICE_ID = None

_adb_lock = threading.Lock()
_screenshot_cache = None

TIMEOUT_TAP_SWIPE = 3
TIMEOUT_DEVICES = 5
TIMEOUT_SCREENCAP = 8
TIMEOUT_DEFAULT = 5


class AdbCompleted:
    def __init__(self, returncode, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout or b""
        self.stderr = stderr or b""


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


def clear_screenshot_cache():
    global _screenshot_cache
    _screenshot_cache = None


def begin_bot_screen_cycle():
    clear_screenshot_cache()


def get_screenshot_cache():
    return _screenshot_cache


def set_screenshot_cache(data):
    global _screenshot_cache
    _screenshot_cache = data


def _format_cmd(command):
    return " ".join(str(part) for part in command)


def _resolve_timeout(args, timeout=None):
    if timeout is not None:
        return timeout

    if not args:
        return TIMEOUT_DEFAULT

    if args[0] in ("devices", "start-server", "kill-server"):
        return TIMEOUT_DEVICES

    joined = " ".join(str(arg) for arg in args)
    if "screencap" in joined or "exec-out" in joined:
        return TIMEOUT_SCREENCAP

    if "input" in args:
        return TIMEOUT_TAP_SWIPE

    return TIMEOUT_DEFAULT


def _execute_adb(command, *, capture_output=True, timeout, raise_on_error=True):
    console = hidden_console_kwargs()
    start = time.monotonic()
    cmd_label = _format_cmd(command)

    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=False,
            timeout=timeout,
            startupinfo=console["startupinfo"],
            creationflags=console["creationflags"],
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        log(
            f"[ADB-TIMEOUT] cmd={cmd_label} timeout={timeout}s "
            f"duration={duration:.2f}s"
        )
        if exc.stdout:
            try:
                exc.stdout.close()
            except Exception:
                pass
        if exc.stderr:
            try:
                exc.stderr.close()
            except Exception:
                pass
        if raise_on_error:
            raise RuntimeError(f"ADB timeout after {timeout}s: {cmd_label}") from exc
        return AdbCompleted(124, b"", b"timeout")

    duration = time.monotonic() - start
    log(f"[ADB-TIME] cmd={cmd_label} duration={duration:.2f}s")

    stdout = result.stdout if capture_output else b""
    stderr = result.stderr if capture_output else b""

    if result.returncode != 0:
        error = (stderr or b"").decode("utf-8", errors="ignore").strip()
        if raise_on_error:
            raise RuntimeError(f"ADB error: {error or result.returncode}")
        return AdbCompleted(result.returncode, stdout, stderr)

    if raise_on_error:
        return stdout if capture_output else None
    return AdbCompleted(result.returncode, stdout, stderr)


def run_adb_raw(args, *, capture_output=True, timeout=None):
    """Run adb with global lock. Returns AdbCompleted on failure, bytes/None on success."""
    timeout = _resolve_timeout(args, timeout)
    command = ["adb", *args]
    try:
        with _adb_lock:
            return _execute_adb(
                command,
                capture_output=capture_output,
                timeout=timeout,
                raise_on_error=False,
            )
    except OSError:
        return None


def run_adb(args, capture_output=True, timeout=None):
    if not DEVICE_ID:
        raise RuntimeError("[ADB] No device selected")

    timeout = _resolve_timeout(args, timeout)
    command = ["adb", "-s", DEVICE_ID, *args]
    with _adb_lock:
        try:
            return _execute_adb(
                command,
                capture_output=capture_output,
                timeout=timeout,
                raise_on_error=True,
            )
        except OSError as exc:
            raise RuntimeError(f"ADB error: {exc}") from exc


def tap(x, y):
    run_adb(["shell", "input", "tap", str(x), str(y)], capture_output=False)
    clear_screenshot_cache()


def swipe(x1, y1, x2, y2, duration=500):
    run_adb([
        "shell", "input", "swipe",
        str(x1), str(y1),
        str(x2), str(y2),
        str(duration),
    ], capture_output=False)
    clear_screenshot_cache()


def keyevent(keycode):
    run_adb(["shell", "input", "keyevent", str(keycode)], capture_output=False)
    clear_screenshot_cache()


def press_back():
    keyevent(4)


def screenshot(path="screenshots/current.png"):
    Path("screenshots").mkdir(exist_ok=True)

    image_data = run_adb(["exec-out", "screencap", "-p"])
    set_screenshot_cache(image_data)

    with open(path, "wb") as f:
        f.write(image_data)

    return path
