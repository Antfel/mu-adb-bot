import subprocess

from core.logger import log
from core.subprocess_utils import hidden_console_kwargs

_adb_server_ready = False


def _run_adb(args, *, check=False, binary=False):
    console = hidden_console_kwargs()
    try:
        return subprocess.run(
            ["adb", *args],
            capture_output=True,
            text=not binary,
            check=check,
            startupinfo=console["startupinfo"],
            creationflags=console["creationflags"],
        )
    except OSError:
        return None


def ensure_adb_server(force=False):
    global _adb_server_ready

    if _adb_server_ready and not force:
        return True

    log("[ADB] Starting server")
    result = _run_adb(["start-server"])
    if result is None:
        log("[ADB] adb command not found")
        _adb_server_ready = False
        return False

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        log(f"[ADB] start-server failed: {stderr or result.returncode}")
        _adb_server_ready = False
        return False

    _adb_server_ready = True
    log("[ADB] Server ready")
    return True


def restart_adb():
    global _adb_server_ready

    log("[ADB] Restarting server")
    _run_adb(["kill-server"])
    _adb_server_ready = False
    ensure_adb_server(force=True)


def list_adb_devices():
    global _adb_server_ready

    if not ensure_adb_server():
        return []

    result = _run_adb(["devices"])
    if result is None:
        _adb_server_ready = False
        return []

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        log(f"[ADB] devices failed: {stderr or result.returncode}")
        _adb_server_ready = False
        return []

    devices = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or line == "List of devices attached":
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        device_id, status = parts[0], parts[1]
        if status == "device":
            devices.append(device_id)

    return devices


def get_device_screenshot(device_id):
    if not device_id:
        return None

    if not ensure_adb_server():
        return None

    result = _run_adb(
        ["-s", device_id, "exec-out", "screencap", "-p"],
        binary=True,
    )
    if result is None:
        log("[ADB] Screenshot failed: adb command not found")
        return None

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace").strip()
        else:
            stderr = (stderr or "").strip()
        log(f"[ADB] Screenshot failed for {device_id}: {stderr or result.returncode}")
        return None

    png_bytes = result.stdout
    if not png_bytes:
        log(f"[ADB] Screenshot empty for {device_id}")
        return None

    return png_bytes
