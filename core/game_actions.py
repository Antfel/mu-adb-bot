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


SHOP_OPEN_TEMPLATE = "templates/ui/common/shop_open.png"
POTION_CLUE_POPUP_TEMPLATE = "templates/ui/potion_clue_popup.png"
POTION_TELEPORT_BUTTON_TEMPLATE = "templates/ui/potion_teleport_button.png"
SHOP_OPEN_THRESHOLD = 0.50
TELEPORT_POPUP_THRESHOLD = 0.8
SHOP_CANDIDATE_LOG_THRESHOLD = 0.50


def _shop_open_search_region(screen):
    screen_h, screen_w = screen.shape[:2]
    half_w = screen_w // 2
    return {
        "x": half_w,
        "y": 0,
        "width": screen_w - half_w,
        "height": screen_h,
    }


def tap_empty_potion_slot():
    hp_empty = is_hp_potion_empty()
    mp_empty = is_mana_potion_empty()

    if hp_empty:
        log("[POTION] Tocando HP agotada")
        return tap_template("templates/ui/hp_potion_out.png", threshold=0.96)

    if mp_empty:
        log("[POTION] Tocando Mana agotada")
        return tap_template("templates/ui/mana_potion_out.png", threshold=0.96)

    log("[POTION] No hay pociones agotadas")
    return False


def is_shop_open():
    screen = get_screen()
    region = _shop_open_search_region(screen)
    return (
        find_template(
            screen,
            SHOP_OPEN_TEMPLATE,
            threshold=SHOP_OPEN_THRESHOLD,
            region=region,
        )
        is not None
    )


def _save_potion_entry_debug(screen, best_shop_match=None):
    import cv2

    from core.path_utils import get_app_root

    debug_dir = get_app_root() / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    if screen is not None:
        cv2.imwrite(str(debug_dir / "potion_entry_unknown.png"), screen)

    if screen is None or best_shop_match is None:
        return

    x = best_shop_match["x"]
    y = best_shop_match["y"]
    w = best_shop_match["width"]
    h = best_shop_match["height"]
    screen_h, screen_w = screen.shape[:2]

    pad = 20
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(screen_w, x + w + pad)
    y2 = min(screen_h, y + h + pad)
    crop = screen[y1:y2, x1:x2]

    if crop.size > 0:
        cv2.imwrite(str(debug_dir / "shop_open_check.png"), crop)


def wait_for_shop_open(timeout=10, poll_interval=0.5):
    import time

    start = time.time()
    while time.time() - start < timeout:
        if is_shop_open():
            return True
        wait(poll_interval)

    return False


def wait_for_potion_entry_result(device_id=None, timeout=8, poll_interval=0.5):
    import time

    from core.vision import probe_template

    _ = device_id
    start = time.time()
    max_teleport_conf = 0.0
    max_shop_conf = 0.0
    best_shop_match = None
    last_screen = None

    while time.time() - start < timeout:
        screen = get_screen()
        last_screen = screen

        shop_region = _shop_open_search_region(screen)
        teleport_conf, _ = probe_template(screen, POTION_CLUE_POPUP_TEMPLATE)
        shop_conf, shop_match = probe_template(
            screen, SHOP_OPEN_TEMPLATE, region=shop_region
        )

        max_teleport_conf = max(max_teleport_conf, teleport_conf)
        if shop_conf >= max_shop_conf:
            max_shop_conf = shop_conf
            best_shop_match = shop_match

        log(
            f"[POTION] Poll confidence teleport_popup={teleport_conf:.3f} "
            f"shop_open={shop_conf:.3f}"
        )

        if (
            SHOP_CANDIDATE_LOG_THRESHOLD <= shop_conf < SHOP_OPEN_THRESHOLD
        ):
            log(
                f"[POTION] Shop candidate detected but below threshold: "
                f"{shop_conf:.3f}"
            )

        if teleport_conf >= TELEPORT_POPUP_THRESHOLD:
            log(
                f"[POTION] Teleport popup detected "
                f"(confidence={teleport_conf:.3f})"
            )
            return "teleport_popup"

        if shop_conf >= SHOP_OPEN_THRESHOLD:
            log(
                f"[POTION] Shop opened directly "
                f"(confidence={shop_conf:.3f})"
            )
            return "shop_open"

        wait(poll_interval)

    log(
        f"[POTION] Unable to determine potion entry flow "
        f"(max teleport_popup={max_teleport_conf:.3f}, "
        f"max shop_open={max_shop_conf:.3f})"
    )
    log(f"[POTION] Max shop_open confidence: {max_shop_conf:.3f}")
    _save_potion_entry_debug(last_screen, best_shop_match)
    return None


def accept_potion_teleport_popup():
    if not is_potion_popup_open():
        log("[POTION] No apareció popup de teleport")
        return False

    screen = get_screen()
    teleport = find_template(
        screen,
        POTION_TELEPORT_BUTTON_TEMPLATE,
        threshold=0.8,
    )

    if not teleport:
        log("[POTION] Botón teleport no encontrado")
        return False

    log("[POTION] Teleport a tienda")
    tap_xy(teleport["center_x"], teleport["center_y"])
    wait(5)
    return True


def teleport_to_potion_store():
    if not tap_empty_potion_slot():
        return False

    wait(1)
    entry = wait_for_potion_entry_result()

    if entry is None:
        return False

    if entry == "teleport_popup":
        if not accept_potion_teleport_popup():
            return False
        return wait_for_shop_open(timeout=10)

    if entry == "shop_open":
        return True

    return False


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