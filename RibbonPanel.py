

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QTabBar, QStackedWidget, QLabel
from PySide6.QtCore import Qt
from DrawRibbonPanel import DrawRibbonPanel
from RibbonPanelWidget import RibbonPanel as RibbonPanelWidget
from panel_factory import create_panel_widget
from RibbonSplitButton import RibbonSplitButton
from IconWidget import Icon


class RibbonPanel(QWidget):
    def __init__(self, ribbon_structure, panel_definitions, parent=None, dark=False):
        super().__init__(parent)
        self.setObjectName("RibbonPanel")
        self.setFixedHeight(140)
        self.setProperty("dark", dark)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
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
            tab_widget = QWidget()
            tab_widget.setProperty("dark", dark)
            tab_widget.setStyleSheet("background: #2D2D2D;")
            tab_layout = QHBoxLayout()
            tab_layout.setContentsMargins(2, 2, 2, 2)
            tab_layout.setSpacing(6)
            for panel_name in tab["panels"]:
                panel_def = panel_definitions.get(panel_name)
                if panel_def:
                    panel_widget = self._build_panel(panel_name, panel_def, dark=dark)
                    tab_layout.addWidget(panel_widget)
            tab_layout.addStretch()
            tab_widget.setLayout(tab_layout)
            self.stacked.addWidget(tab_widget)
        main_layout.addWidget(self.stacked)

        self.tab_bar.currentChanged.connect(self.stacked.setCurrentIndex)
        self.setLayout(main_layout)

    def _build_panel(self, panel_name, panel_def, dark=False):
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
