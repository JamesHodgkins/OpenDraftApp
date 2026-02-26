
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QSize
import os

class Icon(QLabel):
    def __init__(self, name, size=24, parent=None):
        super().__init__(parent)
        # Ensure size is always positive and reasonable
        icon_size = max(16, int(size))
        self.setFixedSize(icon_size, icon_size)
        # Look for SVG first, then PNG
        base_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons')
        svg_path = os.path.join(base_path, f'{name}.svg')
        png_path = os.path.join(base_path, f'{name}.png')
        if os.path.exists(svg_path):
            icon = QIcon(svg_path)
            self.setPixmap(icon.pixmap(icon_size, icon_size))
        elif os.path.exists(png_path):
            pixmap = QPixmap(png_path)
            self.setPixmap(pixmap.scaled(icon_size, icon_size))
        else:
            self.setText('?')
            self.setStyleSheet('color: #888; font-size: 16px;')
