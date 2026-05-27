from core.screen import get_screen
from core.vision import find_template


def is_auto_mode():
    screen = get_screen()

    match = find_template(
        screen,
        "templates/ui/auto_text.png",
        threshold=0.8
    )

    return match is not None


def is_manual_mode():
    screen = get_screen()

    match = find_template(
        screen,
        "templates/ui/manual_mode.png",
        threshold=0.8
    )

    return match is not None

def get_manual_match():
    screen = get_screen()

    return find_template(
        screen,
        "templates/ui/manual_mode.png",
        threshold=0.8
    )