from core.logger import log
from core.screen import get_screen
from core.vision import find_template


ELF_BUFF_ICON_TEMPLATE = "templates/ui/common/elf_buff_icon.png"
ELF_BUFF_THRESHOLD = 0.55


def has_elf_buff():
    screen = get_screen()
    match = find_template(
        screen,
        ELF_BUFF_ICON_TEMPLATE,
        threshold=ELF_BUFF_THRESHOLD,
    )

    if match is not None:
        log("[ELF] Buff active")
        return True

    log("[ELF] Buff not active")
    return False
