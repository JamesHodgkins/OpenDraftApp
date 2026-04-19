"""
Ribbon Panel Widget Component.

Provides a labelled container for a single ribbon panel's tool content.
"""
from typing import Optional

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt

from controls.ribbon.ribbon_constants import Styles, MARGINS

__all__ = ["RibbonPanelFrame"]


class RibbonPanelFrame(QFrame):
    """
    A panel container for the ribbon interface.

    Displays a set of tools with a title label at the bottom.

    Args:
        title: Panel title displayed at the bottom.
        content_widget: Widget containing the panel's tools.
        grid_class: Optional CSS class for grid layout (kept for compatibility).
        parent: Optional parent widget.
        dark: Whether to use dark-mode styling.
    """

    def __init__(
        self,
        title: str,
        content_widget: QWidget,
        grid_class: Optional[str] = None,
        parent: Optional[QWidget] = None,
        dark: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("RibbonPanel")
        self.setFrameShape(QFrame.NoFrame)
        self.setProperty("dark", dark)

        layout = QVBoxLayout()
        layout.setContentsMargins(*MARGINS.SMALL)
        layout.setSpacing(0)

        layout.addWidget(content_widget, alignment=Qt.AlignTop)
        layout.addStretch(1)

        title_label = QLabel(title)
        title_label.setFixedHeight(14)
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        title_label.setProperty("ribbonPanelTitle", True)
        title_label.setProperty("dark", dark)
        title_label.setStyleSheet(Styles.panel_title(dark))
        layout.addWidget(title_label, alignment=Qt.AlignHCenter)

        self.setLayout(layout)
