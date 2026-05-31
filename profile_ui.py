import tkinter as tk
from tkinter import ttk

from core.logger import log
from core.special_locations import get_elf_buff_location, get_farm_spot_location
from core.ui_theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_PURPLE,
    PAD_PANEL,
    PAD_ROW,
    PAD_WINDOW,
    PANEL_BG,
    TEXT_SECONDARY,
    UI_BG,
    configure_window,
    create_checkbutton,
    create_combobox,
    create_entry,
    create_form_label,
    create_dialog_panel,
    create_packed_section,
    create_primary_button,
    create_section_title,
    setup_theme,
    ui_label,
)
from core.window_utils import center_window, fit_and_center_window
from core.navigation_config import list_maps_for_kill_boss_ui
from core.profile import (
    BOT_MODE_LABEL_BY_VALUE,
    BOT_MODE_VALUE_BY_LABEL,
    _write_current_profile_pointer,
    create_profile,
    delete_profile,
    duplicate_profile,
    get_display_name,
    list_profile_entries,
    list_profiles,
    load_profile,
    normalize_profile_data,
    save_profile,
)

PROFILE_WINDOW_WIDTH = 920
PROFILE_WINDOW_HEIGHT = 760
PROFILE_WINDOW_MIN_WIDTH = 880
PROFILE_WINDOW_MIN_HEIGHT = 620
LISTBOX_WIDTH = 22
PROFILE_NAME_MODAL_WIDTH = 420
PROFILE_NAME_MODAL_HEIGHT = 200
CONFIRM_MODAL_WIDTH = 420
CONFIRM_MODAL_HEIGHT = 170

profile_window = None
_on_close_callback = None
profile_entries = []
profile_file_names = []
profiles_dirty = False


def _profile_ui_trace(message):
    print(f"[PROFILE_UI] {message}", flush=True)


def _widget_exists(widget):
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def _safe_focus_set(widget):
    if not _widget_exists(widget):
        return
    try:
        _profile_ui_trace("before focus_set")
        widget.focus_set()
        _profile_ui_trace("after focus_set")
    except tk.TclError as exc:
        _profile_ui_trace(f"focus_set TclError: {exc}")


def _safe_listbox_delete(listbox, first, last=None):
    if not _widget_exists(listbox):
        return
    try:
        _profile_ui_trace(f"before profile_listbox.delete({first}, {last})")
        if last is None:
            listbox.delete(first)
        else:
            listbox.delete(first, last)
        _profile_ui_trace(f"after profile_listbox.delete({first}, {last})")
    except tk.TclError as exc:
        _profile_ui_trace(f"profile_listbox.delete TclError: {exc}")


def _safe_listbox_selection_clear(listbox, first, last):
    if not _widget_exists(listbox):
        return
    try:
        _profile_ui_trace(f"before profile_listbox.selection_clear({first}, {last})")
        listbox.selection_clear(first, last)
        _profile_ui_trace(f"after profile_listbox.selection_clear({first}, {last})")
    except tk.TclError as exc:
        _profile_ui_trace(f"profile_listbox.selection_clear TclError: {exc}")


def _safe_listbox_selection_set(listbox, index):
    if not _widget_exists(listbox):
        return
    try:
        _profile_ui_trace(f"before profile_listbox.selection_set({index})")
        listbox.selection_set(index)
        _profile_ui_trace(f"after profile_listbox.selection_set({index})")
    except tk.TclError as exc:
        _profile_ui_trace(f"profile_listbox.selection_set TclError: {exc}")


def _safe_listbox_insert(listbox, index, value):
    if not _widget_exists(listbox):
        return
    try:
        listbox.insert(index, value)
    except tk.TclError as exc:
        _profile_ui_trace(f"profile_listbox.insert TclError: {exc}")


def _safe_listbox_activate(listbox, index):
    if not _widget_exists(listbox):
        return
    try:
        listbox.activate(index)
    except tk.TclError as exc:
        _profile_ui_trace(f"profile_listbox.activate TclError: {exc}")


def _safe_listbox_see(listbox, index):
    if not _widget_exists(listbox):
        return
    try:
        listbox.see(index)
    except tk.TclError as exc:
        _profile_ui_trace(f"profile_listbox.see TclError: {exc}")


def _run_close_callback(callback, select_filename, main_root):
    if callback is None:
        return

    def _run_callback():
        _profile_ui_trace("before main window profile refresh callback")
        try:
            callback(select_filename)
        except TypeError:
            callback()
        _profile_ui_trace("after main window profile refresh callback")

    if main_root is not None and _widget_exists(main_root):
        try:
            main_root.after(0, _run_callback)
            return
        except tk.TclError as exc:
            _profile_ui_trace(f"main_root.after TclError: {exc}")

    _run_callback()


def set_profile_manager_close_callback(callback):
    global _on_close_callback
    _on_close_callback = callback


def _profile_manager_is_ready():
    if profile_window is None:
        return False
    try:
        return bool(profile_window.winfo_exists())
    except tk.TclError:
        return False

