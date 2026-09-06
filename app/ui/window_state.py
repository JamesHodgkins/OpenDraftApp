"""Persisted main-window geometry/state, stored as JSON under the OS app-data
directory (via `QStandardPaths.AppDataLocation`) rather than the registry/
QSettings - keeps window state a plain, inspectable file alongside any other
app data OpenDraft ends up persisting.

`QWidget.saveGeometry()`/`restoreGeometry()` already round-trip maximized/
normal state together with size and position, so all that needs persisting
is that one opaque `QByteArray` (stored here as base64 text for JSON).
"""
import json
import os

from PySide6.QtCore import QByteArray, QStandardPaths

_STATE_FILENAME = "window_state.json"


def _state_file_path() -> str:
    app_data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    return os.path.join(app_data_dir, _STATE_FILENAME)


def load_window_state() -> str | None:
    """Return the last-saved geometry as a base64 string, or None if
    unavailable."""
    path = _state_file_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    geometry = data.get("geometry")
    return geometry if isinstance(geometry, str) else None


def save_window_state(geometry: QByteArray) -> None:
    """Persist the window's `saveGeometry()` result."""
    path = _state_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {"geometry": geometry.toBase64().data().decode("ascii")}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass
