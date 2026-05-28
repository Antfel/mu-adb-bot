from core.adb import run_adb
from core.vision import decode_image_bytes


def get_screen():
    image_bytes = run_adb(["exec-out", "screencap", "-p"])
    return decode_image_bytes(image_bytes)