profile_listbox = None
selected_profile = None
profile_data = {}
display_name_var = None
level_var = None
hp_var = None
mp_var = None
potion_var = None
death_var = None
auto_var = None
enable_elf_var = None
farm_visual_label = None
elf_buff_label = None
bot_mode_var = None
farm_mode_enabled_var = None
kill_bosses_mode_enabled_var = None
farm_mode_frame = None
kill_bosses_mode_frame = None
map_checkbox_vars = None
golden_mobs_var = None
profile_status_label = None


def _format_location_summary(location):
    if not location:
        return "No configurado"
    x = location.get("x")
    y = location.get("y")
    if x is None or y is None:
        coords = "Coordenadas: —"
    else:
        coords = f"Coordenadas: X: {x}, Y: {y}"
    return (
        f"Mapa: {location.get('map', '-')} | "
        f"Wire: {location.get('wire', '-')} | {coords}"
    )


def _mark_profiles_dirty():
    global profiles_dirty
    profiles_dirty = True
    _profile_ui_trace("profiles_dirty=True")


def close_profile_manager(select_filename=None):
    global profiles_dirty
    callback = _on_close_callback
    window = profile_window
    main_root = None

    _profile_ui_trace(
        f"before close_profile_manager select_filename={select_filename!r} "
        f"profiles_dirty={profiles_dirty}"
    )

    if _widget_exists(window):
        try:
            main_root = window.winfo_toplevel()
        except tk.TclError as exc:
            _profile_ui_trace(f"close_profile_manager winfo_toplevel TclError: {exc}")
            main_root = None

        try:
            _profile_ui_trace("before withdraw")
            window.withdraw()
            _profile_ui_trace("after withdraw")
        except tk.TclError as exc:
            _profile_ui_trace(f"withdraw TclError: {exc}")

        if callback is not None and (profiles_dirty or select_filename is not None):
            notify_select = select_filename
            if notify_select is None and selected_profile is not None:
                try:
                    notify_select = selected_profile.get().strip() or None
                except tk.TclError:
                    notify_select = None
            if (
                notify_select
                and profile_file_names
                and notify_select not in profile_file_names
            ):
                notify_select = profile_file_names[0]

            _profile_ui_trace(
                f"close_profile_manager notifying bot_ui select={notify_select!r}"
            )
            _run_close_callback(callback, notify_select, main_root)

        profiles_dirty = False
        _profile_ui_trace("after close_profile_manager (withdrawn, window kept)")
        return

    profiles_dirty = False
    _profile_ui_trace("after close_profile_manager (no window)")
    if callback is not None and select_filename is not None:
        _run_close_callback(callback, select_filename, main_root)


def _present_profile_manager(parent=None, select_filename=None):
    if not _profile_manager_is_ready():
        return False

    window = profile_window
    if parent is not None:
        try:
            window.transient(parent)
        except tk.TclError as exc:
            _profile_ui_trace(f"transient TclError: {exc}")

    current = None
    if selected_profile is not None:
        try:
            current = selected_profile.get().strip()
        except tk.TclError:
            current = None

    reload_target = select_filename or current or None
    _reload_profile_list(select_filename=reload_target)
    _apply_bot_mode_visibility()

    try:
        window.deiconify()
        window.lift()
        window.focus_force()
    except tk.TclError as exc:
        _profile_ui_trace(f"present profile window TclError: {exc}")
        return False

    return True


def _notify_profiles_changed(select_filename=None, *, delay_ms=0):
    callback = _on_close_callback
    if callback is None:
        return

    def _run_callback():
        try:
            callback(select_filename)
        except TypeError:
            callback()

    if not _profile_manager_is_ready():
        _run_callback()
        return

    try:
        profile_window.after(delay_ms, _run_callback)
    except tk.TclError:
        _run_callback()


def _set_profile_status(message, *, is_error=False, is_success=False):
    if not _widget_exists(profile_status_label):
        return
    if is_error:
        fg = "#ef4444"
    elif is_success:
        fg = ACCENT_GREEN
    else:
        fg = TEXT_SECONDARY
    profile_status_label.config(text=message or "", fg=fg)


