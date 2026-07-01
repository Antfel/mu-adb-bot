import io
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from core.path_utils import ensure_runtime_data
from core.profile import (
    BOT_MODE_LABEL_BY_VALUE,
    bot_mode_from_label,
    get_available_bot_mode_labels,
    get_profile_display_name,
    list_profiles_with_display_names,
    load_profile,
    normalize_profile_data,
    save_profile,
    set_current_profile,
)
from core.character_level import read_character_level
from core.level_validation import parse_character_level, validate_level_for_profile
import core.session_state as session_state
from core.session_state import configure_session, reset_session, set_current_bot_state
from core.logger import log
from core.adb import get_device, set_device
from core.screen import begin_bot_screen_cycle
from core.device_manager import get_device_screenshot, list_adb_devices, restart_adb
from core.game_actions import clean_game_ui, ensure_auto_mode
from core.window_utils import center_window
from core.actions import wait
from states.death_state import is_dead
from states.potion_state import is_any_potion_empty
from states.recovery_state import recover_if_dead
from states.purchase_potions_state import handle_empty_potions
from states.farming import run_farming_state
from states.map_state import is_in_configured_map
from states.navigation_state import go_to_active_farm_spot
from states.elf_buff_check_state import has_elf_buff
from states.elf_buff_state import go_to_elf_buff_and_return
from states.pre_navigation_state import run_pre_navigation_checks
from profile_ui import open_profile_manager, set_profile_manager_close_callback
from core.ui_theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_PINK,
    ACCENT_PURPLE,
    COMBO_WIDTH,
    FONTS,
    LABEL_GAP,
    PAD_PANEL,
    PAD_ROW,
    PAD_WINDOW,
    PANEL_BG,
    PANEL_BORDER,
    PREVIEW_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    UI_BG,
    configure_window,
    create_dialog_panel,
    create_combobox,
    create_entry,
    create_form_label,
    create_primary_button,
    create_section_frame,
    setup_theme,
    ui_label,
)


WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 640
PREVIEW_WIDTH = 460
PREVIEW_HEIGHT = 260
PREVIEW_BTN_WIDTH = 320
COMBO_WIDTH = 32
SPOT_MODAL_WIDTH = 420
SPOT_MODAL_HEIGHT = 200

STATUS_CONFIG = {
    "idle": ("#6b7280", "Detenido"),
    "working": ("#f97316", "Navegando"),
    "farming": ("#22c55e", "Farming"),
    "error": ("#ef4444", "Error"),
}

bot_running = False
startup_already_at_spot = False
_preview_photo = None
preview_refresh_job = None
_preview_in_progress = False
PREVIEW_REFRESH_INTERVAL_MS = 2000 if os.name == "nt" else 1500
_current_bot_status = "idle"

# Widget refs set during layout build
root = None
device_var = None
profile_var = None
profile_display_var = None
filename_to_display_name = {}
display_name_to_filename = {}
device_select = None
profile_select = None
bot_type_var = None
bot_type_select = None
level_var = None
toggle_button = None
preview_label = None
traffic_canvas = None
status_text_label = None
runtime_status_value = None
runtime_device_value = None
runtime_profile_value = None
runtime_bot_mode_value = None
runtime_level_value = None
runtime_elf_buff_value = None
last_event_label = None


def _labeled_combo(parent, label_text, row, textvariable, values=None):
    """Label + Combobox only (not for buttons)."""
    create_form_label(
        parent,
        label_text,
        row=row,
        column=0,
        sticky="w",
        pady=(0, LABEL_GAP),
    )
    return create_combobox(
        parent,
        textvariable,
        values=values,
        width=COMBO_WIDTH,
        row=row + 1,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )


def _runtime_row(parent, icon, label_text, row):
    row_frame = tk.Frame(parent, bg=PANEL_BG)
    row_frame.grid(row=row, column=0, sticky="ew", pady=4)
    row_frame.grid_columnconfigure(1, weight=1)

    ui_label(row_frame, icon, font=FONTS["icon"], width=2).grid(
        row=0, column=0, sticky="w"
    )
    ui_label(
        row_frame,
        label_text,
        font=FONTS["body_bold"],
        fg=TEXT_SECONDARY,
    ).grid(row=0, column=1, sticky="w", padx=(4, 8))

    value = ui_label(row_frame, "-", font=FONTS["body_bold"])
    value.grid(row=0, column=2, sticky="e")
    return value


