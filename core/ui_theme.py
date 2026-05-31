"""Shared visual theme for Tkinter / ttk screens."""

import tkinter as tk
from tkinter import ttk

UI_BG = "#0B0C10"
PANEL_BG = "#111827"
PANEL_BORDER = "#1F2937"
TEXT_PRIMARY = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"
INPUT_BG = "#0D1117"
INPUT_BORDER = "#1F2937"
INPUT_FOCUS = "#3B82F6"
PREVIEW_BG = "#0D1117"

ACCENT_BLUE = "#3B82F6"
ACCENT_PURPLE = "#A855F7"
ACCENT_GREEN = "#22C55E"
ACCENT_PINK = "#EC4899"

BTN_PADDING_X = 12
BTN_PADDING_Y = 8
BTN_TOGGLE_PADDING_Y = 9

PAD_WINDOW = 16
PAD_PANEL = 12
PAD_ROW = 6
LABEL_GAP = 3

COMBO_WIDTH = 32
ENTRY_WIDTH_SHORT = 12
ENTRY_WIDTH_DEFAULT = 30

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

_theme_initialized = False


def setup_theme(root=None):
    global _theme_initialized
    style = ttk.Style(root)
    if not _theme_initialized:
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        _theme_initialized = True

    style.configure(
        "Dark.TCombobox",
        fieldbackground=INPUT_BG,
        background=PANEL_BG,
        foreground=TEXT_PRIMARY,
        arrowcolor=TEXT_PRIMARY,
        bordercolor=INPUT_BORDER,
        lightcolor=INPUT_BORDER,
        darkcolor=INPUT_BORDER,
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", INPUT_BG)],
        foreground=[("readonly", TEXT_PRIMARY)],
    )
    style.configure(
        "TButton",
        font=FONTS["button"],
        padding=(BTN_PADDING_X, BTN_PADDING_Y),
    )
    style.configure(
        "Toggle.TButton",
        font=FONTS["button"],
        padding=(BTN_PADDING_X, BTN_TOGGLE_PADDING_Y),
    )


def configure_window(window, *, bg=None):
    window.configure(bg=bg or UI_BG)


def ui_label(parent, text, *, font=None, fg=None, bg=None, **kwargs):
    return tk.Label(
        parent,
        text=text,
        font=font or FONTS["body"],
        fg=fg or TEXT_PRIMARY,
        bg=bg or PANEL_BG,
        **kwargs,
    )


def create_form_label(parent, text, *, bg=None, **grid):
    label = ui_label(parent, text, fg=TEXT_SECONDARY, bg=bg or PANEL_BG)
    if grid:
        label.grid(**grid)
    return label


def create_entry(parent, textvariable=None, *, width=ENTRY_WIDTH_SHORT, bg=None, **grid):
    entry = tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg=INPUT_BG,
        fg=TEXT_PRIMARY,
        insertbackground=TEXT_PRIMARY,
        relief="flat",
        highlightthickness=1,
        highlightbackground=INPUT_BORDER,
        highlightcolor=INPUT_FOCUS,
    )
    if grid:
        entry.grid(**grid)
    return entry


def create_combobox(parent, textvariable, *, values=None, width=COMBO_WIDTH, **grid):
    combo = ttk.Combobox(
        parent,
        textvariable=textvariable,
        values=values or [],
        state="readonly",
        width=width,
        style="Dark.TCombobox",
    )
    if grid:
        combo.grid(**grid)
    return combo


def create_checkbutton(parent, text, variable, *, bg=None, **grid):
    check = tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        font=FONTS["body"],
        fg=TEXT_PRIMARY,
        bg=bg or PANEL_BG,
        activebackground=bg or PANEL_BG,
        activeforeground=TEXT_PRIMARY,
        selectcolor=INPUT_BG,
        highlightthickness=0,
    )
    if grid:
        check.grid(**grid)
    return check


