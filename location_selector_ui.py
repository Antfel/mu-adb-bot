import tkinter as tk

from PIL import Image, ImageTk

from core.logger import log
from core.path_utils import resource_path
from core.ui_theme import (
    ACCENT_GREEN,
    ACCENT_PURPLE,
    COMBO_WIDTH,
    ENTRY_WIDTH_DEFAULT,
    PAD_ROW,
    PAD_WINDOW,
    PANEL_BG,
    PANEL_BORDER,
    PREVIEW_BG,
    TEXT_SECONDARY,
    UI_BG,
    configure_window,
    create_combobox,
    create_entry,
    create_form_label,
    create_packed_section,
    create_primary_button,
    setup_theme,
    ui_label,
)
from core.window_utils import fit_and_center_window
from core.navigation_config import (
    is_map_navigable,
    list_implemented_navigation_maps,
    load_map_definition,
)
from core.special_locations import (
    get_active_location,
    make_location_id,
    normalize_profile_name,
    upsert_location,
)

CANVAS_WIDTH = 900
CANVAS_HEIGHT = 506
MARKER_RADIUS = 6
LOCATION_WINDOW_INITIAL_WIDTH = 1000
LOCATION_WINDOW_INITIAL_HEIGHT = 700
LOCATION_WINDOW_MIN_WIDTH = 900
LOCATION_WINDOW_MIN_HEIGHT = 650

LOCATION_TITLES = {
    "farm_spot": "Configurar Farm Spot Visual",
    "elf_buff": "Configurar Elf Buff",
}

LOCATION_ICONS = {
    "farm_spot": "◎",
    "elf_buff": "🍃",
}

