from core.screen import get_screen
from core.vision import find_template


def is_inventory_open():
    screen = get_screen()

    match = find_template(
        screen,
        "templates/ui/inventory_open.png",
        threshold=0.8
    )

    return match is not None


def is_inventory_closed():
    return not is_inventory_open()