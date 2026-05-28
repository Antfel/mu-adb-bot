import io
import threading
import tkinter as tk

from PIL import Image, ImageTk
from tkinter import ttk
from core.profile import list_profiles, set_current_profile
from core.profile import load_profile, save_profile
from core.logger import log
from core.adb import get_device, set_device
from core.device_manager import get_device_screenshot, list_adb_devices
from collections import deque
from states.death_state import is_dead
from states.potion_state import is_any_potion_empty
from states.recovery_state import recover_if_dead
from states.purchase_potions_state import handle_empty_potions
from states.farming import run_farming_state
from states.map_state import is_in_configured_map
from states.navigation_state import go_to_active_farm_spot
from states.elf_buff_check_state import has_elf_buff
from states.elf_buff_state import go_to_elf_buff_and_return
from core.game_actions import clean_game_ui
from core.window_utils import center_window
from core.actions import wait


PREVIEW_WIDTH = 320
PREVIEW_HEIGHT = 180
PREVIEW_BG = "#2b2b2b"

STATUS_CONFIG = {
    "idle": ("#808080", "Detenido"),
    "working": ("#ff8c00", "Navegando"),
    "farming": ("#22c55e", "Farmeando"),
    "error": ("#ef4444", "Error"),
}

bot_running = False
log_lines = deque(maxlen=5)
profile = load_profile()
_preview_photo = None
preview_refresh_job = None


def add_log(message):
    log_lines.append(message)
    log(message)


def _active_device_id():
    device_id = get_device() or device_var.get().strip()
    if not device_id:
        log("[ADB] No device selected")
    return device_id


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


def set_bot_status(state):
    def _apply():
        color, text = STATUS_CONFIG.get(state, STATUS_CONFIG["idle"])
        traffic_canvas.delete("all")
        traffic_canvas.create_oval(8, 8, 52, 52, fill=color, outline=color)
        status_text_label.config(text=text)

    if threading.current_thread() is threading.main_thread():
        _apply()
    else:
        root.after(0, _apply)


def bot_loop():
    global bot_running

    set_bot_status("working")

    try:
        log("[MAIN] Reset inicial de ubicación")
        if not navigate_with_retry():
            log("[MAIN] Reset inicial falló")
            set_bot_status("error")
    except Exception as e:
        log(f"[ERROR] {e}")
        set_bot_status("error")

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
                    log("[MAIN] Falló búsqueda de elf buff")

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
                        log("[MAIN] Farming falló")
                        set_bot_status("error")

        except Exception as e:
            log(f"[ERROR] {e}")
            set_bot_status("error")

        wait(3)

    if not bot_running:
        root.after(0, lambda: set_bot_status("idle"))
        add_log("[BOT] Detenido")


def start_bot():
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

    start_button.config(state="disabled")
    stop_button.config(state="normal")

    set_bot_status("working")
    status_label.config(text="Estado: Ejecutando")
    add_log("[BOT] Iniciado")

    thread = threading.Thread(target=bot_loop, daemon=True)
    thread.start()

    cancel_preview_refresh()
    schedule_preview_refresh()


def stop_bot():
    global bot_running

    bot_running = False
    cancel_preview_refresh()

    start_button.config(state="normal")
    stop_button.config(state="disabled")

    status_label.config(text="Estado: Detenido")
    set_bot_status("idle")
    add_log("[BOT] Detenido")


def open_profile_manager():
    import profile_ui


def _show_no_preview():
    global _preview_photo
    _preview_photo = None
    preview_label.config(image="", text="No preview", bg=PREVIEW_BG, fg="#888888")


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
        return

    if len(devices) == 1:
        device_var.set(devices[0])
    elif device_var.get() not in devices:
        device_var.set(devices[0])

    update_device_preview()


root = tk.Tk()
root.title("MU ADB Bot")
center_window(root, 420, 640)

title_label = tk.Label(root, text="MU ADB Bot", font=("Arial", 18))
title_label.pack(pady=15)

tk.Label(root, text="Perfil").pack()

profiles = list_profiles()

profile_var = tk.StringVar()

profile_select = ttk.Combobox(
    root,
    textvariable=profile_var,
    values=profiles,
    state="readonly",
    width=30
)

manage_button = tk.Button(
    root,
    text="Administrar perfiles",
    width=25,
    command=open_profile_manager
)

manage_button.pack(pady=5)

profile_select.pack(pady=5)

if profiles:
    profile_select.current(0)

tk.Label(root, text="Dispositivo").pack()

device_var = tk.StringVar()

device_select = ttk.Combobox(
    root,
    textvariable=device_var,
    values=[],
    state="readonly",
    width=30
)
device_select.pack(pady=5)

refresh_devices_button = tk.Button(
    root,
    text="Refrescar dispositivos",
    width=25,
    command=refresh_devices
)
refresh_devices_button.pack(pady=5)

preview_frame = tk.Frame(
    root,
    width=PREVIEW_WIDTH,
    height=PREVIEW_HEIGHT,
    bg=PREVIEW_BG,
    highlightthickness=1,
    highlightbackground="#444444",
)
preview_frame.pack(pady=5)
preview_frame.pack_propagate(False)

preview_label = tk.Label(
    preview_frame,
    text="No preview",
    bg=PREVIEW_BG,
    fg="#888888",
)
preview_label.place(relx=0.5, rely=0.5, anchor="center")

update_preview_button = tk.Button(
    root,
    text="Actualizar preview",
    width=25,
    command=update_device_preview,
)
update_preview_button.pack(pady=5)

device_select.bind("<<ComboboxSelected>>", lambda _event: update_device_preview())

refresh_devices()

status_label = tk.Label(root, text="Estado: Detenido", font=("Arial", 12))
status_label.pack(pady=10)

traffic_frame = tk.Frame(root)
traffic_frame.pack(pady=5)

traffic_canvas = tk.Canvas(traffic_frame, width=60, height=60, highlightthickness=0)
traffic_canvas.pack(side=tk.LEFT, padx=(0, 10))

status_text_label = tk.Label(traffic_frame, text="Detenido", font=("Arial", 12))
status_text_label.pack(side=tk.LEFT)

set_bot_status("idle")

start_button = tk.Button(root, text="Iniciar Bot", width=20, command=start_bot)
start_button.pack(pady=5)

stop_button = tk.Button(
    root, text="Detener Bot", width=20, command=stop_bot, state="disabled"
)
stop_button.pack(pady=5)

root.mainloop()
