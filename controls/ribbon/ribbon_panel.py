"""
Main Ribbon Panel Component.

Provides the top-level ribbon widget: a tab bar at the top and a stacked
set of tool-panel rows below, one for each tab.

This module contains **no** application-specific imports.  Document/editor
wiring is handled externally by :class:`~app.ribbon_bridge.RibbonDocumentBridge`.
"""
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QTabBar, QStackedWidget, QComboBox, QPushButton,
    QToolButton, QMenu, QWidgetAction, QSizePolicy, QLabel,
)
from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QPaintEvent, QMouseEvent, QResizeEvent
import logging

_LOG = logging.getLogger(__name__)

from controls.ribbon.ribbon_panel_widget import RibbonPanelFrame
from controls.ribbon.ribbon_factory import PanelFactory, ColorSwatchButton
from controls.ribbon.ribbon_models import RibbonConfiguration, TabDefinition, PanelDefinition
from controls.ribbon.ribbon_constants import SIZE, COLORS, MARGINS

__all__ = ["RibbonPanel"]


class _PanelSeparator(QWidget):
    """A 1-px vertical rule drawn directly via QPainter — no stylesheet involved."""

    def __init__(self, dark: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedWidth(1)
        # Tell Qt we paint every pixel ourselves — prevents parent palette/stylesheet bleed
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        # Both themes currently use #2D2D2D (45,45,45) background.
        # A solid 25-step lighter grey is clearly visible but unobtrusive.
        self._color = QColor(COLORS.SEPARATOR)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), self._color)
        p.end()


