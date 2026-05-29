"""Runtime session flags for a single bot execution."""

session_character_level = None
session_elf_buff_enabled = False
session_elf_buff_status = "No configurado"


def reset_session():
    global session_character_level, session_elf_buff_enabled, session_elf_buff_status

    session_character_level = None
    session_elf_buff_enabled = False
    session_elf_buff_status = "No configurado"


def configure_session(character_level, elf_buff_enabled, elf_buff_status):
    global session_character_level, session_elf_buff_enabled, session_elf_buff_status

    session_character_level = character_level
    session_elf_buff_enabled = elf_buff_enabled
    session_elf_buff_status = elf_buff_status
