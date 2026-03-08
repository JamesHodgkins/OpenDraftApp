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
# Add QComboBox for layer select lookup
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPaintEvent, QMouseEvent
import logging

_LOG = logging.getLogger(__name__)

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
            return QColor("#2D2D2D")
        if index == self._hovered_index:
            return QColor(255, 255, 255, 18) if self._dark else QColor(17, 24, 39, 14)
        return None

    def _tab_text_color(self, index: int) -> QColor:
        if index == self.currentIndex():
            return QColor("#f3f4f6")
        if self._dark:
            return QColor("#f3f4f6") if index == self.currentIndex() else QColor("#9ca3af")
        return QColor("#111827") if index == self.currentIndex() else QColor("#6b7280")


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

        # Held after setup_document() for refresh_layers()
        self._document = None
        self._editor = None

    # ------------------------------------------------------------------
    # Document wiring
    # ------------------------------------------------------------------

    def setup_document(self, doc, editor=None) -> None:
        """Wire live document data to the Properties-panel controls.

        Must be called after the ribbon is fully constructed (e.g. from
        ``MainWindow.__init__``).  Safe to call multiple times.

        Parameters
        ----------
        doc:
            The application :class:`~app.document.DocumentStore`.
        editor:
            The application :class:`~app.editor.Editor` — required for
            selection-aware behaviour (layer / property changes apply to
            selected entities when a selection is active).
        """
        self._document = doc
        self._editor = editor
        self.refresh_layers()

        # ── color swatch ─────────────────────────────────────────────
        # Use findChildren (plural) so every tab's instance gets wired.
        from PySide6.QtWidgets import QPushButton, QDialog
        from app.colors.color import Color as _Color
        from app.ui.color_picker import ColorPickerDialog as _ColorPickerDialog
        for btn in self.findChildren(QPushButton, "colorSwatchBtn"):
            def _pick_color(_btn=btn):
                _doc = self._document
                _editor = self._editor
                # Determine a sensible starting colour
                if _editor and _editor.selection:
                    first_id = next(iter(_editor.selection.ids))
                    e = _doc.get_entity(first_id)
                    raw = (e.color if e and e.color else None)
                else:
                    raw = _doc.active_color

                if raw is not None:
                    initial = _Color.from_string(raw)
                else:
                    initial = _Color(aci=7)

                dlg = _ColorPickerDialog(initial=initial, parent=self, title="Override colour")
                if dlg.exec() != QDialog.Accepted:
                    return

                chosen = dlg.chosen_color()
                if chosen is None:
                    return

                color_str = chosen.to_string()
                if _editor and _editor.selection:
                    # Apply colour override to every selected entity (undoable)
                    _editor.set_entity_properties(
                        list(_editor.selection.ids), "color", color_str,
                        description="Change colour",
                    )
                else:
                    # Store as the active override for new entities
                    _doc.active_color = color_str
                    # Notify listeners that document-level state changed
                    try:
                        _doc._notify()
                    except Exception:
                        pass

                # Update all swatch visuals immediately
                for _b in self.findChildren(QPushButton, "colorSwatchBtn"):
                    self._set_swatch_color(_b, color_str)

            btn.clicked.connect(_pick_color)

        # ── line-style combo ─────────────────────────────────────────
        from PySide6.QtWidgets import QComboBox as _QComboBox
        for style_combo in self.findChildren(_QComboBox, "lineStyleCombo"):
            def _style_changed(idx, _combo=style_combo):
                _doc = self._document
                _editor = self._editor
                val = None if idx == 0 else _combo.itemText(idx).lower()
                if _editor and _editor.selection:
                    _editor.set_entity_properties(
                        list(_editor.selection.ids), "line_style", val,
                        description="Change line style",
                    )
                else:
                    _doc.active_line_style = val

            style_combo.currentIndexChanged.connect(_style_changed)
            # Also listen to user activation (fires even if the index didn't change)
            try:
                style_combo.activated.connect(_style_changed)
            except Exception:
                pass

        # ── thickness combo ───────────────────────────────────────────
        for thick_combo in self.findChildren(_QComboBox, "thicknessCombo"):
            def _thick_changed(idx, _combo=thick_combo):
                _doc = self._document
                _editor = self._editor
                if idx == 0:
                    val = None
                else:
                    try:
                        val = float(_combo.itemText(idx).split()[0])
                    except (ValueError, IndexError):
                        val = None
                if _editor and _editor.selection:
                    _editor.set_entity_properties(
                        list(_editor.selection.ids), "line_weight", val,
                        description="Change line weight",
                    )
                else:
                    _doc.active_thickness = val

            thick_combo.currentIndexChanged.connect(_thick_changed)
            # Also handle activation so choosing the same visible item (e.g. "by layer")
            # still triggers the handler when user explicitly picks it from the popup.
            try:
                thick_combo.activated.connect(_thick_changed)
            except Exception:
                pass

        # ── selection awareness ───────────────────────────────────────
        if editor is not None:
            editor.selection.changed.connect(self._refresh_controls_from_selection)

    # ------------------------------------------------------------------
    # Selection-driven control refresh
    # ------------------------------------------------------------------

    def _refresh_controls_from_selection(self) -> None:
        """Update ribbon controls to reflect the current selection state.

        Called automatically whenever ``editor.selection`` changes.
        - No selection: show document-level active layer / overrides.
        - One or more entities selected: show their common properties
          (or leave unchanged for mixed values).
        """
        doc = self._document
        editor = self._editor
        if doc is None:
            return

        sel_ids = editor.selection.ids if editor else set()

        # ── layer combo ───────────────────────────────────────────────
        for combo in self._get_layer_combos():
            combo.blockSignals(True)
            if sel_ids:
                layers = {
                    doc.get_entity(eid).layer
                    for eid in sel_ids
                    if doc.get_entity(eid) is not None
                }
                if len(layers) == 1:
                    idx = combo.findText(next(iter(layers)))
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                # mixed selection: leave combo unchanged
            else:
                idx = combo.findText(doc.active_layer)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        # ── color swatch ──────────────────────────────────────────────
        from PySide6.QtWidgets import QPushButton as _QPushButton
        from PySide6.QtWidgets import QComboBox as _QComboBox
        if sel_ids:
            colors = {
                getattr(doc.get_entity(eid), "color", None)
                for eid in sel_ids
                if doc.get_entity(eid) is not None
            }
            color = next(iter(colors)) if len(colors) == 1 else None
        else:
            color = doc.active_color
        for btn in self.findChildren(_QPushButton, "colorSwatchBtn"):
            self._set_swatch_color(btn, color)

        # ── style combo ───────────────────────────────────────────────
        if sel_ids:
            styles = {
                getattr(doc.get_entity(eid), "line_style", None)
                for eid in sel_ids
                if doc.get_entity(eid) is not None
            }
            style_val = next(iter(styles)) if len(styles) == 1 else None
        else:
            style_val = doc.active_line_style
        for style_combo in self.findChildren(_QComboBox, "lineStyleCombo"):
            style_combo.blockSignals(True)
            self._set_combo_text(style_combo, style_val, case_fold=True)
            style_combo.blockSignals(False)

        # ── thickness combo ───────────────────────────────────────────
        if sel_ids:
            weights = {
                getattr(doc.get_entity(eid), "line_weight", None)
                for eid in sel_ids
                if doc.get_entity(eid) is not None
            }
            weight_val = next(iter(weights)) if len(weights) == 1 else None
        else:
            weight_val = doc.active_thickness
        for thick_combo in self.findChildren(_QComboBox, "thicknessCombo"):
            thick_combo.blockSignals(True)
            if weight_val is None:
                thick_combo.setCurrentIndex(0)
            else:
                for i in range(1, thick_combo.count()):
                    try:
                        if abs(float(thick_combo.itemText(i).split()[0]) - weight_val) < 0.001:
                            thick_combo.setCurrentIndex(i)
                            break
                    except (ValueError, IndexError):
                        pass
            thick_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_swatch_color(btn, color: Optional[str]) -> None:
        """Apply a colour string to a colour-swatch QPushButton.

        Accepts ACI strings (``"aci:N"``) as well as plain ``#rrggbb`` hex.
        """
        if color:
            from app.colors.color import Color as _Color
            try:
                resolved = _Color.from_string(color).to_hex()
            except Exception:
                resolved = color
            btn.setStyleSheet(
                f"QPushButton {{ background: {resolved}; border: 1px solid #666; border-radius: 2px; }}"
                "QPushButton:hover { border-color: #aaa; }"
            )
        else:
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid #666; border-radius: 2px; }"
                "QPushButton:hover { border-color: #aaa; }"
            )

    @staticmethod
    def _set_combo_text(combo, value: Optional[str], *, case_fold: bool = False) -> None:
        """Select the combo item matching *value*, or index 0 if None / not found."""
        if value is None:
            combo.setCurrentIndex(0)
            return
        # Try exact match first, then case-folded capitalisation
        idx = combo.findText(value)
        if idx < 0 and case_fold:
            idx = combo.findText(value.capitalize())
        combo.setCurrentIndex(idx if idx >= 0 else 0)

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

    def refresh_layers(self) -> None:
        """Repopulate the layer-select combo from the current document.

        Call this whenever layers are added, removed or renamed.
        """
        doc = self._document
        if doc is None:
            return

        combos = self._get_layer_combos()
        if not combos:
            return

        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            for layer in doc.layers:
                combo.addItem(layer.name)
            # Restore current selection
            idx = combo.findText(doc.active_layer)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

            # Connect once — store the slot on the widget so multiple calls to
            # refresh_layers() don't stack up duplicate connections.
            if not hasattr(combo, "_layer_slot"):
                def _slot(name, _ribbon=self):
                    _doc = _ribbon._document
                    _editor = _ribbon._editor
                    if _editor and _editor.selection:
                        # Move all selected entities to the chosen layer (undoable)
                        _editor.set_entity_properties(
                            list(_editor.selection.ids), "layer", name,
                            description="Change entity layer",
                        )
                    else:
                        # No selection — change the active (current) layer
                        if _editor:
                            _editor.set_active_layer(name)
                        else:
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
            tab_layout.addWidget(panel_widget, alignment=Qt.AlignTop)
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
