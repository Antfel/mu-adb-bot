from core.logger import log
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
            log(
                f"[NAV] template={template} confidence={match['confidence']:.3f} "
                f"threshold={threshold} found=True scroll_attempt={attempt + 1}"
            )
            return match

        log(
            f"[NAV] template={template} threshold={threshold} "
            f"found=False scroll_attempt={attempt + 1}/{max_attempts}"
        )
        if swipe_coords:
            log(
                f"[NAV] scroll from ({swipe_coords['x1']},{swipe_coords['y1']}) "
                f"to ({swipe_coords['x2']},{swipe_coords['y2']})"
            )
            swipe(
                swipe_coords["x1"],
                swipe_coords["y1"],
                swipe_coords["x2"],
                swipe_coords["y2"],
                swipe_coords.get("duration",300)
            )

        wait(1)

    log(f"[NAV] template={template} not found after {max_attempts} scroll attempts")
    return None
