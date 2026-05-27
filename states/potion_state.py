from core.screen import get_screen
from core.vision import find_template


def is_mana_potion_empty():
    screen = get_screen()

    match = find_template(
        screen,
        "templates/ui/mana_potion_out.png",
        threshold=0.96
    )

    return match is not None

def is_hp_potion_empty():
    screen = get_screen()

    match = find_template(
        screen,
        "templates/ui/hp_potion_out.png",
        threshold=0.96
    )

    return match is not None


def is_any_potion_empty():
    return is_mana_potion_empty() or is_hp_potion_empty()

def is_potion_popup_open():
    screen = get_screen()

    match = find_template(
        screen,
        "templates/ui/potion_clue_popup.png",
        threshold=0.8
    )

    return match is not None