def add_log(message):
    log(message)

    def _update_last_event():
        text = message if len(message) <= 64 else f"{message[:61]}..."
        last_event_label.config(text=text)
        refresh_runtime_status()

    if threading.current_thread() is threading.main_thread():
        _update_last_event()
    else:
        root.after(0, _update_last_event)


def _active_device_id():
    device_id = get_device() or device_var.get().strip()
    if not device_id:
        log("[ADB] No device selected")
    return device_id


def _apply_toggle_stopped():
    toggle_button.config(text="▶ Iniciar Bot")


def _apply_toggle_running():
    toggle_button.config(text="■ Detener Bot")


def _handle_startup_failure():
    global bot_running

    bot_running = False
    cancel_preview_refresh()

    def _reset_ui():
        reset_session()
        refresh_runtime_status()
        _apply_toggle_stopped()
        set_bot_status("error")

    if threading.current_thread() is threading.main_thread():
        _reset_ui()
    else:
        root.after(0, _reset_ui)


def run_startup_sequence(device_id, already_at_spot):
    """Validaciones previas y navegación opcional antes del loop principal."""
    global startup_already_at_spot

    startup_already_at_spot = already_at_spot

    if already_at_spot:
        set_current_bot_state("FARMING")
        set_bot_status("farming")
        log("[STARTUP] User confirmed already at spot; state set to FARMING")
    else:
        set_bot_status("working")

    add_log("[BOT] Secuencia de inicio")

    if is_dead():
        add_log("[MAIN] Personaje muerto")
        if not recover_if_dead(device_id):
            log("[MAIN] Recuperación falló")
            return False

    checks_ok, navigated_to_farm = run_pre_navigation_checks(device_id)
    if not checks_ok:
        log("[MAIN] Validaciones pre-navegación fallaron")
        return False

    need_navigation = not already_at_spot and not navigated_to_farm
    if need_navigation:
        add_log("[MAIN] Navegando al farm spot")
        if not navigate_with_retry():
            set_bot_status("error")
            log("[BOT] Startup failed: could not reach farm spot")
            return False

    if not ensure_auto_mode():
        log("[MAIN] No se pudo activar auto attack")
        return False

    add_log("[BOT] Inicio completado")
    return True


def navigate_with_retry():
    device_id = _active_device_id()
    if not device_id:
        return False

    if go_to_active_farm_spot(device_id):
        return True

    set_bot_status("working")
    log("[MAIN] Navegación falló. Limpiando UI y reintentando")
    clean_game_ui(device_id)

    if go_to_active_farm_spot(device_id):
        return True

    set_bot_status("error")
    return False


def _profile_path(profile_name):
    if not profile_name:
        return None
    from core.path_utils import data_file_path

    name = profile_name if profile_name.endswith(".json") else f"{profile_name}.json"
    return data_file_path(f"profiles/{name}")


def _load_level_from_profile(profile_name=None):
    profile_name = profile_name or profile_var.get()
    path = _profile_path(profile_name)
    if not path:
        level_var.set("")
        return

    try:
        profile_data = load_profile(path)
        level = profile_data.get("character_level")
        level_var.set(str(level) if level is not None else "")
    except (OSError, ValueError, TypeError):
        level_var.set("")


def _save_character_level_to_profile(profile_name, character_level):
    path = _profile_path(profile_name)
    if not path:
        return

    profile_data = load_profile(path)
    profile_data["character_level"] = character_level
    save_profile(profile_data, path)


def _apply_character_level_ui(level):
    """Update level field and runtime label; safe from worker threads."""

    def _apply():
        level_var.set(str(level))
        if runtime_level_value is not None:
            runtime_level_value.config(text=str(level))
        session_state.session_character_level = level

    if root is None:
        return

    if threading.current_thread() is threading.main_thread():
        _apply()
    else:
        root.after(0, _apply)


def _resolve_character_level(selected_device):
    auto_level = read_character_level(selected_device)
    if auto_level is not None:
        _apply_character_level_ui(auto_level)
        refresh_runtime_status()
        log("[LEVEL] Using OCR level (priority over manual)")
        return auto_level

    manual_level = parse_character_level(level_var.get())
    if manual_level is not None:
        log("[LEVEL] OCR failed, using manual level fallback")
        return manual_level

    log("[LEVEL] OCR failed, no manual level configured")
    return None


