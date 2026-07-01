import sys
import threading
from datetime import datetime
from pathlib import Path

from core.path_utils import data_path

subscribers = []
_log_lock = threading.Lock()
_log_file = None
_log_file_path = None


def _resolve_log_file_path():
    return Path(data_path("logs")) / "latest.log"


def init_log_file(*, reset=False):
    global _log_file, _log_file_path

    log_dir = Path(data_path("logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    _log_file_path = log_dir / "latest.log"

    with _log_lock:
        if _log_file is not None:
            try:
                _log_file.close()
            except OSError:
                pass
            _log_file = None

        mode = "w" if reset else "a"
        _log_file = open(_log_file_path, mode, encoding="utf-8", buffering=1)

    return str(_log_file_path)


def get_log_file_path():
    if _log_file_path is None:
        return str(_resolve_log_file_path())
    return str(_log_file_path)


def subscribe(callback):
    subscribers.append(callback)


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    thread_name = threading.current_thread().name
    line = f"{timestamp} [{thread_name}] {message}"

    with _log_lock:
        print(line, flush=True)

        if _log_file is None:
            try:
                init_log_file(reset=False)
            except OSError:
                pass

        if _log_file is not None:
            try:
                _log_file.write(line + "\n")
                _log_file.flush()
            except OSError:
                pass

    for callback in subscribers:
        try:
            callback(message)
        except Exception:
            pass


try:
    init_log_file(reset=False)
except OSError:
    pass
