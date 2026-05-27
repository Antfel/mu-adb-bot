import subprocess
from pathlib import Path


DEVICE_ID = "127.0.0.1:5555"


def run_adb(args, capture_output=True):
    command = ["adb", "-s", DEVICE_ID] + args

    result = subprocess.run(
        command,
        capture_output=capture_output,
        text=False
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


def screenshot(path="screenshots/current.png"):
    Path("screenshots").mkdir(exist_ok=True)

    image_data = run_adb(["exec-out", "screencap", "-p"])

    with open(path, "wb") as f:
        f.write(image_data)

    return path


def swipe(x1, y1, x2, y2, duration=300):

    run_adb([
        "shell",
        "input",
        "swipe",
        str(x1),
        str(y1),
        str(x2),
        str(y2),
        str(duration)
    ], capture_output=False)