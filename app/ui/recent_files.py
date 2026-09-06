"""Persisted "recent files" list, stored as JSON under the OS app-data
directory (via `QStandardPaths.AppDataLocation`) alongside window state -
see `app.ui.window_state` for the same pattern.
"""
import json
import os

from PySide6.QtCore import QStandardPaths

_STATE_FILENAME = "recent_files.json"
_MAX_ENTRIES = 10


def _state_file_path() -> str:
    app_data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    return os.path.join(app_data_dir, _STATE_FILENAME)


def load_recent_files() -> list[str]:
    """Return the persisted recent-file paths, most-recent first.

    Entries that no longer exist on disk are silently dropped.
    """
    path = _state_file_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("recent")
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, str) and os.path.isfile(e)]


def add_recent_file(file_path: str) -> list[str]:
    """Record *file_path* as the most-recently-used file and persist the
    resulting list. Returns the updated list."""
    entries = load_recent_files()
    entries = [e for e in entries if e != file_path]
    entries.insert(0, file_path)
    entries = entries[:_MAX_ENTRIES]

    path = _state_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"recent": entries}, f)
    except OSError:
        pass
    return entries
