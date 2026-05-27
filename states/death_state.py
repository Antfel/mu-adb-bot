from core.screen import get_screen

from core.vision import find_template

def is_dead():

    screen = get_screen()

    match = find_template(

        screen,

        "templates/ui/dead_state.png",

        threshold=0.8

    )

    return match is not None