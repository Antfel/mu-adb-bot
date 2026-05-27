import time

from core.adb import tap, swipe
from core.screen import get_screen
from core.vision import find_template


def wait(seconds):
    time.sleep(seconds)


def tap_xy(x, y):
    tap(x, y)


def swipe_xy(x1, y1, x2, y2, duration=500):
    swipe(x1, y1, x2, y2, duration)


def exists_template(template_path, threshold=0.85):
    screen = get_screen()

    return find_template(
        screen,
        template_path,
        threshold=threshold
    )


def tap_template(template_path, threshold=0.85):
    match = exists_template(template_path, threshold)

    if not match:
        print(f"No se encontró template: {template_path}")
        return False

    print(f"Template encontrado: {template_path}")
    tap(match["center_x"], match["center_y"])
    return True


def wait_template(template_path, timeout=10, threshold=0.85):
    start = time.time()

    while time.time() - start < timeout:
        match = exists_template(template_path, threshold)

        if match:
            return match

        time.sleep(0.5)

    return None


def run_sequence(actions):
    for action in actions:
        action_type = action["type"]

        if action_type == "tap":
            tap_xy(action["x"], action["y"])

        elif action_type == "swipe":
            swipe_xy(
                action["x1"],
                action["y1"],
                action["x2"],
                action["y2"],
                action.get("duration", 500)
            )

        elif action_type == "wait":
            wait(action["seconds"])

        elif action_type == "tap_template":
            tap_template(
                action["template"],
                action.get("threshold", 0.85)
            )
        
        elif action_type == "ensure_auto_mode":
            from core.game_actions import ensure_auto_mode
            ensure_auto_mode()

        elif action["type"] == "find_and_tap_with_scroll":
            match = find_template_with_scroll(
                action["template"],
                action.get("threshold", 0.8)
            )

            if match:

                tap(
                    match["center_x"],
                    match["center_y"]
                )

                wait(1)

            else:

                print(
                    f"No se encontró: {action['template']}"
                )    

from core.adb import tap, swipe
import time


def wait(seconds):
    time.sleep(seconds)


def run_sequence(actions):

    for action in actions:

        if action["type"] == "tap":

            tap(
                action["x"],
                action["y"]
            )

        elif action["type"] == "swipe":

            swipe(
                action["x1"],
                action["y1"],
                action["x2"],
                action["y2"],
                action.get("duration", 300)
            )

        elif action["type"] == "wait":

            wait(action["seconds"])
        elif action["type"] == "ensure_auto_mode":
            from core.game_actions import ensure_auto_mode
            ensure_auto_mode()
