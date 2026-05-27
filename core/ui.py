from core.screen import get_screen
from core.vision import find_template
from core.adb import swipe
from core.actions import wait


def find_template_with_scroll(
    template,
    threshold=0.8,
    max_attempts=10,
    swipe_coords=None
):

    for attempt in range(max_attempts):

        screen = get_screen()

        match = find_template(
            screen,
            template,
            threshold=threshold
        )

        if match:

            print(f"[UI] Template encontrado: {template}")

            return match

        print(f"[UI] Template no encontrado. Scroll #{attempt + 1}")
        if swipe_coords:

            swipe(
                swipe_coords["x1"],
                swipe_coords["y1"],
                swipe_coords["x2"],
                swipe_coords["y2"],
                swipe_coords.get("duration",300)
            )

        wait(1)

    return None