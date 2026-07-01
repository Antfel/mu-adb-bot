import os

LOW_SPEC_BOT_LOOP_DELAY_SECONDS = 6
DEFAULT_BOT_LOOP_DELAY_SECONDS = 3


def is_low_spec_enabled():
    return os.name == "nt"


def get_bot_loop_delay_seconds():
    if is_low_spec_enabled():
        return LOW_SPEC_BOT_LOOP_DELAY_SECONDS
    return DEFAULT_BOT_LOOP_DELAY_SECONDS