def _validate_and_prepare_session(profile_name, selected_device):
    reset_session()

    character_level = _resolve_character_level(selected_device)
    if character_level is None:
        messagebox.showerror(
            "Nivel del personaje",
            "Debes configurar el nivel del personaje antes de iniciar el bot.",
        )
        return False

    _save_character_level_to_profile(profile_name, character_level)

    try:
        validation = validate_level_for_profile(profile_name, character_level)
    except FileNotFoundError as exc:
        messagebox.showerror("Mapa no encontrado", str(exc))
        log(f"[LEVEL] {exc}")
        return False

    if not validation.can_start:
        messagebox.showerror("Nivel insuficiente", validation.farm_blocked_message)
        return False

    if validation.show_elf_warning:
        messagebox.showwarning(
            "Elf Buff",
            "Se desactiva el uso de buscar Elf Buff, debido a que el personaje "
            "no puede ingresar a dicho mapa",
        )

    configure_session(
        character_level,
        validation.elf_buff_enabled,
        validation.elf_buff_status,
    )
    refresh_runtime_status()
    return True


def refresh_profile_options(select_filename=None):
    global filename_to_display_name, display_name_to_filename

    if profile_select is None or root is None:
        log("[UI] profile_select not ready; skipping refresh_profile_options")
        return

    try:
        if not root.winfo_exists():
            return
    except tk.TclError:
        return

    data = list_profiles_with_display_names()
    filename_to_display_name = data["filename_to_display_name"]
    display_name_to_filename = data["display_name_to_filename"]
    display_names = data["display_names"]

    profile_select["values"] = display_names

    if not display_names:
        profile_var.set("")
        if profile_display_var is not None:
            profile_display_var.set("")
        return

    current_filename = (select_filename or profile_var.get() or "").strip()
    if current_filename not in filename_to_display_name:
        current_filename = data["entries"][0]["filename"]

    profile_var.set(current_filename)
    profile_display_var.set(filename_to_display_name[current_filename])
    refresh_bot_type_options(current_filename)
    refresh_runtime_status()


def _schedule_main_profile_refresh(select_filename=None, delay_ms=0):
    if root is None:
        return

    try:
        if not root.winfo_exists():
            return
    except tk.TclError:
        return

    def _apply_refresh():
        try:
            if not root.winfo_exists():
                return
        except tk.TclError:
            return
        refresh_profile_options(select_filename)

    try:
        root.after(delay_ms, _apply_refresh)
    except tk.TclError:
        pass


def refresh_bot_type_options(profile_filename=None):
    if bot_type_select is None or bot_type_var is None:
        return

    profile_filename = (profile_filename or profile_var.get() or "").strip()
    if not profile_filename:
        bot_type_select["values"] = []
        bot_type_var.set("")
        return

    try:
        profile_data = load_profile(f"profiles/{profile_filename}")
    except (FileNotFoundError, OSError, ValueError):
        bot_type_select["values"] = []
        bot_type_var.set("")
        return

    labels = get_available_bot_mode_labels(profile_filename=profile_filename)
    farm_enabled = profile_data.get("farm_config", {}).get("enabled")
    kill_enabled = profile_data.get("kill_bosses_config", {}).get("enabled")
    log(f"[PROFILE] farm_config.enabled = {farm_enabled}")
    log(f"[PROFILE] kill_bosses_config.enabled = {kill_enabled}")
    log(f"[PROFILE] available bot modes = {labels}")

    bot_type_select["values"] = labels

    if not labels:
        bot_type_var.set("")
        return

    normalized = normalize_profile_data(profile_data, profile_filename)
    preferred_mode = normalized.get("bot_mode", "farm")
    preferred_label = BOT_MODE_LABEL_BY_VALUE.get(preferred_mode)

    if len(labels) == 1:
        bot_type_var.set(labels[0])
    elif preferred_label in labels:
        bot_type_var.set(preferred_label)
    else:
        bot_type_var.set(labels[0])


def _get_selected_bot_mode():
    if bot_type_var is None:
        return "farm"
    return bot_mode_from_label(bot_type_var.get())


