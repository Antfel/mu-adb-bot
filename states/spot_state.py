from core.screen import get_screen
from core.vision import find_template
from core.profile import load_profile
from coordinates.spots import resolve_farm_target


def is_in_farm_spot():
    profile = load_profile()
    _, _, spot = resolve_farm_target(profile)

    validation_template = spot.get("spot_validation_template")
    if not validation_template:
        return True

    screen = get_screen()

    match = find_template(
        screen,
        validation_template,
        threshold=0.8,
    )

    return match is not None
