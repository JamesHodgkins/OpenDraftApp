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
    QToolButton, QSizePolicy, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint, QTimer
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

    def __init__(self, dark: bool = False, parent: Optional[QWidget] = None):
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


class _PanelPopup(QFrame):
    """Frameless popup that displays a single hidden ribbon panel."""

    def __init__(
        self,
        panel: RibbonPanelFrame,
        owner: "_OverflowTabContent",
        dark: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("RibbonPanelPopup")
        self._panel = panel
        self._owner = owner

        bg = COLORS.BACKGROUND_DARK if dark else COLORS.BACKGROUND_LIGHT
        self.setStyleSheet(
            f"QFrame#RibbonPanelPopup {{ background: {bg}; "
            f"border: 1px solid {COLORS.MENU_BORDER}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        panel.setParent(self)
        panel.show()
        layout.addWidget(panel)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._panel.setParent(self._owner)
        self._panel.hide()
        self._owner._active_popup = None
        super().closeEvent(event)
        QTimer.singleShot(0, self._owner._restore_and_reflow)


class _OverflowTabContent(QWidget):
    """Tab content widget with responsive overflow handling.

    Panels that don't fit the available width are hidden and replaced by
    compact *condensed buttons* — one per hidden panel.  Clicking a
    condensed button opens a popup displaying that panel's full tool
    content.
    """

    def __init__(self, dark: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("RibbonTabContent")
        self.setProperty("dark", dark)
        bg = COLORS.BACKGROUND_DARK if dark else COLORS.BACKGROUND_LIGHT
        self.setStyleSheet(f"QWidget#RibbonTabContent {{ background: {bg}; }}")
        self._dark = dark

        self._inner_layout = QHBoxLayout()
        self._inner_layout.setContentsMargins(*MARGINS.SMALL)
        self._inner_layout.setSpacing(0)

        # Overflow area: one condensed button per hidden panel
        self._overflow_widget = QWidget()
        self._overflow_widget.setObjectName("RibbonOverflowArea")
        self._overflow_layout = QHBoxLayout()
        self._overflow_layout.setContentsMargins(4, 0, 2, 0)
        self._overflow_layout.setSpacing(2)
        self._overflow_widget.setLayout(self._overflow_layout)
        self._overflow_widget.hide()

        # Panels + separators tracked in insertion order
        self._items: list[QWidget] = []
        self._condensed_buttons: list[QToolButton] = []
        self._active_popup: Optional[_PanelPopup] = None

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(self._inner_layout)
        outer.addStretch()
        outer.addWidget(self._overflow_widget)
        self.setLayout(outer)

        # Debounced reflow — coalesces rapid resize events
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(0)
        self._reflow_timer.timeout.connect(self._reflow)

    def add_panel(self, widget: QWidget) -> None:
        """Append a panel (or separator) to the content area."""
        self._items.append(widget)
        self._inner_layout.addWidget(widget)

    # ------------------------------------------------------------------
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._active_popup:
            self._active_popup.close()
        else:
            self._reflow_timer.start()

    # ------------------------------------------------------------------
    # Overflow logic
    # ------------------------------------------------------------------

    def _reflow(self) -> None:
        """Show/hide panels and create condensed buttons for hidden ones.

        Overflow is right-to-left: the rightmost panel loses tools first.
        When it can't shrink further it becomes a condensed button, then
        the next panel starts losing tools, etc.
        """
        # Clear previous condensed buttons
        for btn in self._condensed_buttons:
            btn.setParent(None)
            btn.deleteLater()
        self._condensed_buttons.clear()
        self._overflow_widget.hide()

        available = self.width() - MARGINS.SMALL[0] - MARGINS.SMALL[2]

        # Gather panels in order with their natural widths
        panels: list[tuple[int, RibbonPanelFrame]] = []
        sep_indices: list[int] = []
        natural_widths: dict[int, int] = {}

        for i, item in enumerate(self._items):
            if isinstance(item, RibbonPanelFrame):
                panels.append((i, item))
                natural_widths[i] = item.natural_width()
            elif isinstance(item, _PanelSeparator):
                sep_indices.append(i)

        if not panels:
            return

        # Determine which panels fit, working right-to-left.
        # Start by computing what we need for all panels + separators.
        hidden_indices: set[int] = set()

        def _visible_panels() -> list[int]:
            return sorted(i for i, _ in panels if i not in hidden_indices)

        def _sep_width(vis: list[int]) -> int:
            total = 0
            for si in sep_indices:
                has_left = any(pi < si for pi in vis)
                has_right = any(pi > si for pi in vis)
                if has_left and has_right:
                    total += 1
            return total

        # First pass: determine which panels must be fully hidden as
        # condensed buttons (right-to-left).
        # Reserve space for condensed buttons as we hide panels.
        condensed_space = 0
        while True:
            vis = _visible_panels()
            if not vis:
                break
            total_needed = (
                sum(natural_widths[i] for i in vis)
                + _sep_width(vis)
                + condensed_space
            )
            if total_needed <= available:
                break
            # Remove rightmost visible panel
            rightmost = vis[-1]
            hidden_indices.add(rightmost)
            condensed_space += self._estimate_btn_width(
                next(p for i, p in panels if i == rightmost)
            ) + 4  # 2px spacing each side

        vis = _visible_panels()

        # Second pass: if visible panels still overflow (e.g. condensed
        # buttons cost more than expected), see if the rightmost visible
        # panel can be squeezed to fit.
        if vis:
            total = (
                sum(natural_widths[i] for i in vis)
                + _sep_width(vis)
                + condensed_space
            )
            if total > available:
                rightmost = vis[-1]
                others_width = (
                    sum(natural_widths[i] for i in vis if i != rightmost)
                    + _sep_width(vis)
                    + condensed_space
                )
                remaining = available - others_width
                rightmost_panel = next(p for i, p in panels if i == rightmost)
                min_w = rightmost_panel.minimumSizeHint().width()
                if remaining >= min_w:
                    # Squeeze the rightmost visible panel
                    rightmost_panel.constrain_width(remaining)
                else:
                    # Can't fit even at minimum — hide it too
                    hidden_indices.add(rightmost)
                    condensed_space += self._estimate_btn_width(rightmost_panel) + 4

        # Apply visibility
        vis = _visible_panels()
        for i, item in enumerate(self._items):
            if isinstance(item, RibbonPanelFrame):
                if i in hidden_indices:
                    item.unconstrain()
                    item.hide()
                else:
                    item.show()
                    # Only unconstrain panels that are NOT the squeezed one
                    if not item._constrained:
                        item.unconstrain()
            elif isinstance(item, _PanelSeparator):
                has_left = any(pi < i for pi in vis)
                has_right = any(pi > i for pi in vis)
                if has_left and has_right:
                    item.show()
                else:
                    item.hide()

        # Build condensed buttons for hidden panels (in display order)
        hidden_panels = [p for i, p in panels if i in hidden_indices]
        if hidden_panels:
            for panel in hidden_panels:
                btn = self._make_condensed_button(panel)
                self._overflow_layout.addWidget(btn)
                self._condensed_buttons.append(btn)
            self._overflow_widget.show()

    # ------------------------------------------------------------------
    # Condensed buttons
    # ------------------------------------------------------------------

    def _estimate_btn_width(self, panel: RibbonPanelFrame) -> int:
        title = self._panel_title(panel)
        fm = self.fontMetrics()
        return fm.horizontalAdvance(title) + 28

    def _make_condensed_button(self, panel: RibbonPanelFrame) -> QToolButton:
        title = self._panel_title(panel)
        btn = QToolButton()
        btn.setText(f"{title} \u25be")
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        btn.setStyleSheet(
            f"QToolButton {{ border: 1px solid {COLORS.MENU_BORDER}; border-radius: 2px;"
            f" background: transparent; color: {COLORS.TAB_TEXT_INACTIVE_DARK};"
            f" font-size: 8pt; padding: 4px 6px; }}"
            f"QToolButton:hover {{ background: {COLORS.TAB_HOVER_DARK};"
            f" color: {COLORS.TAB_TEXT_ACTIVE}; }}"
        )
        btn.clicked.connect(
            lambda checked=False, p=panel, b=btn: self._show_panel_popup(p, b)
        )
        return btn

    @staticmethod
    def _panel_title(panel: RibbonPanelFrame) -> str:
        lbl = panel.findChild(QLabel)
        return lbl.text() if lbl else "Panel"

    # ------------------------------------------------------------------
    # Panel popup
    # ------------------------------------------------------------------

    def _show_panel_popup(
        self, panel: RibbonPanelFrame, anchor: QToolButton
    ) -> None:
        if self._active_popup:
            self._active_popup.close()

        popup = _PanelPopup(panel, self, self._dark, self.window())
        popup.adjustSize()

        pos = anchor.mapToGlobal(QPoint(0, anchor.height()))
        screen = self.screen()
        if screen:
            sr = screen.availableGeometry()
            if pos.x() + popup.width() > sr.right():
                pos.setX(sr.right() - popup.width())
            if pos.y() + popup.height() > sr.bottom():
                pos = anchor.mapToGlobal(QPoint(0, -popup.height()))
        popup.move(pos)
        popup.show()
        self._active_popup = popup

    def _restore_and_reflow(self) -> None:
        """Return all panels to the inner layout and re-evaluate overflow."""
        while self._inner_layout.count() > 0:
            self._inner_layout.takeAt(0)
        for item in self._items:
            item.setParent(self)
            if isinstance(item, RibbonPanelFrame):
                item.unconstrain()
            self._inner_layout.addWidget(item)
        self._reflow()


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

        # Tracks the most recently clicked colour swatch button so external
        # code (bridge) can anchor popups correctly.
        self._last_color_swatch_btn: Optional[QPushButton] = None

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

    def color_swatch_anchor(self) -> Optional[QPushButton]:
        """Return the most recently clicked colour swatch button (if any)."""
        return self._last_color_swatch_btn

    # ------------------------------------------------------------------
    # Internal signal wiring
    # ------------------------------------------------------------------

    def _connect_property_controls(self) -> None:
        """Connect factory-built property widgets to the public signals."""
        # Color swatches → colorChangeRequested
        for btn in self.findChildren(QPushButton, "colorSwatchBtn"):
            btn.clicked.connect(lambda checked=False, b=btn: self._on_color_swatch_clicked(b))

    def _on_color_swatch_clicked(self, btn: QPushButton) -> None:
        self._last_color_swatch_btn = btn
        self.colorChangeRequested.emit()

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
