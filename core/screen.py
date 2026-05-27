import subprocess
import numpy as np
import cv2

DEVICE = "127.0.0.1:5555"


def get_screen():
    result = subprocess.run(
        ["adb", "-s", DEVICE, "exec-out", "screencap", "-p"],
        capture_output=True
    )

    image_bytes = result.stdout

    image_array = np.frombuffer(image_bytes, np.uint8)

    screen = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    return screen