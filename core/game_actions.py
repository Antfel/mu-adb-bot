from pathlib import Path

from core.logger import log
from core.adb import bind_adb_device
from core.actions import tap_template, tap_xy, wait
from core.screen import get_screen
from core.vision import find_template
from coordinates.ui import (
    CHAT_CLOSE_BUTTON_TEMPLATE,
    CHAT_OPEN_TEMPLATE,
    CLOSE_BUTTON,
    CLOSE_X_TEMPLATE,
)
from states.inventory_state import (
    is_inventory_open,
    is_inventory_closed
)


def clean_game_ui(device_id, max_close_attempts=3):
    try:
        bind_adb_device(device_id)
        log("[UI] Cleaning game UI")

        if Path(CLOSE_X_TEMPLATE).is_file():
            for attempt in range(max_close_attempts):
                screen = get_screen()
                match = find_template(screen, CLOSE_X_TEMPLATE, threshold=0.8)

                if not match:
                    break

                log(f"[UI] Closing window via X ({attempt + 1}/{max_close_attempts})")
                tap_xy(match["center_x"], match["center_y"])
                wait(0.5)
        else:
            log(f"[UI] Close X template missing: {CLOSE_X_TEMPLATE}")

        if Path(CHAT_OPEN_TEMPLATE).is_file():
            screen = get_screen()
            chat_open = find_template(screen, CHAT_OPEN_TEMPLATE, threshold=0.8)

            if chat_open:
                log("[UI] Chat abierto detectado")

                if Path(CHAT_CLOSE_BUTTON_TEMPLATE).is_file():
                    screen = get_screen()
                    close_button = find_template(
                        screen,
                        CHAT_CLOSE_BUTTON_TEMPLATE,
                        threshold=0.8,
                    )

                    if close_button:
                        tap_xy(close_button["center_x"], close_button["center_y"])
                        wait(0.5)
                        log("[UI] Chat cerrado")
                    else:
                        log("[UI] Botón cerrar chat no encontrado")
        else:
            log(f"[UI] Chat open template missing: {CHAT_OPEN_TEMPLATE}")

        ensure_inventory_closed()
        return True

    except Exception as e:
        log(f"[ERROR] clean_game_ui failed: {e}")
        return False


def open_inventory():
    return tap_template(
        "templates/ui/inventory.png",
        threshold=0.8
    )


def close_window():
    tap_xy(
        CLOSE_BUTTON["x"],
        CLOSE_BUTTON["y"]
    )


def close_inventory():
    if is_inventory_closed():
        log("[INVENTORY] Ya está cerrado")
        return True

    close_window()
    wait(1)

    return True


def ensure_inventory_open():
    if is_inventory_open():
        log("[INVENTORY] Ya abierto")
        return True

    log("[INVENTORY] Abriendo...")

    open_inventory()
    wait(1)

    return is_inventory_open()


def ensure_inventory_closed():
    if is_inventory_closed():
        log("[INVENTORY] Ya cerrado")
        return True

    log("[INVENTORY] Cerrando...")

    close_inventory()
    wait(1)

    return is_inventory_closed()


from states.combat_state import is_auto_mode, get_manual_match

def ensure_auto_mode():
    if is_auto_mode():
        log("[COMBAT] Auto ya activo")
        return True

    manual_match = get_manual_match()

    if manual_match:
        log("[COMBAT] Manual detectado. Activando auto...")
        tap_xy(manual_match["center_x"], manual_match["center_y"])
        wait(2)
        return is_auto_mode()

    log("[COMBAT] No se pudo detectar Auto/Manual")
    return False

from coordinates.gameplay import REVIVE_BUTTON
from states.death_state import is_dead


def revive_if_dead():
    if not is_dead():
        log("[DEATH] Personaje vivo")
        return True

    log("[DEATH] Personaje muerto. Reviviendo...")

    tap_xy(
        REVIVE_BUTTON["x"],
        REVIVE_BUTTON["y"]
    )

    wait(3)

    return not is_dead()

from states.potion_state import is_mana_potion_empty, is_potion_popup_open,is_hp_potion_empty
from core.vision import find_template
from core.screen import get_screen


def teleport_to_potion_store():
    hp_empty = is_hp_potion_empty()
    mp_empty = is_mana_potion_empty()

    if hp_empty:
        log("[POTION] Tocando HP agotada")
        tap_template("templates/ui/hp_potion_out.png", threshold=0.96)

    elif mp_empty:
        log("[POTION] Tocando Mana agotada")
        tap_template("templates/ui/mana_potion_out.png", threshold=0.96)

    else:
        log("[POTION] No hay pociones agotadas")
        return False

    wait(1)

    if not is_potion_popup_open():
        log("[POTION] No apareció popup de teleport")
        return False

    screen = get_screen()

    teleport = find_template(
        screen,
        "templates/ui/potion_teleport_button.png",
        threshold=0.8
    )

    if not teleport:
        log("[POTION] Botón teleport no encontrado")
        return False

    log("[POTION] Teleport a tienda")

    tap_xy(
        teleport["center_x"],
        teleport["center_y"]
    )

    wait(5)

    return True


from coordinates.gameplay import HP_POTION_PURCHASE, MP_POTION_PURCHASE


def buy_potions(hp_amount=1, mp_amount=1):

    log(f"[POTION] Buying HP x{hp_amount}")

    for _ in range(hp_amount):
        tap_xy(
            HP_POTION_PURCHASE["x"],
            HP_POTION_PURCHASE["y"]
        )

        wait(0.4)

        # segundo tap para cerrar animación
        tap_xy(
            HP_POTION_PURCHASE["x"],
            HP_POTION_PURCHASE["y"]
        )

        wait(0.6)

    log(f"[POTION] Buying MP x{mp_amount}")

    for _ in range(mp_amount):
        tap_xy(
            MP_POTION_PURCHASE["x"],
            MP_POTION_PURCHASE["y"]
        )

        wait(0.4)

        tap_xy(
            MP_POTION_PURCHASE["x"],
            MP_POTION_PURCHASE["y"]
        )

        wait(0.6)

    return True