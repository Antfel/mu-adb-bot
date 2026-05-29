import os
import subprocess


def hidden_console_kwargs():
    """Hide console window for subprocess on Windows."""
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {
            "startupinfo": startupinfo,
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }

    return {
        "startupinfo": None,
        "creationflags": 0,
    }