def refresh_runtime_status():
    device = device_var.get().strip() or "-"
    profile_file = profile_var.get().strip()
    if profile_file:
        profile = filename_to_display_name.get(profile_file) or get_profile_display_name(
            profile_file
        )
    else:
        profile = "-"
    runtime_device_value.config(text=device)
    runtime_profile_value.config(text=profile)

    bot_mode_label = bot_type_var.get().strip() if bot_type_var is not None else ""
    runtime_bot_mode_value.config(text=bot_mode_label or "-")

    session_level = session_state.session_character_level
    if session_level is not None:
        runtime_level_value.config(text=str(session_level))
    else:
        parsed = parse_character_level(level_var.get())
        runtime_level_value.config(text=str(parsed) if parsed is not None else "-")

    if session_level is not None:
        elf_status = session_state.session_elf_buff_status
    else:
        profile_name = profile_var.get()
        preview_level = parse_character_level(level_var.get())
        if profile_name and preview_level is not None:
            try:
                preview = validate_level_for_profile(profile_name, preview_level)
                elf_status = preview.elf_buff_status
            except FileNotFoundError:
                elf_status = "-"
        else:
            elf_status = "No configurado"

    runtime_elf_buff_value.config(text=elf_status)

    color, text = STATUS_CONFIG.get(_current_bot_status, STATUS_CONFIG["idle"])
    runtime_status_value.config(text=text, fg=color)


def _sync_session_bot_state(ui_state):
    mapping = {
        "idle": "IDLE",
        "working": "NAVIGATING",
        "farming": "FARMING",
        "error": "ERROR",
    }
    set_current_bot_state(mapping.get(ui_state, "IDLE"))


def set_bot_status(state):
    global _current_bot_status
    _current_bot_status = state
    _sync_session_bot_state(state)

    def _apply():
        color, text = STATUS_CONFIG.get(state, STATUS_CONFIG["idle"])
        traffic_canvas.delete("all")
        traffic_canvas.create_oval(6, 6, 46, 46, fill=color, outline=PANEL_BORDER, width=2)
        status_text_label.config(text=text, fg=color)
        refresh_runtime_status()

    if threading.current_thread() is threading.main_thread():
        _apply()
    else:
        root.after(0, _apply)


def bot_loop():
    global bot_running

    while bot_running:
        begin_bot_screen_cycle()
        try:
            if is_dead():
                set_bot_status("working")
                add_log("[MAIN] Personaje muerto")
                device_id = _active_device_id()
                if not device_id:
                    set_bot_status("error")
                elif not recover_if_dead(device_id):
                    log("[MAIN] Recuperación falló")
                    set_bot_status("error")
                else:
                    checks_ok, navigated_to_farm = run_pre_navigation_checks(device_id)
                    if not checks_ok:
                        log("[MAIN] Validaciones post-muerte fallaron")
                        set_bot_status("error")
                    elif not navigated_to_farm:
                        add_log("[MAIN] Volviendo al spot tras revive")
                        if not navigate_with_retry():
                            log("[MAIN] Navegación al spot falló")
                            set_bot_status("error")
                        elif not ensure_auto_mode():
                            set_bot_status("error")
                    elif not ensure_auto_mode():
                        set_bot_status("error")

            elif is_any_potion_empty():
                set_bot_status("working")
                add_log("[MAIN] Pociones agotadas")
                device_id = _active_device_id()
                if not device_id:
                    set_bot_status("error")
                elif not handle_empty_potions(device_id):
                    log("[MAIN] Compra de pociones falló")
                    set_bot_status("error")

            elif session_state.session_elf_buff_enabled and not has_elf_buff():
                set_bot_status("working")
                add_log("[MAIN] Elf buff no activo. Buscando buff")
                device_id = _active_device_id()
                if not device_id:
                    set_bot_status("error")
                elif not go_to_elf_buff_and_return(device_id):
                    set_bot_status("error")
                    add_log("[MAIN] Falló búsqueda de elf buff")

            else:
                if not is_in_configured_map():
                    set_bot_status("working")
                    add_log("[MAIN] Mapa incorrecto. Volviendo al spot")
                    if not navigate_with_retry():
                        log("[MAIN] Navegación al spot falló")
                        set_bot_status("error")
                else:
                    if run_farming_state():
                        set_bot_status("farming")
                    else:
                        add_log("[MAIN] Farming falló")
                        set_bot_status("error")

        except Exception as e:
            log(f"[ERROR] {e}")
            set_bot_status("error")

        wait(3)

    if not bot_running:
        root.after(0, lambda: set_bot_status("idle"))
        add_log("[BOT] Detenido")


