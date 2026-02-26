"""
Icon Widget Component.

This module provides a widget for loading and displaying icons from SVG or PNG files.
"""
from typing import Optional
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QSize
import os


class Icon(QLabel):
    """
    A label widget that displays an icon from a file.
    
    Attempts to load SVG files first, falls back to PNG if SVG not found.
    Displays a placeholder '?' if no icon file is found.
    
    Attributes:
        name: The icon name (without extension)
        size: The desired size of the icon in pixels
    """
    
    def __init__(self, name: str, size: int = 24, parent: Optional[QWidget] = None):
        """
        Initialize the icon widget.
        
        Args:
            name: Icon filename without extension (e.g., 'file_new')
            size: Size of the icon in pixels (default: 24)
            parent: Optional parent widget
        """
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
            # Placeholder for missing icon
            self.setText('?')
            self.setStyleSheet('color: #888; font-size: 16px;')
