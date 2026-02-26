"""
Icon Widget Component.

Loads an icon from the project's assets/icons directory.
Attempts SVG first, falls back to PNG, then shows a '?' placeholder.
"""
from typing import Optional
import os

from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QSize

# Resolve assets/icons relative to the project root.
# controls/icon_widget.py → controls/ → OpenDraft/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_ICONS_DIR = os.path.join(_PROJECT_ROOT, "assets", "icons")


class Icon(QLabel):
    """
    A QLabel that displays an icon from the project's assets/icons folder.

    Tries <name>.svg first, then <name>.png.  Falls back to a '?' label if
    neither file exists.

    Args:
        name: Icon filename without extension (e.g. ``'file_new'``).
        size: Desired icon size in pixels (minimum 16, default 24).
        parent: Optional parent widget.
    """

    def __init__(self, name: str, size: int = 24, parent: Optional[QWidget] = None):
        super().__init__(parent)

        icon_size = max(16, int(size))
        self.setFixedSize(icon_size, icon_size)

        svg_path = os.path.join(_ICONS_DIR, f"{name}.svg")
        png_path = os.path.join(_ICONS_DIR, f"{name}.png")

        if os.path.exists(svg_path):
            icon = QIcon(svg_path)
            self.setPixmap(icon.pixmap(icon_size, icon_size))
        elif os.path.exists(png_path):
            pixmap = QPixmap(png_path)
            self.setPixmap(pixmap.scaled(icon_size, icon_size))
        else:
            self.setText("?")
            self.setStyleSheet("color: #888; font-size: 16px;")
