"""
Main Ribbon Panel Component.

Provides the top-level ribbon widget: a tab bar at the top and a stacked
set of tool-panel rows below, one for each tab.
"""
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QTabBar, QStackedWidget, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor

from controls.ribbon.ribbon_panel_widget import RibbonPanel as RibbonPanelWidget
from controls.ribbon.panel_factory import create_panel_widget
from controls.ribbon.ribbon_split_button import RibbonSplitButton
from controls.icon_widget import Icon
from controls.ribbon.ribbon_constants import SIZE, COLORS, MARGINS


class _PanelSeparator(QWidget):
    """A 1-px vertical rule drawn directly via QPainter — no stylesheet involved."""

    def __init__(self, dark: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedWidth(1)
        # Tell Qt we paint every pixel ourselves — prevents parent palette/stylesheet bleed
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        # Both themes currently use #2D2D2D (45,45,45) background.
        # A solid 25-step lighter grey is clearly visible but unobtrusive.
        self._color = QColor(70, 70, 70)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), self._color)
        p.end()


class RibbonPanel(QWidget):
    """
    Main ribbon widget with tabs and tool panels.

    Args:
        ribbon_structure: List of tab definitions, each a dict with ``'name'``
                          and ``'panels'`` (list of panel-name strings).
        panel_definitions: Mapping of panel name → panel definition dict.
        parent: Optional parent widget.
        dark: Whether to apply dark-mode styling.
    """

    #: Emitted whenever any ribbon button is clicked.  The payload is the
    #: ``action`` string from the button's tool definition (e.g.
    #: ``"lineCommand"``).
    actionTriggered = Signal(str)

    def __init__(
        self,
        ribbon_structure: List[Dict[str, Any]],
        panel_definitions: Dict[str, Dict[str, Any]],
        parent: Optional[QWidget] = None,
        dark: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("RibbonPanel")
        self.setFixedHeight(SIZE.RIBBON_HEIGHT)
        self.setProperty("dark", dark)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(*MARGINS.NONE)
        main_layout.setSpacing(0)

        # Tab bar
        self.tab_bar = QTabBar()
        self.tab_names: List[str] = []
        for tab in ribbon_structure:
            self.tab_bar.addTab(tab["name"])
            self.tab_names.append(tab["name"])
        self.tab_bar.setExpanding(False)
        main_layout.addWidget(self.tab_bar)

        # Stacked content area
        self.stacked = QStackedWidget()
        for tab in ribbon_structure:
            self.stacked.addWidget(
                self._create_tab_widget(tab, panel_definitions, dark)
            )
        main_layout.addWidget(self.stacked)

        self.tab_bar.currentChanged.connect(self.stacked.setCurrentIndex)
        self.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_tab_widget(
        self,
        tab: Dict[str, Any],
        panel_definitions: Dict[str, Dict[str, Any]],
        dark: bool,
    ) -> QWidget:
        tab_widget = QWidget()
        tab_widget.setObjectName("RibbonTabContent")
        tab_widget.setProperty("dark", dark)
        bg = COLORS.BACKGROUND_DARK if dark else COLORS.BACKGROUND_LIGHT
        # Use objectName selector so this rule does NOT bleed into child widgets
        tab_widget.setStyleSheet(f"QWidget#RibbonTabContent {{ background: {bg}; }}")

        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(*MARGINS.SMALL)
        # spacing will be provided by the separator line rather than layout gaps
        tab_layout.setSpacing(0)

        panels = [name for name in tab["panels"] if panel_definitions.get(name)]
        for idx, panel_name in enumerate(panels):
            panel_def = panel_definitions.get(panel_name)
            panel_widget = self._build_panel(panel_name, panel_def, dark=dark)
            tab_layout.addWidget(panel_widget)
            # insert a vertical rule between panels (not after last)
            if idx < len(panels) - 1:
                tab_layout.addWidget(_PanelSeparator(dark=dark))

        tab_layout.addStretch()
        tab_widget.setLayout(tab_layout)
        return tab_widget

    def _build_panel(
        self,
        panel_name: str,
        panel_def: Dict[str, Any],
        dark: bool = False,
    ) -> RibbonPanelWidget:
        return create_panel_widget(
            panel_name,
            panel_def,
            action_handler=self.actionTriggered.emit,
            dark=dark,
        )