def _ask_confirm_dialog(title, message, *, confirm_label="Eliminar"):
    parent = profile_window
    if not _profile_manager_is_ready():
        return False

    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)
    configure_window(dialog)
    setup_theme(dialog)

    result = {"value": False}

    content = create_dialog_panel(dialog)
    content.pack(fill=tk.BOTH, expand=True)

    ui_label(
        content,
        message,
        fg=TEXT_SECONDARY,
        wraplength=380,
        justify="left",
    ).pack(anchor="w", pady=(0, PAD_ROW))

    actions = tk.Frame(content, bg=PANEL_BG)
    actions.pack(fill=tk.X)
    actions.grid_columnconfigure(0, weight=1)
    actions.grid_columnconfigure(1, weight=1)

    def close_dialog(confirmed=False):
        result["value"] = confirmed
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        try:
            dialog.destroy()
        except tk.TclError:
            pass

    ttk.Button(
        actions,
        text=confirm_label,
        command=lambda: close_dialog(True),
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ttk.Button(
        actions,
        text="Cancelar",
        command=lambda: close_dialog(False),
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    center_window(dialog, CONFIRM_MODAL_WIDTH, CONFIRM_MODAL_HEIGHT)
    dialog.wait_window()
    return bool(result["value"])


def _ask_profile_display_name(title, prompt, initial="", *, confirm_label="Crear"):
    parent = profile_window
    if parent is None:
        return None

    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)
    configure_window(dialog)
    setup_theme(dialog)

    result = {"value": None}

    content = create_dialog_panel(dialog)
    content.pack(fill=tk.BOTH, expand=True)

    ui_label(content, prompt, fg=TEXT_SECONDARY, wraplength=360, justify="left").pack(
        anchor="w", pady=(0, PAD_ROW)
    )

    name_var = tk.StringVar(value=initial)
    name_entry = create_entry(content, textvariable=name_var, width=36)
    name_entry.pack(fill=tk.X, pady=(0, PAD_ROW))
    _safe_focus_set(name_entry)
    if _widget_exists(name_entry):
        try:
            name_entry.select_range(0, tk.END)
        except tk.TclError as exc:
            _profile_ui_trace(f"select_range TclError: {exc}")

    actions = tk.Frame(content, bg=PANEL_BG)
    actions.pack(fill=tk.X)
    actions.grid_columnconfigure(0, weight=1)
    actions.grid_columnconfigure(1, weight=1)

    def close_dialog(value=None):
        result["value"] = value
        dialog.grab_release()
        dialog.destroy()

    def submit():
        close_dialog(name_var.get().strip())

    name_entry.bind("<Return>", lambda _e: submit())

    ttk.Button(actions, text=confirm_label, command=submit).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    ttk.Button(actions, text="Cancelar", command=lambda: close_dialog(None)).grid(
        row=0, column=1, sticky="ew", padx=(6, 0)
    )

    center_window(dialog, PROFILE_NAME_MODAL_WIDTH, PROFILE_NAME_MODAL_HEIGHT)
    dialog.wait_window()
    return result["value"]


def _profile_window_is_open():
    if profile_window is None:
        return False
    try:
        return bool(profile_window.winfo_exists())
    except tk.TclError:
        return False


def _apply_bot_mode_visibility():
    if farm_mode_frame is None or kill_bosses_mode_frame is None or bot_mode_var is None:
        return

    mode = BOT_MODE_VALUE_BY_LABEL.get(bot_mode_var.get(), "farm")
    if mode == "farm":
        kill_bosses_mode_frame.pack_forget()
        farm_mode_frame.pack(fill=tk.X, pady=(0, PAD_ROW))
    else:
        farm_mode_frame.pack_forget()
        kill_bosses_mode_frame.pack(fill=tk.X, pady=(0, PAD_ROW))


def _load_bot_mode_fields_from_profile():
    if bot_mode_var is None:
        return

    mode = profile_data.get("bot_mode", "farm")
    bot_mode_var.set(BOT_MODE_LABEL_BY_VALUE.get(mode, "Farm"))

    farm_config = profile_data.get("farm_config", {})
    if farm_mode_enabled_var is not None:
        farm_mode_enabled_var.set(bool(farm_config.get("enabled", True)))

    kill_bosses_config = profile_data.get("kill_bosses_config", {})
    if kill_bosses_mode_enabled_var is not None:
        kill_bosses_mode_enabled_var.set(bool(kill_bosses_config.get("enabled", False)))

    if golden_mobs_var is not None:
        golden_mobs_var.set(bool(kill_bosses_config.get("include_golden_mobs", False)))

    if map_checkbox_vars is not None:
        selected_maps = set(profile_data.get("kill_bosses_config", {}).get("maps", []))
        for map_id, var in map_checkbox_vars.items():
            var.set(map_id in selected_maps)


def _apply_bot_mode_fields_to_profile_data():
    mode = BOT_MODE_VALUE_BY_LABEL.get(bot_mode_var.get(), "farm")
    profile_data["bot_mode"] = mode

    farm_config = profile_data.get("farm_config")
    if not isinstance(farm_config, dict):
        farm_config = {}
    if farm_mode_enabled_var is not None:
        farm_config["enabled"] = farm_mode_enabled_var.get()
    elif mode == "farm":
        farm_config["enabled"] = True
    profile_data["farm_config"] = farm_config

    kill_bosses_config = profile_data.get("kill_bosses_config")
    if not isinstance(kill_bosses_config, dict):
        kill_bosses_config = {
            "maps": [],
            "include_golden_mobs": False,
        }
    if kill_bosses_mode_enabled_var is not None:
        kill_bosses_config["enabled"] = kill_bosses_mode_enabled_var.get()
    elif mode == "kill_bosses":
        kill_bosses_config["enabled"] = True

    if mode == "kill_bosses":
        if map_checkbox_vars is not None:
            kill_bosses_config["maps"] = [
                map_id for map_id, var in map_checkbox_vars.items() if var.get()
            ]
        else:
            kill_bosses_config.setdefault("maps", [])
        if golden_mobs_var is not None:
            kill_bosses_config["include_golden_mobs"] = golden_mobs_var.get()
        else:
            kill_bosses_config.setdefault("include_golden_mobs", False)

    profile_data["kill_bosses_config"] = kill_bosses_config


def _clear_profile_form():
    global profile_data

    profile_data = {}
    if not _profile_manager_is_ready():
        return

    selected_profile.set("")
    display_name_var.set("")
    level_var.set("")
    hp_var.set(10)
    mp_var.set(10)
    potion_var.set(True)
    death_var.set(True)
    auto_var.set(True)
    if enable_elf_var is not None:
        enable_elf_var.set(True)
    if bot_mode_var is not None:
        bot_mode_var.set("Farm")
    if farm_mode_enabled_var is not None:
        farm_mode_enabled_var.set(True)
    if kill_bosses_mode_enabled_var is not None:
        kill_bosses_mode_enabled_var.set(False)
    if golden_mobs_var is not None and map_checkbox_vars is not None:
        golden_mobs_var.set(False)
        for var in map_checkbox_vars.values():
            var.set(False)

    if _widget_exists(farm_visual_label):
        farm_visual_label.config(text="No configurado")
    if _widget_exists(elf_buff_label):
        elf_buff_label.config(text="No configurado")

    _apply_bot_mode_visibility()


def refresh_profile_fields():
    _profile_ui_trace("before update_profile_details (refresh_profile_fields)")
    if not _profile_manager_is_ready():
        _profile_ui_trace("after update_profile_details (window not ready)")
        return

    profile_name = selected_profile.get().strip()
    if not profile_name or profile_name not in profile_file_names:
        _profile_ui_trace("after update_profile_details (no valid profile)")
        return

    display_name_var.set(get_display_name(profile_data, profile_name))

    farm_loc = get_farm_spot_location(profile_name)
    if _widget_exists(farm_visual_label):
        farm_visual_label.config(text=_format_location_summary(farm_loc))

    elf_loc = get_elf_buff_location(profile_name)
    if _widget_exists(elf_buff_label):
        elf_buff_label.config(text=_format_location_summary(elf_loc))

    _profile_ui_trace("after update_profile_details (refresh_profile_fields)")


def _load_profile_into_form(profile_name):
    global profile_data

    _profile_ui_trace(
        f"before update_profile_details (_load_profile_into_form) profile={profile_name!r}"
    )
    if not _profile_manager_is_ready():
        _profile_ui_trace("after update_profile_details (_load_profile_into_form, not ready)")
        return

    profile_name = str(profile_name).strip()
    if not profile_name or profile_name not in profile_file_names:
        _profile_ui_trace(
            "after update_profile_details (_load_profile_into_form, invalid filename)"
        )
        return

    try:
        profile_data = normalize_profile_data(
            load_profile(f"profiles/{profile_name}"),
            profile_name,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        log(f"[PROFILE] No se pudo cargar {profile_name}: {exc}")
        _profile_ui_trace(
            f"after update_profile_details (_load_profile_into_form, load error: {exc})"
        )
        return

    selected_profile.set(profile_name)
    _write_current_profile_pointer(profile_name)

    hp_var.set(profile_data["hp_potion_stacks"])
    mp_var.set(profile_data["mp_potion_stacks"])
    character_level = profile_data.get("character_level")
    level_var.set(str(character_level) if character_level is not None else "")
    potion_var.set(profile_data["enable_potion_recovery"])
    death_var.set(profile_data["enable_death_recovery"])
    auto_var.set(profile_data["enable_auto_attack"])
    if enable_elf_var is not None:
        enable_elf_var.set(
            bool(profile_data.get("general_config", {}).get("enable_elf_buff", True))
        )
    _load_bot_mode_fields_from_profile()
    _apply_bot_mode_visibility()
    refresh_profile_fields()
    _profile_ui_trace(
        f"after update_profile_details (_load_profile_into_form) profile={profile_name!r}"
    )


def load_selected_profile(event=None):
    if not _profile_manager_is_ready() or profile_listbox is None:
        return

    selection = profile_listbox.curselection()
    if not selection:
        return

    index = selection[0]
    if index >= len(profile_file_names):
        return

    _load_profile_into_form(profile_file_names[index])


def _reload_profile_list(select_filename=None):
    global profile_entries, profile_file_names

    _profile_ui_trace(
        f"before refresh_profile_list select_filename={select_filename!r}"
    )
    if not _profile_manager_is_ready() or profile_listbox is None:
        _profile_ui_trace("after refresh_profile_list (not ready)")
        return

    listbox = profile_listbox
    if _widget_exists(listbox):
        try:
            listbox.unbind("<<ListboxSelect>>")
        except tk.TclError as exc:
            _profile_ui_trace(f"listbox.unbind TclError: {exc}")

    try:
        profile_entries = list_profile_entries()
        profile_file_names = [entry["filename"] for entry in profile_entries]

        _safe_listbox_delete(listbox, 0, tk.END)
        for entry in profile_entries:
            _safe_listbox_insert(listbox, tk.END, entry["display_name"])

        _safe_listbox_selection_clear(listbox, 0, tk.END)

        if not profile_file_names:
            _clear_profile_form()
            _profile_ui_trace("after refresh_profile_list (empty list)")
            return

        target_index = 0
        if select_filename and select_filename in profile_file_names:
            target_index = profile_file_names.index(select_filename)

        _safe_listbox_selection_set(listbox, target_index)
        _safe_listbox_activate(listbox, target_index)
        _safe_listbox_see(listbox, target_index)
        _load_profile_into_form(profile_file_names[target_index])
    finally:
        if _profile_manager_is_ready() and _widget_exists(listbox):
            try:
                listbox.bind("<<ListboxSelect>>", load_selected_profile)
            except tk.TclError as exc:
                _profile_ui_trace(f"listbox.bind TclError: {exc}")

    _profile_ui_trace("after refresh_profile_list")


def refresh_profile_list(select_filename=None):
    """Safe list reload after profile create/delete/duplicate."""
    _reload_profile_list(select_filename=select_filename)


def _schedule_refresh_after_delete(next_select=None):
    if not _profile_manager_is_ready():
        _profile_ui_trace("skip schedule refresh_profile_list (window not ready)")
        return

    def _deferred_refresh():
        _profile_ui_trace(
            f"deferred refresh_profile_list next_select={next_select!r}"
        )
        refresh_profile_list(select_filename=next_select)

    try:
        profile_window.after(100, _deferred_refresh)
    except tk.TclError as exc:
        _profile_ui_trace(f"after(100) refresh schedule TclError: {exc}")
        refresh_profile_list(select_filename=next_select)


def save_current_profile():
    global profile_data

    selected_profile_filename = selected_profile.get().strip()
    if not selected_profile_filename:
        _set_profile_status("Seleccione un perfil primero.", is_error=True)
        return

    display_text = display_name_var.get().strip()
    if not display_text:
        _set_profile_status("El nombre visible del perfil no puede estar vacío.", is_error=True)
        return

    profile_data = load_profile(f"profiles/{selected_profile_filename}")

    profile_data.setdefault("general_config", {})
    profile_data.setdefault("farm_config", {"enabled": True})
    profile_data.setdefault(
        "kill_bosses_config",
        {
            "enabled": False,
            "maps": [],
            "include_golden_mobs": False,
        },
    )

    profile_data["display_name"] = display_text
    profile_data["hp_potion_stacks"] = hp_var.get()
    profile_data["mp_potion_stacks"] = mp_var.get()

    level_text = level_var.get().strip()
    if level_text:
        try:
            profile_data["character_level"] = int(level_text)
        except ValueError:
            log("[PROFILE] Nivel del personaje inválido, no se guardó")
    elif "character_level" in profile_data:
        del profile_data["character_level"]

    profile_data["enable_potion_recovery"] = potion_var.get()
    profile_data["enable_death_recovery"] = death_var.get()
    profile_data["enable_auto_attack"] = auto_var.get()

    general_config = profile_data["general_config"]
    if not isinstance(general_config, dict):
        general_config = {}
        profile_data["general_config"] = general_config
    if enable_elf_var is not None:
        general_config["enable_elf_buff"] = enable_elf_var.get()

    _apply_bot_mode_fields_to_profile_data()

    profile_data = normalize_profile_data(
        profile_data,
        selected_profile_filename,
    )

    save_profile(profile_data, f"profiles/{selected_profile_filename}")
    log("[PROFILE] Guardado")
    _mark_profiles_dirty()
    _reload_profile_list(select_filename=selected_profile_filename)
    _set_profile_status("Perfil guardado correctamente.", is_success=True)


def open_profile_manager(parent=None):
    global profile_window
    global selected_profile, profile_data
    global profile_listbox
    global display_name_var, level_var, hp_var, mp_var
    global potion_var, death_var, auto_var
    global enable_elf_var, farm_visual_label, elf_buff_label
    global bot_mode_var, farm_mode_enabled_var, kill_bosses_mode_enabled_var
    global farm_mode_frame, kill_bosses_mode_frame
    global map_checkbox_vars, golden_mobs_var
    global profile_status_label

    if _profile_manager_is_ready():
        _profile_ui_trace("reusing profile_window (deiconify)")
        _present_profile_manager(parent=parent)
        return

    window = tk.Toplevel(parent)
    profile_window = window
    window.title("Administrar perfiles")
    configure_window(window)
    setup_theme(window)
    if parent is not None:
        window.transient(parent)

    window.protocol("WM_DELETE_WINDOW", close_profile_manager)

    selected_profile = tk.StringVar(window)
    profile_data = {}

    main = tk.Frame(window, bg=UI_BG)
    main.pack(fill=tk.BOTH, expand=True, padx=PAD_WINDOW, pady=PAD_WINDOW)
    main.grid_columnconfigure(0, weight=1)
    main.grid_rowconfigure(0, weight=1)

    columns = tk.Frame(main, bg=UI_BG)
    columns.grid(row=0, column=0, sticky="nsew")
    columns.grid_columnconfigure(0, weight=0)
    columns.grid_columnconfigure(1, weight=1)
    columns.grid_rowconfigure(0, weight=1)

    left_col = tk.Frame(columns, bg=UI_BG, width=240)
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, PAD_ROW))
    left_col.grid_propagate(False)

    left_body = create_packed_section(left_col, "Perfiles", "👥", accent=ACCENT_BLUE, fill="both")

    profile_listbox = tk.Listbox(
        left_body,
        width=LISTBOX_WIDTH,
        height=14,
        bg=UI_BG,
        fg=TEXT_SECONDARY,
        selectbackground=ACCENT_BLUE,
        selectforeground="#FFFFFF",
        highlightthickness=1,
        highlightbackground=PANEL_BG,
        relief="flat",
        activestyle="none",
    )
    profile_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, PAD_ROW))
    profile_listbox.bind("<<ListboxSelect>>", load_selected_profile)

    left_actions = tk.Frame(left_body, bg=PANEL_BG)
    left_actions.pack(fill=tk.X)

    def create_new_profile():
        display_name = _ask_profile_display_name(
            "Nuevo perfil",
            "Nombre del nuevo perfil",
        )
        if display_name is None:
            return

        try:
            filename = create_profile(display_name)
        except ValueError as exc:
            _set_profile_status(str(exc), is_error=True)
            return

        log(f"[PROFILE] Perfil creado: {filename} ({display_name})")
        _mark_profiles_dirty()
        _reload_profile_list(select_filename=filename)
        _set_profile_status(f"Perfil creado: {display_name}", is_success=True)

    def duplicate_current_profile():
        source_filename = selected_profile.get().strip()
        if not source_filename:
            _set_profile_status("Seleccione un perfil primero.", is_error=True)
            return

        try:
            source_data = load_profile(f"profiles/{source_filename}")
        except (OSError, ValueError) as exc:
            _set_profile_status(str(exc), is_error=True)
            return

        suggested_name = f"{get_display_name(source_data, source_filename)} Copia"
        display_name = _ask_profile_display_name(
            "Duplicar perfil",
            "Nombre del perfil duplicado",
            initial=suggested_name,
            confirm_label="Duplicar",
        )
        if display_name is None:
            return

        try:
            filename = duplicate_profile(source_filename, display_name)
        except (ValueError, FileNotFoundError) as exc:
            _set_profile_status(str(exc), is_error=True)
            return

        log(f"[PROFILE] Perfil duplicado: {source_filename} -> {filename}")
        _mark_profiles_dirty()
        _reload_profile_list(select_filename=filename)
        _set_profile_status(f"Perfil duplicado: {display_name}", is_success=True)

    def delete_current_profile():
        _profile_ui_trace("before delete_current_profile")
        if not _profile_manager_is_ready():
            _profile_ui_trace("after delete_current_profile (window not ready)")
            return

        filename = selected_profile.get().strip()
        if not filename:
            _set_profile_status("Seleccione un perfil primero.", is_error=True)
            return

        try:
            profile_data_for_delete = load_profile(f"profiles/{filename}")
        except (OSError, ValueError) as exc:
            _set_profile_status(str(exc), is_error=True)
            return

        display_name = get_display_name(profile_data_for_delete, filename)
        profiles = list_profiles()

        if len(profiles) == 1:
            if not _ask_confirm_dialog(
                "Eliminar perfil",
                "Este es el último perfil. Si lo eliminas no podrás iniciar el bot "
                "hasta crear otro.\n\n¿Deseas continuar?",
                confirm_label="Eliminar",
            ):
                return

        if not _ask_confirm_dialog(
            "Eliminar perfil",
            f"¿Eliminar perfil {display_name}?",
            confirm_label="Eliminar",
        ):
            return

        remaining = [name for name in profiles if name != filename]
        next_select = remaining[0] if remaining else None

        try:
            _profile_ui_trace("before delete_profile (remove_profile_locations + os.remove)")
            delete_profile(filename)
            _profile_ui_trace("after delete_profile (remove_profile_locations + os.remove)")
        except FileNotFoundError as exc:
            _set_profile_status(str(exc), is_error=True)
            _profile_ui_trace(f"after delete_current_profile (error: {exc})")
            return

        log(f"[PROFILE] Perfil eliminado: {filename} ({display_name})")

        global profile_data
        profile_data = {}
        selected_profile.set("")

        _mark_profiles_dirty()
        _schedule_refresh_after_delete(next_select)
        _set_profile_status("Perfil eliminado correctamente", is_success=True)
        _profile_ui_trace(
            "after delete_current_profile (profile list refresh only, bot_ui on close)"
        )

    create_primary_button(
        left_actions,
        "+ Nuevo",
        create_new_profile,
        pack_options={"fill": "x", "pady": (0, 4)},
    )
    create_primary_button(
        left_actions,
        "Duplicar",
        duplicate_current_profile,
        pack_options={"fill": "x", "pady": (0, 4)},
    )
    create_primary_button(
        left_actions,
        "Eliminar",
        delete_current_profile,
        pack_options={"fill": "x"},
    )

    profile_status_label = ui_label(
        left_body,
        "",
        fg=TEXT_SECONDARY,
        wraplength=220,
        justify="left",
        font=("Segoe UI", 9),
    )
    profile_status_label.pack(fill=tk.X, pady=(PAD_ROW, 0))

    right_col = tk.Frame(columns, bg=UI_BG)
    right_col.grid(row=0, column=1, sticky="nsew")

    right_body = create_packed_section(
        right_col, "Perfil seleccionado", "📋", accent=ACCENT_PURPLE, fill="both"
    )
    right_body.grid_columnconfigure(0, weight=1)

    hp_var = tk.IntVar(window)
    mp_var = tk.IntVar(window)
    level_var = tk.StringVar(window)
    display_name_var = tk.StringVar(window)
    potion_var = tk.BooleanVar(window)
    death_var = tk.BooleanVar(window)
    auto_var = tk.BooleanVar(window)
    enable_elf_var = tk.BooleanVar(window, value=True)

    create_section_title(right_body, "General")
    general_frame = tk.Frame(right_body, bg=PANEL_BG)
    general_frame.pack(fill=tk.X, pady=(0, PAD_ROW))
    general_frame.grid_columnconfigure(1, weight=1)

    ui_label(general_frame, "Nombre visible", fg=TEXT_SECONDARY).grid(
        row=0, column=0, sticky="nw", padx=(0, 12), pady=(0, 3)
    )
    create_entry(
        general_frame,
        textvariable=display_name_var,
        width=32,
        row=0,
        column=1,
        sticky="ew",
        pady=(0, 6),
    )

    ui_label(general_frame, "Nivel PJ", fg=TEXT_SECONDARY).grid(
        row=1, column=0, sticky="nw", padx=(0, 12), pady=(6, 2)
    )
    create_entry(
        general_frame,
        textvariable=level_var,
        width=12,
        row=1,
        column=1,
        sticky="w",
        pady=(6, 6),
    )

    bot_mode_var = tk.StringVar(window, value="Farm")
    create_form_label(
        general_frame,
        "Tipo de bot",
        row=2,
        column=0,
        sticky="w",
        pady=(0, 3),
    )
    bot_mode_select = create_combobox(
        general_frame,
        bot_mode_var,
        values=list(BOT_MODE_LABEL_BY_VALUE.values()),
        width=24,
        row=3,
        column=0,
        columnspan=2,
        sticky="ew",
        pady=(0, PAD_ROW),
    )
    bot_mode_select.bind("<<ComboboxSelected>>", lambda _e: _apply_bot_mode_visibility())

    modes_enabled_frame = tk.Frame(general_frame, bg=PANEL_BG)
    modes_enabled_frame.grid(
        row=4,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(0, PAD_ROW),
    )
    farm_mode_enabled_var = tk.BooleanVar(window, value=True)
    kill_bosses_mode_enabled_var = tk.BooleanVar(window, value=False)
    create_checkbutton(
        modes_enabled_frame,
        "Habilitar modo Farm",
        farm_mode_enabled_var,
    ).pack(anchor="w", pady=(0, 2))
    create_checkbutton(
        modes_enabled_frame,
        "Habilitar modo Kill Bosses",
        kill_bosses_mode_enabled_var,
    ).pack(anchor="w")

    create_section_title(right_body, "Configuración general")
    general_config_frame = tk.Frame(right_body, bg=PANEL_BG)
    general_config_frame.pack(fill=tk.X, pady=(0, PAD_ROW))

    potions_row = tk.Frame(general_config_frame, bg=PANEL_BG)
    potions_row.pack(fill=tk.X, pady=(0, PAD_ROW))

    hp_col = tk.Frame(potions_row, bg=PANEL_BG)
    hp_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, PAD_ROW))
    ui_label(hp_col, "HP stacks", fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 3))
    create_entry(hp_col, textvariable=hp_var, width=10).pack(anchor="w")

    mp_col = tk.Frame(potions_row, bg=PANEL_BG)
    mp_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
    ui_label(mp_col, "MP stacks", fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 3))
    create_entry(mp_col, textvariable=mp_var, width=10).pack(anchor="w")

    potions_options = tk.Frame(general_config_frame, bg=PANEL_BG)
    potions_options.pack(fill=tk.X)
    for label, var in (
        ("Potion Recovery", potion_var),
        ("Death Recovery", death_var),
        ("Auto Attack", auto_var),
    ):
        create_checkbutton(potions_options, label, var).pack(anchor="w", pady=(0, 4))

    create_checkbutton(
        general_config_frame,
        "Elf Buff habilitado",
        enable_elf_var,
    ).pack(anchor="w", pady=(PAD_ROW, PAD_ROW))

    elf_buff_label = ui_label(
        general_config_frame,
        "No configurado",
        fg=TEXT_SECONDARY,
        wraplength=520,
        justify="left",
    )
    elf_buff_label.pack(anchor="w", pady=(0, PAD_ROW))

    def open_elf_buff_config_from_profile():
        profile_filename = selected_profile.get().strip()
        if not profile_filename:
            _set_profile_status("Seleccione un perfil primero.", is_error=True)
            return

        import location_selector_ui

        location_selector_ui.open_location_selector(
            "elf_buff",
            profile_filename,
            on_close=refresh_profile_fields,
        )

    create_primary_button(
        general_config_frame,
        "Configurar Elf Buff",
        open_elf_buff_config_from_profile,
        pack_options={"fill": "x"},
    )

    farm_mode_frame = tk.Frame(right_body, bg=PANEL_BG)

    create_section_title(farm_mode_frame, "Farm")
    farm_frame = tk.Frame(farm_mode_frame, bg=PANEL_BG)
    farm_frame.pack(fill=tk.X, pady=(0, PAD_ROW))

    farm_visual_label = ui_label(
        farm_frame,
        "No configurado",
        fg=TEXT_SECONDARY,
        wraplength=520,
        justify="left",
    )
    farm_visual_label.pack(anchor="w", pady=(0, PAD_ROW))

    def open_farm_spot_config_from_profile():
        profile_filename = selected_profile.get().strip()
        if not profile_filename:
            _set_profile_status("Seleccione un perfil primero.", is_error=True)
            return

        import location_selector_ui

        location_selector_ui.open_location_selector(
            "farm_spot",
            profile_filename,
            on_close=refresh_profile_fields,
        )

    create_primary_button(
        farm_frame,
        "Configurar Farm Spot Visual",
        open_farm_spot_config_from_profile,
        pack_options={"fill": "x"},
    )

    kill_bosses_mode_frame = tk.Frame(right_body, bg=PANEL_BG)

    create_section_title(kill_bosses_mode_frame, "Kill Bosses")
    kill_bosses_body = tk.Frame(kill_bosses_mode_frame, bg=PANEL_BG)
    kill_bosses_body.pack(fill=tk.X)

    ui_label(
        kill_bosses_body,
        "La lógica de Kill Bosses aún está pendiente de implementación.",
        fg=TEXT_SECONDARY,
        font=("Segoe UI", 9),
        wraplength=520,
        justify="left",
    ).pack(anchor="w", pady=(0, PAD_ROW))

    maps_list_frame = tk.Frame(kill_bosses_body, bg=PANEL_BG)
    maps_list_frame.pack(fill=tk.BOTH, expand=False, pady=(0, PAD_ROW))

    maps_canvas = tk.Canvas(
        maps_list_frame,
        bg=UI_BG,
        height=200,
        highlightthickness=1,
        highlightbackground=PANEL_BG,
    )
    maps_scrollbar = tk.Scrollbar(maps_list_frame, orient=tk.VERTICAL, command=maps_canvas.yview)
    maps_inner = tk.Frame(maps_canvas, bg=UI_BG)

    maps_inner.bind(
        "<Configure>",
        lambda _e: maps_canvas.configure(scrollregion=maps_canvas.bbox("all")),
    )
    maps_canvas.create_window((0, 0), window=maps_inner, anchor="nw")
    maps_canvas.configure(yscrollcommand=maps_scrollbar.set)

    maps_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    maps_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    map_checkbox_vars = {}
    for map_entry in list_maps_for_kill_boss_ui():
        var = tk.BooleanVar(window, value=False)
        map_checkbox_vars[map_entry["id"]] = var
        create_checkbutton(
            maps_inner,
            map_entry["name"],
            var,
        ).pack(anchor="w", pady=(0, 2))

    golden_mobs_var = tk.BooleanVar(window, value=False)
    create_checkbutton(
        kill_bosses_body,
        "Incluir mobs dorados",
        golden_mobs_var,
    ).pack(anchor="w")

    right_actions = tk.Frame(right_body, bg=PANEL_BG)
    right_actions.pack(fill=tk.X, pady=(PAD_PANEL, 0))
    right_actions.grid_columnconfigure(0, weight=1)
    right_actions.grid_columnconfigure(1, weight=1)

    create_primary_button(
        right_actions,
        "Guardar",
        save_current_profile,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

    create_primary_button(
        right_actions,
        "Cerrar",
        close_profile_manager,
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    _reload_profile_list()
    _apply_bot_mode_visibility()

    fit_and_center_window(
        window,
        PROFILE_WINDOW_WIDTH,
        PROFILE_WINDOW_HEIGHT,
        min_width=PROFILE_WINDOW_MIN_WIDTH,
        min_height=PROFILE_WINDOW_MIN_HEIGHT,
    )