LOCATION_ACCENTS = {
    "farm_spot": ACCENT_PURPLE,
    "elf_buff": ACCENT_GREEN,
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
        wire_ids = sorted({_safe_int(key, 0) for key in wires} - {0})
        return wire_ids
    return []


def _build_map_display_mapping(include_map_ids=None):
    map_display_to_id = {}
    map_display_names = []
    for map_def in list_implemented_navigation_maps(include_map_ids=include_map_ids):
        display_name = map_def.get("name") or map_def["id"]
        map_display_to_id[display_name] = map_def["id"]
        map_display_names.append(display_name)
    return map_display_to_id, map_display_names


def open_location_selector(location_type, profile_name, on_close=None):
    profile_name = normalize_profile_name(profile_name)
    if not profile_name:
        log("[LOCATIONS] Profile name is required")
        return

    title = LOCATION_TITLES.get(location_type, f"Configurar {location_type}")
    icon = LOCATION_ICONS.get(location_type, "📍")
    accent = LOCATION_ACCENTS.get(location_type, ACCENT_PURPLE)

    existing_location = get_active_location(profile_name, location_type)
    include_map_ids = []
    if existing_location and existing_location.get("map"):
        existing_map_id = existing_location["map"]
        try:
            existing_map_def = load_map_definition(existing_map_id)
            if is_map_navigable(existing_map_def):
                include_map_ids.append(existing_map_id)
        except FileNotFoundError:
            pass

    map_display_to_id, map_display_names = _build_map_display_mapping(include_map_ids)

    def selected_map_id():
        return map_display_to_id.get(map_var.get().strip(), "")

    window = tk.Toplevel()
    window.title(title)
    configure_window(window)
    setup_theme(window)

    def _notify_close():
        if on_close is not None:
            on_close()

    def close_location_window():
        try:
            window.destroy()
        except tk.TclError:
            pass
        _notify_close()

    window.protocol("WM_DELETE_WINDOW", close_location_window)

    main = tk.Frame(window, bg=UI_BG)
    main.pack(fill=tk.BOTH, expand=True, padx=PAD_WINDOW, pady=PAD_WINDOW)

    form_body = create_packed_section(main, title, icon, accent=accent, fill="both")
    form_body.grid_columnconfigure(0, weight=1)

    map_var = tk.StringVar()
    wire_var = tk.StringVar()
    name_var = tk.StringVar(
        value="Farm Spot" if location_type == "farm_spot" else "Elf Buff"
    )

    row = 0
    create_form_label(form_body, "Mapa", row=row, column=0, sticky="w", pady=(0, 3))
    map_select = create_combobox(
        form_body,
        map_var,
        values=map_display_names,
        width=COMBO_WIDTH + 8,
        row=row + 1,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )
    row += 2

    create_form_label(form_body, "Wire", row=row, column=0, sticky="w", pady=(0, 3))
    wire_select = create_combobox(
        form_body,
        wire_var,
        width=COMBO_WIDTH + 8,
        row=row + 1,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )
    row += 2

    create_form_label(form_body, "Nombre", row=row, column=0, sticky="w", pady=(0, 3))
    name_entry = create_entry(
        form_body,
        textvariable=name_var,
        width=ENTRY_WIDTH_DEFAULT + 10,
        row=row + 1,
        column=0,
        sticky="ew",
        pady=(0, PAD_ROW),
    )
    row += 2

    message_label = ui_label(form_body, "", fg=TEXT_SECONDARY)
    message_label.grid(row=row, column=0, sticky="w", pady=(0, PAD_ROW))
    row += 1

    coords_label = ui_label(form_body, "X: - | Y: -", font=("Segoe UI", 10, "bold"))
    coords_label.grid(row=row, column=0, sticky="w", pady=(0, PAD_ROW))

    canvas_section = create_packed_section(main, "Mapa", "🗺", accent=accent, fill="both")
    canvas_frame = tk.Frame(
        canvas_section,
        width=CANVAS_WIDTH,
        height=CANVAS_HEIGHT,
        bg=PREVIEW_BG,
        highlightthickness=1,
        highlightbackground=PANEL_BORDER,
    )
    canvas_frame.pack(pady=(0, PAD_ROW))
    canvas_frame.pack_propagate(False)

    canvas = tk.Canvas(
        canvas_frame,
        width=CANVAS_WIDTH,
        height=CANVAS_HEIGHT,
        bg=PREVIEW_BG,
        highlightthickness=0,
    )
    canvas.pack()

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
            message_label.config(text="Wire no configurado")
            return

        if not wire_ids:
            wire_select["values"] = []
            wire_var.set("")
            message_label.config(text="Wire no configurado")
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
        _notify_close()

    def on_map_selected(_event=None):
        load_map_image()
        refresh_wire_options()

    canvas.bind("<Button-1>", on_canvas_click)
    map_select.bind("<<ComboboxSelected>>", on_map_selected)

    actions = tk.Frame(main, bg=UI_BG)
    actions.pack(fill=tk.X, pady=(PAD_ROW, 0))
    actions.grid_columnconfigure(0, weight=1)
    actions.grid_columnconfigure(1, weight=1)

    create_primary_button(
        actions,
        "Guardar ubicación",
        save_location,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

    create_primary_button(
        actions,
        "Cerrar",
        close_location_window,
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    if map_display_names:
        initial_display = map_display_names[0]
        if include_map_ids:
            try:
                existing_map_def = load_map_definition(include_map_ids[0])
                initial_display = existing_map_def.get("name") or include_map_ids[0]
                if initial_display not in map_display_names:
                    initial_display = map_display_names[0]
            except FileNotFoundError:
                pass
        map_var.set(initial_display)
        if existing_location:
            wire_var.set(str(existing_location.get("wire", "")))
            if existing_location.get("name"):
                name_var.set(existing_location["name"])
        on_map_selected()

    fit_and_center_window(
        window,
        LOCATION_WINDOW_INITIAL_WIDTH,
        LOCATION_WINDOW_INITIAL_HEIGHT,
        min_width=LOCATION_WINDOW_MIN_WIDTH,
        min_height=LOCATION_WINDOW_MIN_HEIGHT,
    )