def _show_spot_confirm_modal():
    dialog = tk.Toplevel(root)
    dialog.title("Confirmación")
    configure_window(dialog, bg=PANEL_BG)
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()
    center_window(dialog, SPOT_MODAL_WIDTH, SPOT_MODAL_HEIGHT)

    result = {"value": None}

    def close_dialog(value=None):
        result["value"] = value
        dialog.grab_release()
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", lambda: close_dialog(None))

    content = create_dialog_panel(dialog)
    content.pack(fill="both", expand=True)

    ui_label(
        content,
        "¿Ya te encuentras en el spot?",
        font=FONTS["body_bold"],
        bg=PANEL_BG,
    ).pack(pady=(0, 18))

    actions = tk.Frame(content, bg=PANEL_BG)
    actions.pack()
    actions.grid_columnconfigure(0, weight=1)
    actions.grid_columnconfigure(1, weight=1)

    create_primary_button(actions, "Sí", lambda: close_dialog(True)).grid(
        row=0, column=0, sticky="ew", padx=(0, 8)
    )
    create_primary_button(actions, "No", lambda: close_dialog(False)).grid(
        row=0, column=1, sticky="ew", padx=(8, 0)
    )

    dialog.wait_window()

    if result["value"] is None:
        return

    _begin_bot(already_at_spot=result["value"])


def _begin_bot(already_at_spot):
    global bot_running

    if bot_running:
        return

    selected_profile = profile_var.get()
    selected_device = device_var.get().strip()

    if selected_profile:
        set_current_profile(selected_profile)
        add_log(f"[PROFILE] Perfil activo: {selected_profile}")

    if not selected_device:
        log("[DEVICE] Ningún dispositivo seleccionado")
        return

    set_device(selected_device)
    log(f"[DEVICE] Usando dispositivo: {selected_device}")

    if not selected_profile:
        messagebox.showerror("Perfil", "Seleccione un perfil antes de iniciar el bot.")
        return

    selected_bot_mode = _get_selected_bot_mode()
    if not selected_bot_mode:
        messagebox.showerror(
            "Tipo Bot",
            "Seleccione un tipo de bot antes de iniciar.",
        )
        return

    try:
        profile_for_start = normalize_profile_data(
            load_profile(f"profiles/{selected_profile}"),
            selected_profile,
        )
    except (FileNotFoundError, OSError):
        messagebox.showerror("Perfil", "No se pudo cargar el perfil seleccionado.")
        return

    profile_for_start["bot_mode"] = selected_bot_mode
    save_profile(profile_for_start, f"profiles/{selected_profile}")
    refresh_bot_type_options(selected_profile)

    if not _validate_and_prepare_session(selected_profile, selected_device):
        return

    if selected_bot_mode == "kill_bosses":
        messagebox.showinfo(
            "Kill Bosses",
            "El modo Kill Bosses aún no está implementado.",
        )
        return

    bot_running = True
    _apply_toggle_running()
    add_log("[BOT] Iniciado")

    threading.Thread(target=_bot_worker, args=(already_at_spot,), daemon=True).start()

    cancel_preview_refresh()
    schedule_preview_refresh()


def _bot_worker(already_at_spot):
    try:
        device_id = _active_device_id()
        if not device_id:
            _handle_startup_failure()
            return

        if not run_startup_sequence(device_id, already_at_spot):
            _handle_startup_failure()
            return

        bot_loop()
    except Exception as e:
        log(f"[ERROR] {e}")
        _handle_startup_failure()


def toggle_bot():
    if bot_running:
        stop_bot()
    else:
        _show_spot_confirm_modal()


def stop_bot():
    global bot_running

    bot_running = False
    cancel_preview_refresh()

    _apply_toggle_stopped()
    reset_session()
    refresh_runtime_status()
    set_bot_status("idle")
    add_log("[BOT] Detenido")


def _show_no_preview():
    global _preview_photo
    _preview_photo = None
    preview_label.config(image="", text="No preview", bg=PREVIEW_BG, fg=TEXT_SECONDARY)


