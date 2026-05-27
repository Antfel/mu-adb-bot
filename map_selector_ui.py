import tkinter as tk
from tkinter import ttk

from coordinates.spots import MAPS, get_spot_ids, get_wire_ids, normalize_wire_id


def _wire_label(map_id, wire_id):
    wire_data = MAPS[map_id]["wires"][wire_id]
    return f"{wire_id} - {wire_data.get('name', f'Wire {wire_id}')}"


def _spot_label(map_id, wire_id, spot_id):
    spot_data = MAPS[map_id]["wires"][wire_id]["spots"][spot_id]
    return f"{spot_id} - {spot_data.get('name', spot_id)}"


def open_selector(profile_data, on_save_callback=None):

    window = tk.Toplevel()
    window.title("Seleccionar Mapa")
    window.geometry("360x300")

    map_var = tk.StringVar(
        value=profile_data.get("map", list(MAPS.keys())[0])
    )

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
        values=list(MAPS.keys()),
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

    def refresh_wire_options():
        selected_map = map_var.get()
        wire_ids = get_wire_ids(selected_map)

        wire_select["values"] = [
            _wire_label(selected_map, wire_id) for wire_id in wire_ids
        ]

        current_wire = normalize_wire_id(wire_var.get()) if wire_var.get() else wire_ids[0]
        if current_wire not in wire_ids:
            current_wire = wire_ids[0]

        wire_var.set(_wire_label(selected_map, current_wire))

    def refresh_spot_options():
        selected_map = map_var.get()
        wire_id = normalize_wire_id(wire_var.get().split(" - ", 1)[0])
        spot_ids = get_spot_ids(selected_map, wire_id)

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
        profile_data["wire"] = normalize_wire_id(
            wire_var.get().split(" - ", 1)[0]
        )
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
