"""
OpenDraft — entry point.

Initialises the Qt application, loads the stylesheet, and shows the main window.
"""
import sys
import ctypes
from pathlib import Path

from typing import Optional, Sequence

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from app.main_window import MainWindow

# Absolute path to the stylesheet — resolved relative to *this* file so the
# app works regardless of the current working directory at launch time.
_QSS_PATH = Path(__file__).parent / "assets" / "themes" / "ribbon.qss"
_ICON_PATH = Path(__file__).parent / "assets" / "svg" / "badge_logo.svg"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Start the OpenDraft Qt application.

    Accepts an argv sequence for testability and `python -m` usage.
    Returns the application's exit code.
    """
    argv = list(argv) if argv is not None else sys.argv

    # Tell Windows this is a distinct app (not "python.exe") so it gets its
    # own taskbar button and shows the correct icon.
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "OpenDraft.CAD.2D.1"
        )

    app = QApplication(argv)
    app.setWindowIcon(QIcon(str(_ICON_PATH)))

    try:
        app.setStyleSheet(_QSS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Could not load stylesheet: {e}")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
