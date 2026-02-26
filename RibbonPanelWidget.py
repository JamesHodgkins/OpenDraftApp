"""
Ribbon Panel Widget Component.

This module provides a container widget for ribbon panels that displays
a title at the bottom and holds tool content.
"""
from typing import Optional
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt
from ribbon_constants import Styles, MARGINS


class RibbonPanel(QFrame):
    """
    A panel container for the ribbon interface.
    
    Displays a set of tools with a title label at the bottom.
    
    Attributes:
        title: The panel title displayed at the bottom
        content_widget: Widget containing the panel's tools
        dark: Whether to use dark mode styling
    """
    
    def __init__(
        self,
        title: str,
        content_widget: QWidget,
        grid_class: Optional[str] = None,
        parent: Optional[QWidget] = None,
        dark: bool = False
    ):
        """
        Initialize the ribbon panel.
        
        Args:
            title: Panel title to display
            content_widget: Widget containing the panel content
            grid_class: Optional CSS class for grid layout (unused, kept for compatibility)
            parent: Optional parent widget
            dark: Whether to use dark mode styling
        """
        super().__init__(parent)
        self.setObjectName("RibbonPanel")
        self.setProperty("dark", dark)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(*MARGINS.SMALL)
        layout.setSpacing(2)
        
        # Content
        layout.addWidget(content_widget)
        
        # Panel label at the bottom
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        title_label.setProperty("ribbonPanelTitle", True)
        title_label.setProperty("dark", dark)
        title_label.setStyleSheet(Styles.panel_title(dark))
        layout.addWidget(title_label, alignment=Qt.AlignHCenter | Qt.AlignBottom)
        
        self.setLayout(layout)
