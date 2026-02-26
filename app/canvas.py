"""
CAD Canvas widget — the main drawing surface.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import Qt


class CADCanvas(QWidget):
    """Simple paint canvas for 2-D CAD geometry."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)
        # Example: draw a simple line
        painter.drawLine(100, 100, 300, 300)
