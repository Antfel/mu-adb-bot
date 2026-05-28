import io
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from core.profile import list_profiles, set_current_profile
from core.logger import log
from core.adb import get_device, set_device
from core.device_manager import get_device_screenshot, list_adb_devices
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


# --- Visual constants ---
COLORS = {
    "bg": "#0b0c10",
    "panel": "#161b22",
    "panel_alt": "#1c2128",
    "border": "#30363d",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent_blue": "#3b82f6",
    "accent_purple": "#a855f7",
    "accent_green": "#22c55e",
    "accent_orange": "#f97316",
    "accent_pink": "#ec4899",
    "btn_start": "#2563eb",
    "btn_start_hover": "#1d4ed8",
    "btn_stop": "#dc2626",
    "btn_stop_hover": "#b91c1c",
    "btn_light": "#f0f3f6",
    "btn_light_hover": "#dce1e8",
    "btn_light_text": "#1a1f26",
    "btn_disabled_bg": "#2d333b",
    "btn_disabled_fg": "#8b949e",
    "btn_action_disabled_bg": "#2d333b",
    "input": "#0d1117",
    "preview_bg": "#0d1117",
}

FONTS = {
    "title": ("Segoe UI", 22, "bold"),
    "section": ("Segoe UI", 11, "bold"),
    "body": ("Segoe UI", 10),
    "body_bold": ("Segoe UI", 10, "bold"),
    "button": ("Segoe UI", 10, "bold"),
    "status": ("Segoe UI", 14, "bold"),
    "icon": ("Segoe UI", 14),
    "logo": ("Segoe UI", 16, "bold"),
}

PAD = {
    "window": 16,
    "panel": 12,
    "row": 6,
}

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
_current_bot_status = "idle"

# Widget refs set during layout build
root = None
device_var = None
profile_var = None
device_select = None
profile_select = None
toggle_button = None
preview_label = None
traffic_canvas = None
status_text_label = None
runtime_status_value = None
runtime_device_value = None
runtime_profile_value = None
last_event_label = None


def _setup_theme():
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        "Dark.TCombobox",
        fieldbackground=COLORS["input"],
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", COLORS["input"])],
        foreground=[("readonly", COLORS["text"])],
    )


def _label(parent, text, font=None, fg=None, bg=None, **kwargs):
    return tk.Label(
        parent,
        text=text,
        font=font or FONTS["body"],
        fg=fg or COLORS["text"],
        bg=bg or COLORS["panel"],
        **kwargs,
    )


def _labeled_combo(parent, label_text, row, textvariable, values=None):
    """Label + Combobox only (not for buttons)."""
    _label(parent, label_text, fg=COLORS["muted"]).grid(
        row=row, column=0, sticky="w", pady=(0, 3)
    )
    combo = ttk.Combobox(
        parent,
        textvariable=textvariable,
        values=values or [],
        state="readonly",
        width=COMBO_WIDTH,
        style="Dark.TCombobox",
    )
    combo.grid(row=row + 1, column=0, sticky="ew", pady=(0, PAD["row"]))
    return combo


def _light_button(parent, text, command, width=None):
    opts = {
        "text": text,
        "command": command,
        "font": FONTS["button"],
        "bg": COLORS["btn_light"],
        "fg": COLORS["btn_light_text"],
        "activebackground": COLORS["btn_light_hover"],
        "activeforeground": COLORS["btn_light_text"],
        "disabledforeground": COLORS["btn_disabled_fg"],
        "relief": "flat",
        "bd": 0,
        "padx": 12,
        "pady": 8,
        "cursor": "hand2",
    }
    if width:
        opts["width"] = width
    return tk.Button(parent, **opts)


def _set_bot_action_state(button, enabled, *, active_bg, active_hover):
    """macOS ignores custom bg on disabled tk.Button; toggle colors manually."""
    button._bot_enabled = enabled
    if enabled:
        button.config(
            bg=active_bg,
            fg="white",
            activebackground=active_hover,
            activeforeground="white",
            cursor="hand2",
        )
    else:
        button.config(
            bg=COLORS["btn_action_disabled_bg"],
            fg=COLORS["btn_disabled_fg"],
            activebackground=COLORS["btn_action_disabled_bg"],
            activeforeground=COLORS["btn_disabled_fg"],
            cursor="arrow",
        )


