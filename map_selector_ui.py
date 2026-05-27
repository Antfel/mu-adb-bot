import tkinter as tk
from tkinter import ttk

from core.navigation_config import list_available_maps, load_map_definition


def _wire_label(map_id, wire_id):
    map_def = load_map_definition(map_id)
    wire_data = map_def["wires"][wire_id]
    return f"{wire_id} - {wire_data.get('name', f'Wire {wire_id}')}"


def _spot_label(map_id, wire_id, spot_id):
    map_def = load_map_definition(map_id)
    wire_data = map_def["wires"][wire_id]
    spot_ids = wire_data.get("spots", [])
    if spot_id not in spot_ids:
        # fallback: si el wire no lista spots, aún permitimos label desde el dict global de spots
        spot_data = map_def.get("spots", {}).get(spot_id, {})
    else:
        spot_data = map_def.get("spots", {}).get(spot_id, {})
    return f"{spot_id} - {spot_data.get('name', spot_id)}"


def open_selector(profile_data, on_save_callback=None):

    window = tk.Toplevel()
    window.title("Seleccionar Mapa")
    window.geometry("360x300")

    available_maps = list_available_maps()
    default_map = profile_data.get("map", available_maps[0] if available_maps else "")
    map_var = tk.StringVar(value=default_map)

    wire_var = tk.StringVar(
        value=str(profile_data.get("wire", 1))
    )

    spot_var = tk.StringVar(
        value=profile_data.get("spot", "spot_1")
    )

    tk.Label(window, text="Mapa").pack(pady=(15, 5))

    map_select = ttk.Combobox(
        window,
        textvariable=map_var,
        values=available_maps,
        state="readonly",
        width=30,
    )

    map_select.pack(pady=5)

    tk.Label(window, text="Wire").pack(pady=(10, 5))

    wire_select = ttk.Combobox(
        window,
        textvariable=wire_var,
        state="readonly",
        width=30,
    )

    wire_select.pack(pady=5)

    tk.Label(window, text="Spot").pack(pady=(10, 5))

    spot_select = ttk.Combobox(
        window,
        textvariable=spot_var,
        state="readonly",
        width=30,
    )

    spot_select.pack(pady=5)

    def _normalize_wire_id(wire):
        # wire puede venir como "1" o como "1 - Wire 1"
        value = str(wire).split(" - ", 1)[0]
        return int(value)

    def refresh_wire_options():
        selected_map = map_var.get()
        map_def = load_map_definition(selected_map)
        wire_ids = sorted(map_def.get("wires", {}).keys())

        wire_select["values"] = [
            _wire_label(selected_map, wire_id) for wire_id in wire_ids
        ]

        current_wire = _normalize_wire_id(wire_var.get()) if wire_var.get() else wire_ids[0]
        if current_wire not in wire_ids:
            current_wire = wire_ids[0]

        wire_var.set(_wire_label(selected_map, current_wire))

    def refresh_spot_options():
        selected_map = map_var.get()
        wire_id = _normalize_wire_id(wire_var.get())

        map_def = load_map_definition(selected_map)
        wire_data = map_def.get("wires", {}).get(wire_id, {})
        spot_ids = list(wire_data.get("spots", []))

        spot_select["values"] = [
            _spot_label(selected_map, wire_id, spot_id) for spot_id in spot_ids
        ]

        current_spot = spot_var.get().split(" - ", 1)[0]
        if current_spot not in spot_ids:
            current_spot = spot_ids[0]

        spot_var.set(_spot_label(selected_map, wire_id, current_spot))

    def refresh_options(event=None):
        refresh_wire_options()
        refresh_spot_options()

    map_select.bind("<<ComboboxSelected>>", refresh_options)
    wire_select.bind("<<ComboboxSelected>>", refresh_spot_options)

    refresh_options()

    def save_selection():
        profile_data["map"] = map_var.get()
        profile_data["wire"] = _normalize_wire_id(wire_var.get())
        profile_data["spot"] = spot_var.get().split(" - ", 1)[0]

        if on_save_callback:
            on_save_callback()

        window.destroy()

    tk.Button(
        window,
        text="Usar selección",
        width=25,
        command=save_selection,
    ).pack(pady=25)
