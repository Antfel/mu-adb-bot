import subprocess


def list_adb_devices():
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
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

    try:
        result = subprocess.run(
            ["adb", "-s", device_id, "exec-out", "screencap", "-p"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None

    if result.returncode != 0 or not result.stdout:
        return None

    return result.stdout

