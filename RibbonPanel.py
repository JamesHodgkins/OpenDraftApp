"""
Main Ribbon Panel Component.

This module provides the main ribbon interface with tabs and panels.
"""
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
    QTabBar, QStackedWidget, QLabel
)
from PySide6.QtCore import Qt
from DrawRibbonPanel import DrawRibbonPanel
from RibbonPanelWidget import RibbonPanel as RibbonPanelWidget
from panel_factory import create_panel_widget
from RibbonSplitButton import RibbonSplitButton
from IconWidget import Icon
from ribbon_constants import SIZE, COLORS, MARGINS


class RibbonPanel(QWidget):
    """
    Main ribbon panel widget with tabs and tool panels.
    
    Provides a tabbed interface where each tab contains multiple tool panels.
    
    Attributes:
        ribbon_structure: List of tab definitions
        panel_definitions: Dictionary of panel definitions by name
        dark: Whether to use dark mode styling
    """
    
    def __init__(
        self,
        ribbon_structure: List[Dict[str, Any]],
        panel_definitions: Dict[str, Dict[str, Any]],
        parent: Optional[QWidget] = None,
        dark: bool = False
    ):
        """
        Initialize the ribbon panel.
        
        Args:
            ribbon_structure: List of dictionaries defining tabs and their panels
            panel_definitions: Dictionary mapping panel names to their tool definitions
            parent: Optional parent widget
            dark: Whether to use dark mode styling
        """
        super().__init__(parent)
        self.setObjectName("RibbonPanel")
        self.setFixedHeight(SIZE.RIBBON_HEIGHT)
        self.setProperty("dark", dark)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(*MARGINS.NONE)
        main_layout.setSpacing(0)

        # Tabs along the top
        self.tab_bar = QTabBar()
        self.tab_names = []
        for tab in ribbon_structure:
            self.tab_bar.addTab(tab["name"])
            self.tab_names.append(tab["name"])
        self.tab_bar.setExpanding(False)
        main_layout.addWidget(self.tab_bar)

        # Stacked widget for ribbon content
        self.stacked = QStackedWidget()
        for tab in ribbon_structure:
            tab_widget = self._create_tab_widget(tab, panel_definitions, dark)
            self.stacked.addWidget(tab_widget)
        main_layout.addWidget(self.stacked)

        self.tab_bar.currentChanged.connect(self.stacked.setCurrentIndex)
        self.setLayout(main_layout)
    
    def _create_tab_widget(
        self,
        tab: Dict[str, Any],
        panel_definitions: Dict[str, Dict[str, Any]],
        dark: bool
    ) -> QWidget:
        """
        Create a widget for a single tab containing its panels.
        
        Args:
            tab: Tab definition with name and panel list
            panel_definitions: Dictionary of all panel definitions
            dark: Whether to use dark mode
            
        Returns:
            QWidget containing all panels for the tab
        """
        tab_widget = QWidget()
        tab_widget.setProperty("dark", dark)
        background_color = COLORS.BACKGROUND_DARK if dark else COLORS.BACKGROUND_LIGHT
        tab_widget.setStyleSheet(f"background: {background_color};")
        
        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(*MARGINS.SMALL)
        tab_layout.setSpacing(SIZE.PANEL_SPACING)
        
        for panel_name in tab["panels"]:
            panel_def = panel_definitions.get(panel_name)
            if panel_def:
                panel_widget = self._build_panel(panel_name, panel_def, dark=dark)
                tab_layout.addWidget(panel_widget)
        
        tab_layout.addStretch()
        tab_widget.setLayout(tab_layout)
        return tab_widget

    def _build_panel(
        self,
        panel_name: str,
        panel_def: Dict[str, Any],
        dark: bool = False
    ) -> RibbonPanelWidget:
        """
        Build a panel widget from its definition.
        
        Args:
            panel_name: Name of the panel
            panel_def: Panel definition dictionary
            dark: Whether to use dark mode
            
        Returns:
            RibbonPanelWidget containing the panel's tools
        """
        return create_panel_widget(panel_name, panel_def, dark=dark)

    def _file_tab(self):
        w = QWidget()
        l = QHBoxLayout()
        l.addWidget(QPushButton("New"))
        l.addWidget(QPushButton("Open"))
        l.addWidget(QPushButton("Save"))
        l.addWidget(QPushButton("Export"))
        l.addStretch()
        w.setLayout(l)
        return w

    def _home_tab(self):
        w = QWidget()
        l = QHBoxLayout()
        l.addWidget(QPushButton("Select"))
        l.addWidget(QPushButton("Move"))
        l.addWidget(QPushButton("Copy"))
        l.addWidget(QPushButton("Paste"))
        l.addStretch()
        w.setLayout(l)
        return w

    def _draw_tab(self):
        # Use the new DrawRibbonPanel for the Draw tab
        return DrawRibbonPanel()

    def _modify_tab(self):
        w = QWidget()
        l = QHBoxLayout()
        l.addWidget(QPushButton("Erase"))
        l.addWidget(QPushButton("Trim"))
        l.addWidget(QPushButton("Extend"))
        l.addWidget(QPushButton("Offset"))
        l.addStretch()
        w.setLayout(l)
        return w

    def _view_tab(self):
        w = QWidget()
        l = QHBoxLayout()
        l.addWidget(QPushButton("Zoom In"))
        l.addWidget(QPushButton("Zoom Out"))
        l.addWidget(QPushButton("Pan"))
        l.addWidget(QPushButton("Fit to View"))
        l.addStretch()
        w.setLayout(l)
        return w
