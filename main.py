"""
OpenDraft — entry point.

Initialises the Qt application, loads the stylesheet, and shows the main window.
"""
import sys
from pathlib import Path

from typing import Optional, Sequence

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow

# Absolute path to the stylesheet — resolved relative to *this* file so the
# app works regardless of the current working directory at launch time.
_QSS_PATH = Path(__file__).parent / "assets" / "themes" / "ribbon.qss"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Start the OpenDraft Qt application.

    Accepts an argv sequence for testability and `python -m` usage.
    Returns the application's exit code.
    """
    argv = list(argv) if argv is not None else sys.argv
    app = QApplication(argv)

    try:
        app.setStyleSheet(_QSS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Could not load stylesheet: {e}")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
