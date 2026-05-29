import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from core.logger import log
from core.path_utils import resource_path
from core.window_utils import center_window
from core.navigation_config import load_all_map_definitions, load_map_definition
from core.special_locations import (
    make_location_id,
    normalize_profile_name,
    upsert_location,
)

CANVAS_WIDTH = 900
CANVAS_HEIGHT = 506
MARKER_RADIUS = 6

LOCATION_TITLES = {
    "farm_spot": "Configurar Farm Spot Visual",
    "elf_buff": "Configurar Elf Buff",
}


def _safe_int(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _wire_count_from_metadata(wire_value):
    if wire_value is None or isinstance(wire_value, dict):
        return None
    if isinstance(wire_value, bool):
        return None
    if isinstance(wire_value, int):
        return wire_value if wire_value > 0 else None
    if isinstance(wire_value, str):
        try:
            count = int(wire_value.strip())
            return count if count > 0 else None
        except (TypeError, ValueError):
            return None
    try:
        count = int(wire_value)
        return count if count > 0 else None
    except (TypeError, ValueError):
        return None


def _wire_options_from_map_def(map_def):
    wire_count = _wire_count_from_metadata(map_def.get("wire"))
    if wire_count is not None:
        return list(range(1, wire_count + 1))

    wires = map_def.get("wires") or {}
    if wires:
        wire_ids = sorted(
            {_safe_int(key, 0) for key in wires} - {0}
        )
        return wire_ids
    return []


def _map_sort_key(map_def):
    order = map_def.get("order")
    try:
        order = int(order) if order is not None else 9999
    except (TypeError, ValueError):
        order = 9999
    submap = _safe_int(map_def.get("submap"), 1)
    name = map_def.get("name") or map_def["id"]
    return (order, submap, name)


def _build_map_display_mapping():
    sorted_defs = sorted(
        load_all_map_definitions().values(),
        key=_map_sort_key,
    )
    map_display_to_id = {}
    map_display_names = []
    for map_def in sorted_defs:
        display_name = map_def.get("name") or map_def["id"]
        map_display_to_id[display_name] = map_def["id"]
        map_display_names.append(display_name)
    return map_display_to_id, map_display_names


def open_location_selector(location_type, profile_name):
    profile_name = normalize_profile_name(profile_name)
    if not profile_name:
        log("[LOCATIONS] Profile name is required")
        return

    title = LOCATION_TITLES.get(location_type, f"Configurar {location_type}")

    map_display_to_id, map_display_names = _build_map_display_mapping()

    def selected_map_id():
        return map_display_to_id.get(map_var.get().strip(), "")

    window = tk.Toplevel()
    window.title(title)
    center_window(window, 1000, 780)

    state = {
        "scale": 1.0,
        "offset_x": 0,
        "offset_y": 0,
        "image_width": 2560,
        "image_height": 1440,
        "selected_x": None,
        "selected_y": None,
        "photo": None,
        "marker_id": None,
    }

    tk.Label(window, text="Mapa").pack(pady=(10, 2))
    map_var = tk.StringVar()
    map_select = ttk.Combobox(
        window,
        textvariable=map_var,
        values=map_display_names,
        state="readonly",
        width=40,
    )
    map_select.pack(pady=2)

    tk.Label(window, text="Wire").pack(pady=(8, 2))
    wire_var = tk.StringVar()
    wire_select = ttk.Combobox(
        window,
        textvariable=wire_var,
        state="readonly",
        width=40,
    )
    wire_select.pack(pady=2)

    tk.Label(window, text="Nombre").pack(pady=(8, 2))
    name_var = tk.StringVar(value="Farm Spot" if location_type == "farm_spot" else "Elf Buff")
    name_entry = tk.Entry(window, textvariable=name_var, width=42)
    name_entry.pack(pady=2)

    message_label = tk.Label(window, text="", fg="#888888")
    message_label.pack(pady=4)

    canvas_frame = tk.Frame(
        window,
        width=CANVAS_WIDTH,
        height=CANVAS_HEIGHT,
        bg="#2b2b2b",
        highlightthickness=1,
        highlightbackground="#444444",
    )
    canvas_frame.pack(pady=8)
    canvas_frame.pack_propagate(False)

    canvas = tk.Canvas(
        canvas_frame,
        width=CANVAS_WIDTH,
        height=CANVAS_HEIGHT,
        bg="#2b2b2b",
        highlightthickness=0,
    )
    canvas.pack()

    coords_label = tk.Label(window, text="X: - | Y: -", font=("Arial", 11))
    coords_label.pack(pady=4)

    def refresh_wire_options():
        map_id = selected_map_id()
        if not map_id:
            wire_select["values"] = []
            wire_var.set("")
            return

        try:
            map_def = load_map_definition(map_id)
            wire_ids = _wire_options_from_map_def(map_def)
        except Exception as e:
            log(f"[LOCATIONS] Failed to load wires for {map_id}: {e}")
            wire_select["values"] = []
            wire_var.set("")
            message_label.config(text="Wire no configurado", fg="#888888")
            return

        if not wire_ids:
            wire_select["values"] = []
            wire_var.set("")
            message_label.config(text="Wire no configurado", fg="#888888")
            return

        wire_select["values"] = [str(w) for w in wire_ids]
        if wire_var.get() not in wire_select["values"]:
            wire_var.set(str(wire_ids[0]))

    def clear_marker():
        if state["marker_id"] is not None:
            canvas.delete(state["marker_id"])
            state["marker_id"] = None

    def draw_marker(display_x, display_y):
        clear_marker()
        r = MARKER_RADIUS
        state["marker_id"] = canvas.create_oval(
            display_x - r,
            display_y - r,
            display_x + r,
            display_y + r,
            fill="#22c55e",
            outline="#ffffff",
            width=2,
        )

    def display_to_real(display_x, display_y):
        real_x = int((display_x - state["offset_x"]) / state["scale"])
        real_y = int((display_y - state["offset_y"]) / state["scale"])
        real_x = max(0, min(real_x, state["image_width"]))
        real_y = max(0, min(real_y, state["image_height"]))
        return real_x, real_y

    def update_coords_label():
        if state["selected_x"] is None or state["selected_y"] is None:
            coords_label.config(text="X: - | Y: -")
        else:
            coords_label.config(
                text=f"X: {state['selected_x']} | Y: {state['selected_y']}"
            )

    def load_map_image(_event=None):
        clear_marker()
        state["selected_x"] = None
        state["selected_y"] = None
        update_coords_label()
        canvas.delete("all")

        map_id = selected_map_id()
        if not map_id:
            message_label.config(text="Seleccione un mapa")
            return

        try:
            map_def = load_map_definition(map_id)
        except Exception as e:
            message_label.config(text=f"Error cargando mapa: {e}")
            log(f"[LOCATIONS] {e}")
            return

        maintenance = map_def.get("maintenance", {})
        image_path = maintenance.get("map_ui_image")

        if not image_path:
            message_label.config(text="Mapa sin imagen de mantenimiento")
            log(f"[LOCATIONS] No maintenance.map_ui_image for {map_id}")
            return

        state["image_width"] = _safe_int(maintenance.get("image_width"), 2560)
        state["image_height"] = _safe_int(maintenance.get("image_height"), 1440)

        try:
            image = Image.open(resource_path(image_path))
        except Exception as e:
            message_label.config(text="No se pudo cargar imagen de mantenimiento")
            log(f"[LOCATIONS] Failed to load image {image_path}: {e}")
            return

        scale = min(
            CANVAS_WIDTH / state["image_width"],
            CANVAS_HEIGHT / state["image_height"],
        )
        display_w = max(1, int(state["image_width"] * scale))
        display_h = max(1, int(state["image_height"] * scale))

        resized = image.resize((display_w, display_h), Image.Resampling.LANCZOS)
        state["photo"] = ImageTk.PhotoImage(resized)
        state["scale"] = scale
        state["offset_x"] = (CANVAS_WIDTH - display_w) // 2
        state["offset_y"] = (CANVAS_HEIGHT - display_h) // 2

        canvas.create_image(
            state["offset_x"],
            state["offset_y"],
            image=state["photo"],
            anchor="nw",
        )
        message_label.config(text="")
        log(f"[LOCATIONS] Loaded maintenance image for {map_id}")

    def on_canvas_click(event):
        if state["photo"] is None:
            return

        display_x = event.x
        display_y = event.y

        img_left = state["offset_x"]
        img_top = state["offset_y"]
        img_right = img_left + int(state["image_width"] * state["scale"])
        img_bottom = img_top + int(state["image_height"] * state["scale"])

        if not (img_left <= display_x <= img_right and img_top <= display_y <= img_bottom):
            return

        real_x, real_y = display_to_real(display_x, display_y)
        state["selected_x"] = real_x
        state["selected_y"] = real_y
        draw_marker(display_x, display_y)
        update_coords_label()
        log(f"[LOCATIONS] Selected coordinates: {real_x}, {real_y}")

    def save_location():
        map_id = selected_map_id()
        name = name_var.get().strip()

        if not map_id:
            log("[LOCATIONS] Map is required to save")
            return

        try:
            wire_ids = _wire_options_from_map_def(load_map_definition(map_id))
        except Exception as e:
            log(f"[LOCATIONS] Failed to load wires for save: {e}")
            return

        if not wire_ids:
            log("[LOCATIONS] Wire no configurado para este mapa")
            return

        wire = _safe_int(wire_var.get(), 0)
        if wire not in wire_ids:
            log("[LOCATIONS] Seleccione un wire válido")
            return

        if state["selected_x"] is None or state["selected_y"] is None:
            log("[LOCATIONS] Select a point on the map image first")
            return

        if not name:
            log("[LOCATIONS] Name is required to save")
            return

        location = {
            "id": make_location_id(profile_name, location_type, name),
            "profile": profile_name,
            "type": location_type,
            "name": name,
            "map": map_id,
            "wire": wire,
            "x": state["selected_x"],
            "y": state["selected_y"],
        }

        upsert_location(location)
        log(f"[LOCATIONS] Saved {location_type}: {location['id']}")

    def on_map_selected(_event=None):
        load_map_image()
        refresh_wire_options()

    canvas.bind("<Button-1>", on_canvas_click)
    map_select.bind("<<ComboboxSelected>>", on_map_selected)

    button_frame = tk.Frame(window)
    button_frame.pack(pady=10)

    tk.Button(
        button_frame,
        text="Guardar",
        width=16,
        command=save_location,
    ).pack(side=tk.LEFT, padx=5)

    tk.Button(
        button_frame,
        text="Cerrar",
        width=16,
        command=window.destroy,
    ).pack(side=tk.LEFT, padx=5)

    if map_display_names:
        map_var.set(map_display_names[0])
        on_map_selected()
