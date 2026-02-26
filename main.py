"""
OpenDraft — entry point.

Initialises the Qt application, loads the stylesheet, and shows the main window.
"""
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    try:
        with open("assets/themes/ribbon.qss", "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"Could not load stylesheet: {e}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