def create_primary_button(
    parent,
    text,
    command,
    *,
    style="TButton",
    width=None,
    pack_options=None,
    grid_options=None,
):
    opts = {"text": text, "command": command, "style": style}
    if width is not None:
        opts["width"] = width
    button = ttk.Button(parent, **opts)
    if pack_options:
        button.pack(**pack_options)
    if grid_options:
        button.grid(**grid_options)
    return button


def _build_section_shell(parent, title, icon, *, accent=None, fill="x"):
    if fill == "both":
        outer = tk.Frame(parent, bg=PANEL_BORDER)
        outer.pack(fill=tk.BOTH, expand=True)
    else:
        outer = tk.Frame(parent, bg=PANEL_BORDER)
        outer.pack(fill=tk.X, pady=(0, PAD_ROW))

    inner = tk.Frame(outer, bg=PANEL_BG)
    inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    header = tk.Frame(inner, bg=PANEL_BG)
    header.pack(fill=tk.X, padx=PAD_PANEL, pady=(10, 6))

    ui_label(
        header,
        icon,
        font=FONTS["icon"],
        fg=accent or ACCENT_BLUE,
    ).pack(side=tk.LEFT)
    ui_label(
        header,
        title.upper(),
        font=FONTS["section"],
        fg=TEXT_SECONDARY,
    ).pack(side=tk.LEFT, padx=(8, 0))

    body = tk.Frame(inner, bg=PANEL_BG)
    body.pack(fill=tk.BOTH, expand=True, padx=PAD_PANEL, pady=(0, 10))
    return body


def create_packed_section(parent, title, icon, *, accent=None, fill="x"):
    """Section panel for standalone windows (pack layout)."""
    return _build_section_shell(parent, title, icon, accent=accent, fill=fill)


def create_section_frame(
    parent,
    title,
    icon,
    *,
    row=0,
    column=0,
    columnspan=1,
    sticky="nsew",
    accent=None,
    padx=None,
):
    """Section panel for grid layout (main bot dashboard)."""
    outer = tk.Frame(parent, bg=PANEL_BORDER)
    outer.grid(
        row=row,
        column=column,
        columnspan=columnspan,
        sticky=sticky,
        padx=padx if padx is not None else (0 if column == 0 else 6, 0),
        pady=0,
    )

    inner = tk.Frame(outer, bg=PANEL_BG)
    inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    header = tk.Frame(inner, bg=PANEL_BG)
    header.pack(fill=tk.X, padx=PAD_PANEL, pady=(10, 6))

    ui_label(
        header,
        icon,
        font=FONTS["icon"],
        fg=accent or ACCENT_BLUE,
    ).pack(side=tk.LEFT)
    ui_label(
        header,
        title.upper(),
        font=FONTS["section"],
        fg=TEXT_SECONDARY,
    ).pack(side=tk.LEFT, padx=(8, 0))

    body = tk.Frame(inner, bg=PANEL_BG)
    body.pack(fill=tk.X, padx=PAD_PANEL, pady=(0, 10))
    return body


def create_dialog_panel(parent, *, padx=24, pady=20):
    """Content area for modal dialogs."""
    return tk.Frame(parent, bg=PANEL_BG, padx=padx, pady=pady)


def create_section_title(parent, title, *, bg=None):
    """Uppercase subsection heading inside a panel body."""
    row = tk.Frame(parent, bg=bg or PANEL_BG)
    row.pack(fill=tk.X, pady=(PAD_ROW, LABEL_GAP))
    ui_label(
        row,
        title.upper(),
        font=FONTS["section"],
        fg=TEXT_SECONDARY,
        bg=bg or PANEL_BG,
    ).pack(side=tk.LEFT)
    return row


def add_labeled_field(parent, label_text, widget, *, row, pady_bottom=PAD_ROW):
    create_form_label(
        parent,
        label_text,
        row=row,
        column=0,
        sticky="w",
        pady=(0, LABEL_GAP),
    )
    widget.grid(row=row + 1, column=0, sticky="ew", pady=(0, pady_bottom))
    parent.grid_columnconfigure(0, weight=1)