class _RibbonTabBar(QTabBar):
    """Borderless ribbon tab bar with custom painting.

    Qt's native tab-bar style can keep drawing outlines on Windows even when
    stylesheets set ``border: none``. Painting the tabs ourselves guarantees
    the top-row ribbon tabs render without borders.
    """

    def __init__(self, dark: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._dark = dark
        self._hovered_index = -1
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideNone)
        self.setUsesScrollButtons(False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        hovered_index = self.tabAt(event.position().toPoint())
        if hovered_index != self._hovered_index:
            self._hovered_index = hovered_index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hovered_index != -1:
            self._hovered_index = -1
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        for index in range(self.count()):
            rect = self.tabRect(index)
            if not rect.isValid():
                continue

            fill = self._tab_fill(index)
            if fill is not None:
                painter.setPen(Qt.NoPen)
                painter.setBrush(fill)
                painter.drawRoundedRect(self._background_rect(index, rect), 0, 0)

            painter.setPen(self._tab_text_color(index))
            painter.drawText(rect, Qt.AlignCenter, self.tabText(index))

        painter.end()

    def _background_rect(self, index: int, rect: QRect) -> QRect:
        if index == self.currentIndex():
            return rect.adjusted(2, 4, -2, 0)
        return rect.adjusted(2, 4, -2, -2)

    def _tab_fill(self, index: int) -> Optional[QColor]:
        if index == self.currentIndex():
            return QColor(COLORS.BACKGROUND_DARK)
        if index == self._hovered_index:
            return QColor(255, 255, 255, 18) if self._dark else QColor(17, 24, 39, 14)
        return None

    def _tab_text_color(self, index: int) -> QColor:
        if index == self.currentIndex():
            return QColor(COLORS.TAB_TEXT_ACTIVE)
        if self._dark:
            return QColor(COLORS.TAB_TEXT_INACTIVE_DARK)
        return QColor(COLORS.TAB_TEXT_INACTIVE_LIGHT)


class _OverflowTabContent(QWidget):
    """Tab content widget that hides panels which overflow and shows a chevron.

    All panels + separators are added to an inner ``QHBoxLayout``.  On each
    ``resizeEvent`` the widget walks the children left-to-right, hiding any
    panel (and its preceding separator) once the accumulated width exceeds
    the available width minus the chevron button width.  Hidden panels are
    accessible via a ``>>`` popup menu.
    """

    _CHEVRON_WIDTH = 24

    def __init__(self, dark: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("RibbonTabContent")
        self.setProperty("dark", dark)
        bg = COLORS.BACKGROUND_DARK if dark else COLORS.BACKGROUND_LIGHT
        self.setStyleSheet(f"QWidget#RibbonTabContent {{ background: {bg}; }}")

        self._inner_layout = QHBoxLayout()
        self._inner_layout.setContentsMargins(*MARGINS.SMALL)
        self._inner_layout.setSpacing(0)

        # Chevron button lives outside the inner layout at the far right.
        self._chevron = QToolButton(self)
        self._chevron.setObjectName("ribbonOverflowChevron")
        self._chevron.setText("\u00bb")  # »
        self._chevron.setFixedWidth(self._CHEVRON_WIDTH)
        self._chevron.setPopupMode(QToolButton.InstantPopup)
        self._chevron.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._chevron.setStyleSheet(
            f"QToolButton {{ border: none; font-size: 14px; color: {COLORS.TAB_TEXT_INACTIVE_DARK}; }}"
            f"QToolButton:hover {{ color: {COLORS.TAB_TEXT_ACTIVE}; background: {COLORS.TAB_HOVER_DARK}; }}"
        )
        self._chevron.hide()

        # Panels + separators tracked in insertion order
        self._items: list[QWidget] = []

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(self._inner_layout)
        outer.addStretch()
        outer.addWidget(self._chevron)
        self.setLayout(outer)

    def add_panel(self, widget: QWidget) -> None:
        """Append a panel (or separator) to the content area."""
        self._items.append(widget)
        self._inner_layout.addWidget(widget)

    # ------------------------------------------------------------------
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self) -> None:
        """Show/hide panels based on available width."""
        available = self.width() - self._CHEVRON_WIDTH - MARGINS.SMALL[0] - MARGINS.SMALL[2]
        used = 0
        overflowed = False
        hidden_panels: list[QWidget] = []

        for item in self._items:
            # Determine the natural width the item wants
            hint = item.sizeHint()
            w = hint.width() if hint.isValid() else item.minimumSizeHint().width()
            if w <= 0:
                w = item.width()

            if not overflowed and (used + w) <= available:
                item.show()
                used += w
            else:
                overflowed = True
                item.hide()
                # Only track real panels, not separators
                if isinstance(item, RibbonPanelFrame):
                    hidden_panels.append(item)

        if hidden_panels:
            self._chevron.show()
            self._build_overflow_menu(hidden_panels)
        else:
            self._chevron.hide()

    def _build_overflow_menu(self, panels: list[QWidget]) -> None:
        """Build a popup showing the hidden panels."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {COLORS.BACKGROUND_DARK}; border: 1px solid {COLORS.MENU_BORDER}; padding: 4px; }}"
        )
        for panel in panels:
            action = QWidgetAction(menu)
            # Extract the panel's title from its QLabel child
            title_label = panel.findChild(QLabel)
            title = title_label.text() if title_label else "Panel"
            btn = QPushButton(title)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {COLORS.TAB_TEXT_ACTIVE}; border: none; "
                f"padding: 6px 16px; text-align: left; font-size: 12px; }}"
                f"QPushButton:hover {{ background: {COLORS.TAB_HOVER_DARK}; }}"
            )
            btn.clicked.connect(menu.close)
            action.setDefaultWidget(btn)
            menu.addAction(action)
        self._chevron.setMenu(menu)


class RibbonPanel(QWidget):
    """
    Main ribbon widget with tabs and tool panels.

    Emits signals for property-control interactions.  Application-level
    wiring (to document/editor) should be done via an external bridge
    — see :class:`~app.ribbon_bridge.RibbonDocumentBridge`.

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

    #: Emitted when the user clicks the colour swatch to request a change.
    colorChangeRequested = Signal()

    #: Emitted when the user picks a new line style from the combo.
    #: Payload is ``""`` for "by layer" or the item text (e.g. ``"Dashed"``).
    lineStyleChanged = Signal(str)

    #: Emitted when the user picks a new line weight from the combo.
    #: Payload is ``""`` for "by layer" or the item text (e.g. ``"0.50 mm"``).
    lineWeightChanged = Signal(str)

    #: Emitted when the user picks a different layer from the combo.
    #: Payload is the layer name string.
    layerChanged = Signal(str)

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
        self.tab_bar = _RibbonTabBar(dark=dark)
        self.tab_bar.setObjectName("RibbonTabBar")
        self.tab_bar.setProperty("dark", dark)
        self.tab_names: List[str] = []
        for tab in ribbon_config.tabs:
            self.tab_bar.addTab(tab.name)
            self.tab_names.append(tab.name)
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

        # Wire property-control signals (internal → public signals)
        self._connect_property_controls()

    # ------------------------------------------------------------------
    # Public API — called by RibbonDocumentBridge (or tests)
    # ------------------------------------------------------------------

    def set_swatch_color(self, color: Optional[str]) -> None:
        """Update all colour-swatch buttons to display *color*.

        Accepts ACI strings (``"aci:N"``) as well as plain ``#rrggbb`` hex.
        Pass ``None`` to show "by layer".
        """
        for btn in self.findChildren(QPushButton, "colorSwatchBtn"):
            if not isinstance(btn, ColorSwatchButton):
                continue
            if color:
                try:
                    # Inline-resolve ACI → hex so the ribbon stays domain-free.
                    # The import is from the ribbon's own factory, not app code.
                    resolved = color
                    if color.startswith("aci:"):
                        # lightweight fallback: leave as-is; bridge already resolves
                        pass
                    btn.set_color(resolved)
                except Exception:
                    btn.set_color(color)
            else:
                btn.set_color(None)

    def set_layer_selection(self, layer_name: Optional[str]) -> None:
        """Select *layer_name* in all layer combos (without emitting signals)."""
        for combo in self._get_layer_combos():
            combo.blockSignals(True)
            if layer_name is not None:
                idx = combo.findText(layer_name)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def set_line_style_selection(self, style: Optional[str]) -> None:
        """Select *style* in all line-style combos (without emitting signals)."""
        for combo in self.findChildren(QComboBox, "lineStyleCombo"):
            combo.blockSignals(True)
            if style is None:
                combo.setCurrentIndex(0)
            else:
                idx = combo.findText(style)
                if idx < 0:
                    idx = combo.findText(style.capitalize())
                combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def set_line_weight_selection(self, weight: Optional[float]) -> None:
        """Select *weight* in all thickness combos (without emitting signals)."""
        for combo in self.findChildren(QComboBox, "thicknessCombo"):
            combo.blockSignals(True)
            if weight is None:
                combo.setCurrentIndex(0)
            else:
                for i in range(1, combo.count()):
                    try:
                        if abs(float(combo.itemText(i).split()[0]) - weight) < 0.001:
                            combo.setCurrentIndex(i)
                            break
                    except (ValueError, IndexError):
                        pass
            combo.blockSignals(False)

    def populate_layers(self, layer_names: List[str], active_layer: Optional[str] = None) -> None:
        """Repopulate all layer-select combos with *layer_names*.

        Call this whenever layers are added, removed or renamed.
        """
        for combo in self._get_layer_combos():
            combo.blockSignals(True)
            combo.clear()
            for name in layer_names:
                combo.addItem(name)
            if active_layer is not None:
                idx = combo.findText(active_layer)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    # Keep refresh_layers as a convenience alias (MainWindow calls it)
    def refresh_layers(self) -> None:
        """Compatibility shim — bridge should call ``populate_layers()``."""
        _LOG.debug("refresh_layers() called without bridge; no-op.")

    # ------------------------------------------------------------------
    # Internal signal wiring
    # ------------------------------------------------------------------

    def _connect_property_controls(self) -> None:
        """Connect factory-built property widgets to the public signals."""
        # Color swatches → colorChangeRequested
        for btn in self.findChildren(QPushButton, "colorSwatchBtn"):
            btn.clicked.connect(self.colorChangeRequested.emit)

        # Line-style combos → lineStyleChanged
        for combo in self.findChildren(QComboBox, "lineStyleCombo"):
            def _style_cb(idx, _c=combo):
                val = "" if idx == 0 else _c.itemText(idx)
                self.lineStyleChanged.emit(val)
            combo.currentIndexChanged.connect(_style_cb)

        # Thickness combos → lineWeightChanged
        for combo in self.findChildren(QComboBox, "thicknessCombo"):
            def _weight_cb(idx, _c=combo):
                val = "" if idx == 0 else _c.itemText(idx)
                self.lineWeightChanged.emit(val)
            combo.currentIndexChanged.connect(_weight_cb)

        # Layer combos → layerChanged
        for combo in self._get_layer_combos():
            combo.currentTextChanged.connect(self.layerChanged.emit)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_layer_combos(self) -> "List[QComboBox]":
        """Return all ``layerSelectCombo`` widgets found in the ribbon."""
        combos: List[QComboBox] = []
        if hasattr(self, "stacked") and self.stacked is not None:
            for i in range(self.stacked.count()):
                page = self.stacked.widget(i)
                if page is None:
                    continue
                c = page.findChild(QComboBox, "layerSelectCombo")
                if c is not None:
                    combos.append(c)
        if not combos:
            c = self.findChild(QComboBox, "layerSelectCombo")
            if c is not None:
                combos.append(c)
        return combos

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_tab_widget(
        self,
        tab: TabDefinition,
        panels: Dict[str, PanelDefinition],
        dark: bool,
    ) -> _OverflowTabContent:
        tab_widget = _OverflowTabContent(dark=dark)

        panel_names = [name for name in tab.panels if name in panels]
        for idx, panel_name in enumerate(panel_names):
            panel_def = panels[panel_name]
            panel_widget = self._build_panel(panel_name, panel_def, dark=dark)
            tab_widget.add_panel(panel_widget)
            # insert a vertical rule between panels (not after last)
            if idx < len(panel_names) - 1:
                tab_widget.add_panel(_PanelSeparator(dark=dark))

        return tab_widget

    def _build_panel(
        self,
        panel_name: str,
        panel_def: PanelDefinition,
        dark: bool = False,
    ) -> RibbonPanelFrame:
        factory = PanelFactory(dark=dark, action_handler=self.actionTriggered.emit)
        content = factory.create_panel_content(panel_def.tools)
        return RibbonPanelFrame(panel_name, content, dark=dark)