def _bot_action_button(parent, text, command, *, active_bg, active_hover, enabled=True):
    state = {"enabled": enabled}

    def on_click():
        if state["enabled"]:
            command()

    button = tk.Button(
        parent,
        text=text,
        command=on_click,
        font=FONTS["button"],
        relief="flat",
        bd=0,
        pady=9,
        highlightthickness=0,
    )
    button._active_bg = active_bg
    button._active_hover = active_hover

    def set_enabled(value):
        state["enabled"] = value
        _set_bot_action_state(
            button, value, active_bg=active_bg, active_hover=active_hover
        )

    button.set_enabled = set_enabled
    set_enabled(enabled)
    return button


def _create_panel(
    parent, title, icon, row, column, columnspan=1, sticky="nsew", accent=None
):
    outer = tk.Frame(parent, bg=COLORS["border"])
    outer.grid(
        row=row,
        column=column,
        columnspan=columnspan,
        sticky=sticky,
        padx=(0 if column == 0 else 6, 0),
        pady=0,
    )

    inner = tk.Frame(outer, bg=COLORS["panel"])
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    header = tk.Frame(inner, bg=COLORS["panel"])
    header.pack(fill="x", padx=PAD["panel"], pady=(10, 6))

    _label(header, icon, font=FONTS["icon"], fg=accent or COLORS["accent_blue"]).pack(
        side="left"
    )
    _label(
        header,
        title,
        font=FONTS["section"],
        fg=COLORS["muted"],
    ).pack(side="left", padx=(8, 0))

    body = tk.Frame(inner, bg=COLORS["panel"])
    body.pack(fill="x", padx=PAD["panel"], pady=(0, 10))
    return body


def _runtime_row(parent, icon, label_text, row):
    row_frame = tk.Frame(parent, bg=COLORS["panel"])
    row_frame.grid(row=row, column=0, sticky="ew", pady=4)
    row_frame.grid_columnconfigure(1, weight=1)

    _label(row_frame, icon, font=FONTS["icon"], width=2).grid(row=0, column=0, sticky="w")
    _label(
        row_frame,
        label_text,
        font=FONTS["body_bold"],
        fg=COLORS["muted"],
    ).grid(row=0, column=1, sticky="w", padx=(4, 8))

    value = _label(row_frame, "-", font=FONTS["body_bold"])
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
    toggle_button.config(text="▶  Iniciar Bot")
    _set_bot_action_state(
        toggle_button,
        True,
        active_bg=COLORS["btn_start"],
        active_hover=COLORS["btn_start_hover"],
    )


def _apply_toggle_running():
    toggle_button.config(text="■  Detener Bot")
    _set_bot_action_state(
        toggle_button,
        True,
        active_bg=COLORS["btn_stop"],
        active_hover=COLORS["btn_stop_hover"],
    )


def _handle_startup_failure():
    global bot_running

    bot_running = False
    cancel_preview_refresh()

    def _reset_ui():
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
    set_bot_status("working")
    add_log("[BOT] Secuencia de inicio")

    if is_dead():
        add_log("[MAIN] Personaje muerto")
        if not recover_if_dead(device_id):
            log("[MAIN] Recuperación falló")
            return False

    if is_any_potion_empty():
        add_log("[MAIN] Pociones agotadas")
        if not handle_empty_potions(device_id):
            log("[MAIN] Compra de pociones falló")
            return False

    navigated_via_elf = False
    if not has_elf_buff():
        add_log("[MAIN] Elf buff no activo. Buscando buff")
        if not go_to_elf_buff_and_return(device_id):
            log("[MAIN] Falló búsqueda de elf buff")
            return False
        navigated_via_elf = True

    need_navigation = not already_at_spot and not navigated_via_elf
    if need_navigation:
        add_log("[MAIN] Navegando al farm spot")
        if not navigate_with_retry():
            log("[MAIN] Navegación al spot falló")
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


