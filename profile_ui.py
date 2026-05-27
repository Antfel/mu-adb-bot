import tkinter as tk
from tkinter import ttk

from core.profile import (
    load_profile,
    save_profile,
    list_profiles
)

from coordinates.spots import MAPS


root = tk.Toplevel()

root.title("Profile Manager")
root.geometry("400x500")


# profiles

profiles = list_profiles()

selected_profile = tk.StringVar()

profile_select = ttk.Combobox(
    root,
    textvariable=selected_profile,
    values=profiles,
    state="readonly",
    width=30
)

profile_select.pack(pady=10)


profile_data = {}

def refresh_profile_fields():
    selected_map_label.config(
        text=f"Mapa: {profile_data.get('map', '-')} | "
             f"Wire: {profile_data.get('wire', '-')} | "
             f"Spot: {profile_data.get('spot', '-')}"
    )

def open_map_selector():
    import map_selector_ui
    map_selector_ui.open_selector(profile_data, refresh_profile_fields)


map_button = tk.Button(
    root,
    text="Seleccionar Mapa / Wire / Spot",
    width=28,
    command=open_map_selector
)

map_button.pack(pady=10)

selected_map_label = tk.Label(
    root,
    text="Mapa: - | Wire: - | Spot: -"
)

selected_map_label.pack(pady=5)

def load_selected_profile(event=None):
    
    global profile_data

    profile_name = selected_profile.get()

    profile_data = load_profile(f"profiles/{profile_name}")

    hp_var.set(profile_data["hp_potion_stacks"])
    mp_var.set(profile_data["mp_potion_stacks"])

    potion_var.set(profile_data["enable_potion_recovery"])
    death_var.set(profile_data["enable_death_recovery"])
    auto_var.set(profile_data["enable_auto_attack"])

    refresh_profile_fields()


profile_select.bind("<<ComboboxSelected>>", load_selected_profile)

# hp stacks
tk.Label(root, text="HP Potion Stacks").pack()
hp_var = tk.IntVar()
hp_input = tk.Entry(root, textvariable=hp_var)
hp_input.pack()


# mp stacks
tk.Label(root, text="MP Potion Stacks").pack()
mp_var = tk.IntVar()
mp_input = tk.Entry(root, textvariable=mp_var)
mp_input.pack()


# checkboxes

potion_var = tk.BooleanVar()
death_var = tk.BooleanVar()
auto_var = tk.BooleanVar()

tk.Checkbutton(
    root,
    text="Potion Recovery",
    variable=potion_var
).pack()

tk.Checkbutton(
    root,
    text="Death Recovery",
    variable=death_var
).pack()

tk.Checkbutton(
    root,
    text="Auto Attack",
    variable=auto_var
).pack()


def save_current_profile():

    profile_data["hp_potion_stacks"] = hp_var.get()
    profile_data["mp_potion_stacks"] = mp_var.get()

    profile_data["enable_potion_recovery"] = potion_var.get()
    profile_data["enable_death_recovery"] = death_var.get()
    profile_data["enable_auto_attack"] = auto_var.get()

    profile_name = selected_profile.get()

    save_profile(
        profile_data,
        f"profiles/{profile_name}"
    )

    print("[PROFILE] Guardado")


save_button = tk.Button(
    root,
    text="Guardar",
    width=20,
    command=save_current_profile
)

save_button.pack(pady=20)


if profiles:
    profile_select.current(0)
    load_selected_profile()


root.mainloop()