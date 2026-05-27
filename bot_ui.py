import threading
import tkinter as tk

from tkinter import ttk
from core.profile import list_profiles, set_current_profile
from core.profile import load_profile, save_profile
from core.logger import subscribe
from collections import deque
from states.death_state import is_dead
from states.potion_state import is_any_potion_empty
from states.recovery_state import recover_if_dead
from states.purchase_potions_state import handle_empty_potions
from states.farming import run_farming_state
from states.map_state import is_in_configured_map
from states.navigation_state import go_to_active_farm_spot
from core.actions import wait



bot_running = False
log_lines = deque(maxlen=5)
profile = load_profile()


def add_log(message):
    log_lines.append(message)
    log_text.config(state="normal")
    log_text.delete("1.0", tk.END)
    log_text.insert(tk.END, "\n".join(log_lines))
    log_text.config(state="disabled")

subscribe(add_log)

def bot_loop():
    global bot_running

    while bot_running:
        if is_dead():
            add_log("[MAIN] Personaje muerto")
            recover_if_dead()

        elif is_any_potion_empty():
            add_log("[MAIN] Pociones agotadas")
            handle_empty_potions()

        else:
            if not is_in_configured_map():
                add_log("[MAIN] Mapa incorrecto. Volviendo al spot")
                go_to_active_farm_spot()
            else:
                run_farming_state()

        wait(3)

    add_log("[BOT] Detenido")


def start_bot():
    global bot_running

    if bot_running:
        return

    selected_profile = profile_var.get()

    if selected_profile:
        set_current_profile(selected_profile)
        add_log(f"[PROFILE] Perfil activo: {selected_profile}")

    bot_running = True

    start_button.config(state="disabled")
    stop_button.config(state="normal")

    thread = threading.Thread(target=bot_loop, daemon=True)
    thread.start()

    status_label.config(text="Estado: Ejecutando")
    add_log("[BOT] Iniciado")


def stop_bot():
    global bot_running

    bot_running = False

    start_button.config(state="normal")
    stop_button.config(state="disabled")

    status_label.config(text="Estado: Detenido")
    add_log("[BOT] Detenido")


root = tk.Tk()
root.title("MU ADB Bot")
root.geometry("420x430")

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


def open_profile_manager():
    import profile_ui

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

status_label = tk.Label(root, text="Estado: Detenido", font=("Arial", 12))
status_label.pack(pady=10)

log_text = tk.Text(
    root,
    height=6,
    width=42,
    state="disabled"
)

log_text.pack(pady=10)

subscribe(add_log)

start_button = tk.Button(root, text="Iniciar Bot", width=20, command=start_bot)
start_button.pack(pady=5)

stop_button = tk.Button(root, text="Detener Bot", width=20, command=stop_bot,state="disabled")
stop_button.pack(pady=5)

root.mainloop()