def _apply_preview(png_bytes):
    global _preview_photo

    if not png_bytes:
        _show_no_preview()
        return

    try:
        img = Image.open(io.BytesIO(png_bytes))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")

        img.thumbnail((PREVIEW_WIDTH, PREVIEW_HEIGHT), Image.Resampling.LANCZOS)

        canvas_img = Image.new("RGB", (PREVIEW_WIDTH, PREVIEW_HEIGHT), PREVIEW_BG)
        offset_x = (PREVIEW_WIDTH - img.width) // 2
        offset_y = (PREVIEW_HEIGHT - img.height) // 2

        if img.mode == "RGBA":
            canvas_img.paste(img, (offset_x, offset_y), img)
        else:
            canvas_img.paste(img, (offset_x, offset_y))

        _preview_photo = ImageTk.PhotoImage(canvas_img)
        preview_label.config(image=_preview_photo, text="", bg=PREVIEW_BG)
    except Exception:
        _show_no_preview()


def update_device_preview():
    global _preview_in_progress

    device_id = device_var.get().strip()
    if not device_id:
        _show_no_preview()
        return

    if _preview_in_progress:
        return

    def worker():
        global _preview_in_progress
        try:
            png_bytes = get_device_screenshot(device_id)
            root.after(0, lambda: _apply_preview(png_bytes))
        finally:
            _preview_in_progress = False

    _preview_in_progress = True
    threading.Thread(target=worker, daemon=True).start()


def cancel_preview_refresh():
    global preview_refresh_job

    if preview_refresh_job is not None:
        root.after_cancel(preview_refresh_job)
        preview_refresh_job = None


def schedule_preview_refresh():
    global preview_refresh_job

    if not bot_running:
        return

    update_device_preview()
    preview_refresh_job = root.after(
        PREVIEW_REFRESH_INTERVAL_MS,
        schedule_preview_refresh,
    )


def restart_adb_devices():
    restart_adb()
    refresh_devices()


def refresh_devices():
    if device_select is None:
        log("[UI] device_select not ready; skipping refresh_devices")
        return

    devices = list_adb_devices()
    device_select["values"] = devices

    if not devices:
        device_var.set("")
        log("[DEVICE] No hay dispositivos ADB disponibles")
        _show_no_preview()
        refresh_runtime_status()
        return

    if len(devices) == 1:
        device_var.set(devices[0])
    elif device_var.get() not in devices:
        device_var.set(devices[0])

    update_device_preview()
    refresh_runtime_status()


def _on_profile_selected(_event=None):
    display = profile_display_var.get().strip()
    filename = display_name_to_filename.get(display)
    if filename:
        profile_var.set(filename)
    _load_level_from_profile()
    refresh_bot_type_options()
    refresh_runtime_status()


def _on_bot_type_selected(_event=None):
    refresh_runtime_status()


def _on_level_changed(_event=None):
    if bot_running:
        return

    profile_name = profile_var.get()
    character_level = parse_character_level(level_var.get())
    if profile_name and character_level is not None:
        _save_character_level_to_profile(profile_name, character_level)
    session_state.session_character_level = None
    refresh_runtime_status()


def _on_device_selected(_event=None):
    update_device_preview()
    refresh_runtime_status()


