def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


def fit_and_center_window(
    window,
    initial_width,
    initial_height,
    *,
    min_width=900,
    min_height=650,
):
    """Size window to fit content, then center on screen."""
    window.update_idletasks()
    req_width = window.winfo_reqwidth()
    req_height = window.winfo_reqheight()
    width = max(initial_width, req_width, min_width)
    height = max(initial_height, req_height, min_height)
    window.minsize(min_width, min_height)
    center_window(window, width, height)