def refresh_runtime_status():
    device = device_var.get().strip() or "-"
    profile = profile_var.get().strip() or "-"
    runtime_device_value.config(text=device)
    runtime_profile_value.config(text=profile)
    color, text = STATUS_CONFIG.get(_current_bot_status, STATUS_CONFIG["idle"])
    runtime_status_value.config(text=text, fg=color)


def set_bot_status(state):
    global _current_bot_status
    _current_bot_status = state

    def _apply():
        color, text = STATUS_CONFIG.get(state, STATUS_CONFIG["idle"])
        traffic_canvas.delete("all")
        traffic_canvas.create_oval(6, 6, 46, 46, fill=color, outline=COLORS["border"], width=2)
        status_text_label.config(text=text, fg=color)
        refresh_runtime_status()

    if threading.current_thread() is threading.main_thread():
        _apply()
    else:
        root.after(0, _apply)


def bot_loop():
    global bot_running

    while bot_running:
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

            elif is_any_potion_empty():
                set_bot_status("working")
                add_log("[MAIN] Pociones agotadas")
                device_id = _active_device_id()
                if not device_id:
                    set_bot_status("error")
                elif not handle_empty_potions(device_id):
                    log("[MAIN] Compra de pociones falló")
                    set_bot_status("error")

            elif not has_elf_buff():
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
    dialog.configure(bg=COLORS["panel"])
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

    content = tk.Frame(dialog, bg=COLORS["panel"], padx=24, pady=20)
    content.pack(fill="both", expand=True)

    _label(
        content,
        "¿Ya te encuentras en el spot?",
        font=FONTS["body_bold"],
    ).pack(pady=(0, 18))

    actions = tk.Frame(content, bg=COLORS["panel"])
    actions.pack()
    actions.grid_columnconfigure(0, weight=1)
    actions.grid_columnconfigure(1, weight=1)

    _light_button(actions, "Sí", lambda: close_dialog(True)).grid(
        row=0, column=0, sticky="ew", padx=(0, 8)
    )
    _light_button(actions, "No", lambda: close_dialog(False)).grid(
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
    set_bot_status("idle")
    add_log("[BOT] Detenido")


def open_profile_manager():
    import profile_ui


def open_farm_spot_config():
    profile_name = profile_var.get()
    if not profile_name:
        log("[PROFILE] Seleccione un perfil primero")
        return
    import location_selector_ui

    location_selector_ui.open_location_selector("farm_spot", profile_name)


def open_elf_buff_config():
    profile_name = profile_var.get()
    if not profile_name:
        log("[PROFILE] Seleccione un perfil primero")
        return
    import location_selector_ui

    location_selector_ui.open_location_selector("elf_buff", profile_name)


def _show_no_preview():
    global _preview_photo
    _preview_photo = None
    preview_label.config(image="", text="No preview", bg=COLORS["preview_bg"], fg=COLORS["muted"])


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

        canvas_img = Image.new("RGB", (PREVIEW_WIDTH, PREVIEW_HEIGHT), COLORS["preview_bg"])
        offset_x = (PREVIEW_WIDTH - img.width) // 2
        offset_y = (PREVIEW_HEIGHT - img.height) // 2

        if img.mode == "RGBA":
            canvas_img.paste(img, (offset_x, offset_y), img)
        else:
            canvas_img.paste(img, (offset_x, offset_y))

        _preview_photo = ImageTk.PhotoImage(canvas_img)
        preview_label.config(image=_preview_photo, text="", bg=COLORS["preview_bg"])
    except Exception:
        _show_no_preview()


def update_device_preview():
    device_id = device_var.get().strip()
    if not device_id:
        _show_no_preview()
        return

    def worker():
        png_bytes = get_device_screenshot(device_id)
        root.after(0, lambda: _apply_preview(png_bytes))

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
    preview_refresh_job = root.after(2000, schedule_preview_refresh)


def refresh_devices():
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
    refresh_runtime_status()


def _on_device_selected(_event=None):
    update_device_preview()
    refresh_runtime_status()


def _build_ui():
    global root, device_var, profile_var, device_select, profile_select
    global toggle_button, preview_label, traffic_canvas, status_text_label
    global runtime_status_value, runtime_device_value, runtime_profile_value, last_event_label

    root = tk.Tk()
    root.title("MU Immortal Bot")
    root.configure(bg=COLORS["bg"])
    root.resizable(False, False)
    center_window(root, WINDOW_WIDTH, WINDOW_HEIGHT)
    _setup_theme()

    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=0)

    # --- Header ---
    header = tk.Frame(root, bg=COLORS["bg"])
    header.grid(row=0, column=0, sticky="ew", padx=PAD["window"], pady=(12, 6))
    header.grid_columnconfigure(1, weight=1)

    logo_canvas = tk.Canvas(
        header,
        width=44,
        height=44,
        bg=COLORS["bg"],
        highlightthickness=0,
    )
    logo_canvas.grid(row=0, column=0, sticky="w")
    logo_canvas.create_rectangle(4, 4, 40, 40, fill=COLORS["accent_blue"], outline="")
    logo_canvas.create_text(22, 22, text="MU", fill="white", font=FONTS["logo"])

    title_block = tk.Frame(header, bg=COLORS["bg"])
    title_block.grid(row=0, column=1, sticky="w", padx=(12, 0))
    _label(title_block, "MU Immortal Bot", font=FONTS["title"]).pack(anchor="w")

    status_block = tk.Frame(header, bg=COLORS["bg"])
    status_block.grid(row=0, column=2, sticky="e")

    traffic_canvas = tk.Canvas(
        status_block,
        width=52,
        height=52,
        bg=COLORS["bg"],
        highlightthickness=0,
    )
    traffic_canvas.pack(side=tk.LEFT, padx=(0, 10))

    status_text_label = _label(
        status_block,
        "Detenido",
        font=FONTS["status"],
        fg=COLORS["muted"],
        bg=COLORS["bg"],
    )
    status_text_label.pack(side=tk.LEFT)

    # --- Main 3-column grid ---
    main = tk.Frame(root, bg=COLORS["bg"])
    main.grid(row=1, column=0, sticky="n", padx=PAD["window"], pady=(0, 6))
    main.grid_columnconfigure(0, weight=0, minsize=272)
    main.grid_columnconfigure(1, weight=0, minsize=PREVIEW_WIDTH + 48)
    main.grid_columnconfigure(2, weight=0, minsize=272)
    main.grid_rowconfigure(0, weight=0)

    # Column 1: Device / Profile
    device_body = _create_panel(
        main, "DEVICE / PROFILE", "🖥", row=0, column=0, sticky="n", accent=COLORS["accent_blue"]
    )
    device_body.grid_columnconfigure(0, weight=1, minsize=248)

    device_var = tk.StringVar()
    device_select = _labeled_combo(device_body, "Dispositivo", 0, device_var)

    _light_button(
        device_body,
        "↻  Refrescar dispositivos",
        refresh_devices,
    ).grid(row=2, column=0, sticky="ew", pady=(0, PAD["row"]))

    profiles = list_profiles()
    profile_var = tk.StringVar()
    profile_select = _labeled_combo(device_body, "Perfil", 3, profile_var, values=profiles)
    profile_select.grid_configure(pady=(0, 10))
    if profiles:
        profile_select.current(0)

    bot_actions = tk.Frame(device_body, bg=COLORS["panel"])
    bot_actions.grid(row=5, column=0, sticky="ew")
    bot_actions.grid_columnconfigure(0, weight=1)

    toggle_button = _bot_action_button(
        bot_actions,
        "▶  Iniciar Bot",
        toggle_bot,
        active_bg=COLORS["btn_start"],
        active_hover=COLORS["btn_start_hover"],
        enabled=True,
    )
    toggle_button.grid(row=0, column=0, sticky="ew")

    # Column 2: Live Preview
    preview_body = _create_panel(
        main, "LIVE PREVIEW", "👁", row=0, column=1, sticky="n", accent=COLORS["accent_purple"]
    )
    preview_body.grid_columnconfigure(0, weight=1)

    preview_center = tk.Frame(preview_body, bg=COLORS["panel"])
    preview_center.grid(row=0, column=0)
    preview_center.grid_columnconfigure(0, weight=1)

    preview_frame = tk.Frame(
        preview_center,
        width=PREVIEW_WIDTH,
        height=PREVIEW_HEIGHT,
        bg=COLORS["preview_bg"],
        highlightthickness=1,
        highlightbackground=COLORS["border"],
    )
    preview_frame.grid(row=0, column=0)
    preview_frame.grid_propagate(False)

    preview_label = tk.Label(
        preview_frame,
        text="No preview",
        bg=COLORS["preview_bg"],
        fg=COLORS["muted"],
        font=FONTS["body"],
    )
    preview_label.place(relx=0.5, rely=0.5, anchor="center")

    preview_btn_padx = max(0, (PREVIEW_WIDTH - PREVIEW_BTN_WIDTH) // 2)
    preview_btn_wrap = tk.Frame(preview_center, bg=COLORS["panel"], width=PREVIEW_BTN_WIDTH)
    preview_btn_wrap.grid(row=1, column=0, pady=(8, 0), padx=preview_btn_padx)
    preview_btn_wrap.grid_propagate(False)
    _light_button(
        preview_btn_wrap,
        "↻  Actualizar preview",
        update_device_preview,
    ).pack(fill="x")

    # Column 3: Runtime Status
    runtime_body = _create_panel(
        main, "RUNTIME STATUS", "♥", row=0, column=2, sticky="n", accent=COLORS["accent_green"]
    )
    runtime_body.grid_columnconfigure(0, weight=1)

    runtime_status_value = _runtime_row(runtime_body, "●", "Estado", 0)
    runtime_device_value = _runtime_row(runtime_body, "🖥", "Dispositivo", 1)
    runtime_profile_value = _runtime_row(runtime_body, "👤", "Perfil", 2)

    event_frame = tk.Frame(runtime_body, bg=COLORS["panel"])
    event_frame.grid(row=3, column=0, sticky="ew", pady=4)
    _label(event_frame, "🕐", font=FONTS["icon"], width=2).grid(row=0, column=0, sticky="nw")
    _label(
        event_frame,
        "Último evento",
        font=FONTS["body_bold"],
        fg=COLORS["muted"],
    ).grid(row=0, column=1, sticky="nw", padx=(4, 0))
    last_event_label = _label(
        event_frame,
        "-",
        font=FONTS["body"],
        fg=COLORS["muted"],
        wraplength=200,
        justify="left",
    )
    last_event_label.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(4, 0))

    # --- Configuration panel ---
    config_outer = tk.Frame(root, bg=COLORS["border"])
    config_outer.grid(row=2, column=0, sticky="ew", padx=PAD["window"], pady=(0, 14))

    config_inner = tk.Frame(config_outer, bg=COLORS["panel"])
    config_inner.pack(fill="x", padx=1, pady=1)

    config_header = tk.Frame(config_inner, bg=COLORS["panel"])
    config_header.pack(fill="x", padx=PAD["panel"], pady=(10, 6))
    _label(config_header, "⚙", font=FONTS["icon"], fg=COLORS["accent_pink"]).pack(side="left")
    _label(config_header, "CONFIGURACIÓN", font=FONTS["section"], fg=COLORS["muted"]).pack(
        side="left", padx=(8, 0)
    )

    config_actions = tk.Frame(config_inner, bg=COLORS["panel"])
    config_actions.pack(fill="x", padx=PAD["panel"], pady=(0, 10))
    for col in range(3):
        config_actions.grid_columnconfigure(col, weight=1, uniform="config")

    _light_button(
        config_actions,
        "👥  Administrar perfiles",
        open_profile_manager,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6), ipady=2)

    _light_button(
        config_actions,
        "◎  Configurar Farm Spot Visual",
        open_farm_spot_config,
    ).grid(row=0, column=1, sticky="ew", padx=6, ipady=2)

    _light_button(
        config_actions,
        "🍃  Configurar Elf Buff",
        open_elf_buff_config,
    ).grid(row=0, column=2, sticky="ew", padx=(6, 0), ipady=2)

    device_select.bind("<<ComboboxSelected>>", _on_device_selected)
    profile_select.bind("<<ComboboxSelected>>", _on_profile_selected)


_build_ui()
set_bot_status("idle")
refresh_devices()
refresh_runtime_status()
root.mainloop()
