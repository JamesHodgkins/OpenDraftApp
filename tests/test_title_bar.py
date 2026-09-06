import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.title_bar import AppFileButton


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def test_app_file_button_can_suppress_reopen_click() -> None:
    _app()
    clicked = []
    btn = AppFileButton()
    btn.clicked.connect(lambda: clicked.append(True))

    btn.suppress_next_click()
    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)

    assert clicked == []
    btn.deleteLater()


def test_app_file_button_next_click_works_after_suppression() -> None:
    _app()
    clicked = []
    btn = AppFileButton()
    btn.clicked.connect(lambda: clicked.append(True))

    btn.suppress_next_click()
    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)

    assert clicked == [True]
    btn.deleteLater()
