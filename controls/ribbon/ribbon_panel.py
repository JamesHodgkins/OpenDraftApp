"""
Main Ribbon Panel Component.

Provides the top-level ribbon widget: a tab bar at the top and a stacked
set of tool-panel rows below, one for each tab.
"""
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QTabBar, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor

from controls.ribbon.ribbon_panel_widget import RibbonPanel as RibbonPanelWidget
from controls.ribbon.ribbon_factory import PanelFactory
from controls.ribbon.ribbon_models import RibbonConfiguration, TabDefinition, PanelDefinition
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
        ribbon_config: Typed :class:`~controls.ribbon.ribbon_models.RibbonConfiguration`
                       describing the full tab/panel/tool layout.
        parent: Optional parent widget.
        dark: Whether to apply dark-mode styling.
    """

    #: Emitted whenever any ribbon button is clicked.  The payload is the
    #: ``action`` string from the button's tool definition (e.g.
    #: ``"lineCommand"``).
    actionTriggered = Signal(str)

    def __init__(
        self,
        ribbon_config: RibbonConfiguration,
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
        for tab in ribbon_config.tabs:
            self.tab_bar.addTab(tab.name)
            self.tab_names.append(tab.name)
        self.tab_bar.setExpanding(False)
        main_layout.addWidget(self.tab_bar)

        # Stacked content area
        self.stacked = QStackedWidget()
        for tab in ribbon_config.tabs:
            self.stacked.addWidget(
                self._create_tab_widget(tab, ribbon_config.panels, dark)
            )
        main_layout.addWidget(self.stacked)

        self.tab_bar.currentChanged.connect(self.stacked.setCurrentIndex)
        self.setLayout(main_layout)

        # Held after setup_document() for refresh_layers()
        self._document = None

    # ------------------------------------------------------------------
    # Document wiring
    # ------------------------------------------------------------------

    def setup_document(self, doc) -> None:
        """Wire live document data to the Properties-panel controls.

        Must be called after the ribbon is fully constructed (e.g. from
        ``MainWindow.__init__``).  Safe to call multiple times.

        Parameters
        ----------
        doc:
            The application :class:`~app.document.DocumentStore`.
        """
        self._document = doc
        self.refresh_layers()

        # ── color swatch ─────────────────────────────────────────────
        btn = self.findChild(object, "colorSwatchBtn")
        if btn is not None:
            from PySide6.QtWidgets import QColorDialog
            def _pick_color(*, _doc=doc, _btn=btn):
                start = _doc.active_color or "#ffffff"
                from PySide6.QtGui import QColor
                c = QColorDialog.getColor(QColor(start), self, "Override colour")
                if c.isValid():
                    _doc.active_color = c.name()
                    _btn.setStyleSheet(
                        f"QPushButton {{ background: {c.name()}; border: 1px solid #666; "
                        "border-radius: 2px; }"
                        "QPushButton:hover { border-color: #aaa; }"
                    )
            btn.clicked.connect(_pick_color)

        # ── line-style combo ─────────────────────────────────────────
        style_combo = self.findChild(object, "lineStyleCombo")
        if style_combo is not None:
            def _style_changed(idx, *, _doc=doc, _combo=style_combo):
                if idx == 0:
                    _doc.active_line_style = None
                else:
                    _doc.active_line_style = _combo.itemText(idx).lower()
            style_combo.currentIndexChanged.connect(_style_changed)

        # ── thickness combo ───────────────────────────────────────────
        thick_combo = self.findChild(object, "thicknessCombo")
        if thick_combo is not None:
            def _thick_changed(idx, *, _doc=doc, _combo=thick_combo):
                if idx == 0:
                    _doc.active_thickness = None
                else:
                    try:
                        val = float(_combo.itemText(idx).split()[0])
                        _doc.active_thickness = val
                    except (ValueError, IndexError):
                        _doc.active_thickness = None
            thick_combo.currentIndexChanged.connect(_thick_changed)

    def refresh_layers(self) -> None:
        """Repopulate the layer-select combo from the current document.

        Call this whenever layers are added, removed or renamed.
        """
        doc = self._document
        if doc is None:
            return
        combo = self.findChild(object, "layerSelectCombo")
        if combo is None:
            return
        combo.blockSignals(True)
        combo.clear()
        for layer in doc.layers:
            combo.addItem(layer.name)
        # Restore current selection
        idx = combo.findText(doc.active_layer)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)

        # Connect once – store the slot on the widget so multiple calls to
        # refresh_layers() don't stack up duplicate connections.
        if not hasattr(combo, "_layer_slot"):
            def _slot(name, _doc=doc):
                _doc.active_layer = name
            combo._layer_slot = _slot
            combo.currentTextChanged.connect(_slot)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_tab_widget(
        self,
        tab: TabDefinition,
        panels: Dict[str, PanelDefinition],
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

        panel_names = [name for name in tab.panels if name in panels]
        for idx, panel_name in enumerate(panel_names):
            panel_def = panels[panel_name]
            panel_widget = self._build_panel(panel_name, panel_def, dark=dark)
            tab_layout.addWidget(panel_widget)
            # insert a vertical rule between panels (not after last)
            if idx < len(panel_names) - 1:
                tab_layout.addWidget(_PanelSeparator(dark=dark))

        tab_layout.addStretch()
        tab_widget.setLayout(tab_layout)
        return tab_widget

    def _build_panel(
        self,
        panel_name: str,
        panel_def: PanelDefinition,
        dark: bool = False,
    ) -> RibbonPanelWidget:
        factory = PanelFactory(dark=dark, action_handler=self.actionTriggered.emit)
        content = factory.create_panel_content(panel_def.tools)
        return RibbonPanelWidget(panel_name, content, dark=dark)
