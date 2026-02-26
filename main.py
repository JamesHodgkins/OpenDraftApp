"""
OpenDraft — entry point.

Initialises the Qt application, loads the stylesheet, and shows the main window.
"""
import sys

from typing import Optional, Sequence

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Start the OpenDraft Qt application.

    Accepts an argv sequence for testability and `python -m` usage.
    Returns the application's exit code.
    """
    argv = list(argv) if argv is not None else sys.argv
    app = QApplication(argv)

    try:
        with open("assets/themes/ribbon.qss", "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"Could not load stylesheet: {e}")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
