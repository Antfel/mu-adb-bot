import tkinter as tk

from core.navigation_config import list_available_maps, load_map_definition
from core.ui_theme import (
    ACCENT_BLUE,
    COMBO_WIDTH,
    PAD_ROW,
    PAD_WINDOW,
    UI_BG,
    configure_window,
    create_combobox,
    create_form_label,
    create_packed_section,
    create_primary_button,
    setup_theme,
)
from core.window_utils import center_window


def _wire_label(map_id, wire_id):
    map_def = load_map_definition(map_id)
    wire_data = map_def["wires"][wire_id]
    return f"{wire_id} - {wire_data.get('name', f'Wire {wire_id}')}"


def _spot_label(map_id, wire_id, spot_id):
    map_def = load_map_definition(map_id)
    wire_data = map_def["wires"][wire_id]
    spot_ids = wire_data.get("spots", [])
    if spot_id not in spot_ids:
        spot_data = map_def.get("spots", {}).get(spot_id, {})
    else:
        spot_data = map_def.get("spots", {}).get(spot_id, {})
    return f"{spot_id} - {spot_data.get('name', spot_id)}"


def open_selector(profile_data, on_save_callback=None):
    window = tk.Toplevel()
    window.title("Seleccionar mapa")
    center_window(window, 400, 420)
    configure_window(window)
    setup_theme(window)

    main = tk.Frame(window, bg=UI_BG)
    main.pack(fill=tk.BOTH, expand=True, padx=PAD_WINDOW, pady=PAD_WINDOW)
    main.grid_columnconfigure(0, weight=1)

    available_maps = list_available_maps()
    default_map = profile_data.get("map", available_maps[0] if available_maps else "")
    map_var = tk.StringVar(value=default_map)
    wire_var = tk.StringVar(value=str(profile_data.get("wire", 1)))
    spot_var = tk.StringVar(value=profile_data.get("spot", "spot_1"))

    selector_body = create_packed_section(main, "Selector de mapas", "🗺", accent=ACCENT_BLUE)
    selector_body.grid_columnconfigure(0, weight=1)

    row = 0
    create_form_label(selector_body, "Mapa", row=row, column=0, sticky="w", pady=(0, 3))
    map_select = create_combobox(
        selector_body,
        map_var,
        values=available_maps,
        width=COMBO_WIDTH,
        row=row + 1,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )
    row += 2

    create_form_label(selector_body, "Wire", row=row, column=0, sticky="w", pady=(0, 3))
    wire_select = create_combobox(
        selector_body,
        wire_var,
        width=COMBO_WIDTH,
        row=row + 1,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )
    row += 2

    create_form_label(selector_body, "Spot", row=row, column=0, sticky="w", pady=(0, 3))
    spot_select = create_combobox(
        selector_body,
        spot_var,
        width=COMBO_WIDTH,
        row=row + 1,
        column=0,
        sticky="ew",
    )

    def _normalize_wire_id(wire):
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

    actions = tk.Frame(main, bg=UI_BG)
    actions.pack(fill=tk.X, pady=(PAD_ROW, 0))
    actions.grid_columnconfigure(0, weight=1)
    actions.grid_columnconfigure(1, weight=1)

    create_primary_button(
        actions,
        "Confirmar",
        save_selection,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

    create_primary_button(
        actions,
        "Cancelar",
        window.destroy,
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