def _build_ui():
    global root, device_var, device_select, profile_var, profile_display_var, profile_select
    global bot_type_var, bot_type_select
    global filename_to_display_name, display_name_to_filename
    global level_var, toggle_button, preview_label, traffic_canvas, status_text_label
    global runtime_status_value, runtime_device_value, runtime_profile_value
    global runtime_bot_mode_value, runtime_level_value, runtime_elf_buff_value
    global last_event_label

    root = tk.Tk()
    root.title("MU Immortal Bot")
    configure_window(root)
    root.resizable(False, False)
    center_window(root, WINDOW_WIDTH, WINDOW_HEIGHT)
    setup_theme(root)

    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=0)

    # --- Header ---
    header = tk.Frame(root, bg=UI_BG)
    header.grid(row=0, column=0, sticky="ew", padx=PAD_WINDOW, pady=(12, 6))
    header.grid_columnconfigure(1, weight=1)

    logo_canvas = tk.Canvas(
        header,
        width=44,
        height=44,
        bg=UI_BG,
        highlightthickness=0,
    )
    logo_canvas.grid(row=0, column=0, sticky="w")
    logo_canvas.create_rectangle(4, 4, 40, 40, fill=ACCENT_BLUE, outline="")
    logo_canvas.create_text(22, 22, text="MU", fill="white", font=FONTS["logo"])

    title_block = tk.Frame(header, bg=UI_BG)
    title_block.grid(row=0, column=1, sticky="w", padx=(12, 0))
    ui_label(title_block, "MU Immortal Bot", font=FONTS["title"], bg=UI_BG).pack(anchor="w")

    status_block = tk.Frame(header, bg=UI_BG)
    status_block.grid(row=0, column=2, sticky="e")

    traffic_canvas = tk.Canvas(
        status_block,
        width=52,
        height=52,
        bg=UI_BG,
        highlightthickness=0,
    )
    traffic_canvas.pack(side=tk.LEFT, padx=(0, 10))

    status_text_label = ui_label(
        status_block,
        "Detenido",
        font=FONTS["status"],
        fg=TEXT_SECONDARY,
        bg=UI_BG,
    )
    status_text_label.pack(side=tk.LEFT)

    # --- Main 3-column grid ---
    main = tk.Frame(root, bg=UI_BG)
    main.grid(row=1, column=0, sticky="n", padx=PAD_WINDOW, pady=(0, 6))
    main.grid_columnconfigure(0, weight=0, minsize=272)
    main.grid_columnconfigure(1, weight=0, minsize=PREVIEW_WIDTH + 48)
    main.grid_columnconfigure(2, weight=0, minsize=272)
    main.grid_rowconfigure(0, weight=0)

    # Column 1: Device / Profile
    device_body = create_section_frame(
        main, "DEVICE / PROFILE", "🖥", row=0, column=0, sticky="n", accent=ACCENT_BLUE
    )
    device_body.grid_columnconfigure(0, weight=1, minsize=248)

    device_var = tk.StringVar()
    device_select = _labeled_combo(device_body, "Dispositivo", 0, device_var)

    device_btn_row = tk.Frame(device_body, bg=PANEL_BG)
    device_btn_row.grid(row=2, column=0, sticky="ew", pady=(0, PAD_ROW))
    device_btn_row.grid_columnconfigure(0, weight=1)
    device_btn_row.grid_columnconfigure(1, weight=0)

    create_primary_button(
        device_btn_row,
        "↻  Refrescar dispositivos",
        refresh_devices,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

    create_primary_button(
        device_btn_row,
        "Reiniciar ADB",
        restart_adb_devices,
    ).grid(row=0, column=1, sticky="e")

    profile_var = tk.StringVar()
    profile_display_var = tk.StringVar()
    create_form_label(
        device_body,
        "Perfil",
        row=3,
        column=0,
        sticky="w",
        pady=(0, LABEL_GAP),
    )
    profile_select = create_combobox(
        device_body,
        profile_display_var,
        values=[],
        width=COMBO_WIDTH,
        row=4,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )

    bot_type_var = tk.StringVar()
    create_form_label(
        device_body,
        "Tipo Bot",
        row=5,
        column=0,
        sticky="w",
        pady=(0, LABEL_GAP),
    )
    bot_type_select = create_combobox(
        device_body,
        bot_type_var,
        values=[],
        width=COMBO_WIDTH,
        row=6,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )

    create_form_label(
        device_body,
        "Nivel PJ",
        row=7,
        column=0,
        sticky="w",
        pady=(0, LABEL_GAP),
    )
    level_var = tk.StringVar()
    level_entry = create_entry(
        device_body,
        textvariable=level_var,
        width=12,
        row=8,
        column=0,
        sticky="w",
        pady=(0, 10),
    )
    level_entry.bind("<FocusOut>", _on_level_changed)
    level_entry.bind("<Return>", _on_level_changed)

    bot_actions = tk.Frame(device_body, bg=PANEL_BG)
    bot_actions.grid(row=9, column=0, sticky="ew")
    bot_actions.grid_columnconfigure(0, weight=1)

    toggle_button = create_primary_button(
        bot_actions,
        "▶ Iniciar Bot",
        toggle_bot,
        style="Toggle.TButton",
    )
    toggle_button.grid(row=0, column=0, sticky="ew")

    # Column 2: Live Preview
    preview_body = create_section_frame(
        main, "LIVE PREVIEW", "👁", row=0, column=1, sticky="n", accent=ACCENT_PURPLE
    )
    preview_body.grid_columnconfigure(0, weight=1)

    preview_center = tk.Frame(preview_body, bg=PANEL_BG)
    preview_center.grid(row=0, column=0)
    preview_center.grid_columnconfigure(0, weight=1)

    preview_frame = tk.Frame(
        preview_center,
        width=PREVIEW_WIDTH,
        height=PREVIEW_HEIGHT,
        bg=PREVIEW_BG,
        highlightthickness=1,
        highlightbackground=PANEL_BORDER,
    )
    preview_frame.grid(row=0, column=0)
    preview_frame.grid_propagate(False)

    preview_label = tk.Label(
        preview_frame,
        text="No preview",
        bg=PREVIEW_BG,
        fg=TEXT_SECONDARY,
        font=FONTS["body"],
    )
    preview_label.place(relx=0.5, rely=0.5, anchor="center")

    preview_btn_padx = max(0, (PREVIEW_WIDTH - PREVIEW_BTN_WIDTH) // 2)
    preview_btn_wrap = tk.Frame(preview_center, bg=PANEL_BG, width=PREVIEW_BTN_WIDTH)
    preview_btn_wrap.grid(row=1, column=0, pady=(8, 0), padx=preview_btn_padx)
    preview_btn_wrap.grid_propagate(False)
    create_primary_button(
        preview_btn_wrap,
        "↻  Actualizar preview",
        update_device_preview,
    ).pack(fill="x")

    # Column 3: Runtime Status
    runtime_body = create_section_frame(
        main, "RUNTIME STATUS", "♥", row=0, column=2, sticky="n", accent=ACCENT_GREEN
    )
    runtime_body.grid_columnconfigure(0, weight=1)

    runtime_status_value = _runtime_row(runtime_body, "●", "Estado", 0)
    runtime_device_value = _runtime_row(runtime_body, "🖥", "Dispositivo", 1)
    runtime_profile_value = _runtime_row(runtime_body, "👤", "Perfil", 2)
    runtime_bot_mode_value = _runtime_row(runtime_body, "⚙", "Tipo bot", 3)
    runtime_level_value = _runtime_row(runtime_body, "⬆", "Nivel PJ", 4)
    runtime_elf_buff_value = _runtime_row(runtime_body, "🍃", "Elf Buff", 5)

    event_frame = tk.Frame(runtime_body, bg=PANEL_BG)
    event_frame.grid(row=6, column=0, sticky="ew", pady=4)
    ui_label(event_frame, "🕐", font=FONTS["icon"], width=2).grid(
        row=0, column=0, sticky="nw"
    )
    ui_label(
        event_frame,
        "Último evento",
        font=FONTS["body_bold"],
        fg=TEXT_SECONDARY,
    ).grid(row=0, column=1, sticky="nw", padx=(4, 0))
    last_event_label = ui_label(
        event_frame,
        "-",
        font=FONTS["body"],
        fg=TEXT_SECONDARY,
        wraplength=200,
        justify="left",
    )
    last_event_label.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(4, 0))

    # --- Configuration panel ---
    config_outer = tk.Frame(root, bg=PANEL_BORDER)
    config_outer.grid(row=2, column=0, sticky="ew", padx=PAD_WINDOW, pady=(0, 14))

    config_inner = tk.Frame(config_outer, bg=PANEL_BG)
    config_inner.pack(fill="x", padx=1, pady=1)

    config_header = tk.Frame(config_inner, bg=PANEL_BG)
    config_header.pack(fill="x", padx=PAD_PANEL, pady=(10, 6))
    ui_label(config_header, "⚙", font=FONTS["icon"], fg=ACCENT_PINK).pack(side="left")
    ui_label(
        config_header,
        "CONFIGURACIÓN",
        font=FONTS["section"],
        fg=TEXT_SECONDARY,
    ).pack(side="left", padx=(8, 0))

    config_actions = tk.Frame(config_inner, bg=PANEL_BG)
    config_actions.pack(fill="x", padx=PAD_PANEL, pady=(0, 10))
    config_actions.grid_columnconfigure(0, weight=1)

    create_primary_button(
        config_actions,
        "👥  Administrar perfiles",
        lambda: open_profile_manager(root),
    ).grid(row=0, column=0, sticky="ew", ipady=6)

    device_select.bind("<<ComboboxSelected>>", _on_device_selected)
    profile_select.bind("<<ComboboxSelected>>", _on_profile_selected)
    bot_type_select.bind("<<ComboboxSelected>>", _on_bot_type_selected)
    set_profile_manager_close_callback(_schedule_main_profile_refresh)
    _load_level_from_profile()


def _start_app():
    ensure_runtime_data()
    _build_ui()
    set_bot_status("idle")
    refresh_profile_options()
    refresh_devices()
    refresh_runtime_status()
    root.mainloop()


_start_app()
