"""
Controller Panel — unified dockable panel for command input and entity properties.

The panel is composed of four vertically stacked sections:

1. **Command bar** — a mode pill (READY / active command name), a single-line
   command input, and a vertical list of suggested commands while the user types.
2. **Stateful command card** — visible while a stateful command is active.
   Shows the command's exported properties, a live cursor read-out, and a pair
   of prominent Commit / Cancel buttons.
3. **Selection summary** — number of selected entities plus a row of toggleable
   *type chips* when the selection contains multiple entity kinds.
4. **Property cards** — one card for shared *general* properties (layer, color,
   line weight, line style) and one card driven by a per-kind geometry schema
   (line / circle / arc / rect / polyline / text / dimension / hatch).

Wiring is unchanged from the previous panel — :class:`MainWindow` constructs
this widget and connects ``selection.changed`` and the stateful-command signals
exactly as before.

Public API (preserved):
    PropertiesPanel(document, editor, parent=None)
    .refresh()
    .bind_stateful_command(cmd) / .clear_stateful_command()
    .set_command_property_value(name, value)
    .set_active_command_property(name)
    .update_cursor_world(x, y)
    .focus_command_input()
    .set_commands(commands)

Signals (preserved):
    properties_changed              — entity attribute(s) edited
    command_requested(str)          — idle command id chosen
    property_changed(str, object)   — stateful command property edit
    header_value_submitted(str)     — raw text from command bar input
    commit_requested / cancel_requested
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QDoubleValidator, QFocusEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.document import DocumentStore
from app.editor.stateful_command import ExportInfo, PartialPoint, StatefulCommandBase
from app.editor.undo import SetEntityPropertiesUndoCommand
from app.entities import Vec2

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

_BG          = "#252526"   # outer panel background
_BG_CARD     = "#2d2d30"   # property card background
_BG_INPUT    = "#1e1e1e"   # input background
_BG_HOVER    = "#3a3a3d"
_BORDER      = "#3a3a3a"
_BORDER_HI   = "#505055"
_TEXT        = "#e4e4e6"
_TEXT_DIM    = "#888c92"
_TEXT_FAINT  = "#5a5e64"
_EMERALD     = "#10b981"
_EMERALD_DIM = "#064e3b"
_BLUE        = "#60a5fa"
_BLUE_DIM    = "#1e3a5f"
_RED         = "#ef4444"
_RED_DIM     = "#3a1e1e"
_AMBER       = "#f59e0b"

_VARIOUS = "various"  # sentinel display string for mixed values

_LINE_STYLES  = ["ByLayer", "solid", "dashed", "dotted", "dashdot",
                 "dashdotdot", "center", "phantom", "hidden"]
_LINE_WEIGHTS = ["ByLayer", "0.25", "0.5", "0.75", "1.0",
                 "1.25", "1.5", "2.0", "2.5", "3.0"]


_PANEL_STYLE = f"""
QWidget {{
    background: {_BG};
    color: {_TEXT};
    font-size: 11px;
}}

/* ── Section card ─────────────────────────────────────────────── */
QFrame#SectionCard {{
    background: {_BG_CARD};
    border: 1px solid {_BORDER};
    border-radius: 5px;
}}
QLabel#SectionTitle {{
    color: {_EMERALD};
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 0 0 2px 0;
}}
QLabel#SectionSubtitle {{
    color: {_TEXT_DIM};
    font-size: 10px;
}}

/* ── Property rows (key labels) ───────────────────────────────── */
QLabel[role="key"] {{
    color: {_TEXT_DIM};
    padding-right: 6px;
}}
QLabel[role="readout"] {{
    color: {_TEXT_FAINT};
    font-style: italic;
    padding: 2px 6px;
}}

/* ── Inputs ───────────────────────────────────────────────────── */
QLineEdit {{
    background: {_BG_INPUT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 3px;
    padding: 3px 6px;
    selection-background-color: {_EMERALD_DIM};
    selection-color: {_TEXT};
}}
QLineEdit:focus {{
    border-color: {_EMERALD};
}}
QLineEdit:read-only {{
    background: transparent;
    border: 1px solid transparent;
    color: {_TEXT_FAINT};
    font-style: italic;
}}
QLineEdit[various="true"] {{
    color: {_TEXT_DIM};
    font-style: italic;
}}

QComboBox {{
    background: {_BG_INPUT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 3px;
    padding: 3px 8px 3px 6px;
}}
QComboBox:focus {{
    border-color: {_EMERALD};
}}
QComboBox::drop-down {{
    border: none;
    width: 14px;
}}
QComboBox QAbstractItemView {{
    background: #2a2a2c;
    color: {_TEXT};
    border: 1px solid {_BORDER_HI};
    selection-background-color: {_EMERALD_DIM};
    outline: none;
    padding: 2px;
}}

/* ── Mode pill (top of command bar) ───────────────────────────── */
QLabel#ModePillIdle {{
    background: {_BG_CARD};
    color: {_TEXT_DIM};
    border: 1px solid {_BORDER};
    border-radius: 9px;
    padding: 1px 8px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#ModePillActive {{
    background: {_BLUE_DIM};
    color: {_BLUE};
    border: 1px solid {_BLUE};
    border-radius: 9px;
    padding: 1px 8px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
}}

/* ── Command input prefix label ───────────────────────────────── */
QLabel#CommandPrefix {{
    color: {_EMERALD};
    font-weight: 700;
    padding-right: 2px;
}}
QLineEdit#CommandInput {{
    background: {_BG_INPUT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
}}
QLineEdit#CommandInput:focus {{
    border-color: {_EMERALD};
}}

/* ── Suggestion buttons ───────────────────────────────────────── */
QToolButton#SuggestionButton {{
    background: {_BG_CARD};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 3px;
    padding: 4px 8px;
    text-align: left;
}}
QToolButton#SuggestionButton:hover {{
    background: {_BG_HOVER};
    border-color: {_EMERALD};
}}
QToolButton#SuggestionButton[selected="true"] {{
    background: {_EMERALD_DIM};
    border: 1px solid {_EMERALD};
    color: {_EMERALD};
}}
QLabel#SuggestionAlias {{
    color: {_TEXT_DIM};
    font-style: italic;
}}

/* ── Workflow toggles row ─────────────────────────────────────── */
QCheckBox#WorkflowToggle {{
    color: {_TEXT_DIM};
    font-size: 10px;
    spacing: 4px;
}}
QCheckBox#WorkflowToggle:hover {{
    color: {_TEXT};
}}
QCheckBox#WorkflowToggle::indicator {{
    width: 12px;
    height: 12px;
    border: 1px solid {_BORDER};
    border-radius: 2px;
    background: {_BG_INPUT};
}}
QCheckBox#WorkflowToggle::indicator:checked {{
    background: {_EMERALD};
    border: 1px solid {_EMERALD};
}}

/* ── Cursor read-out ──────────────────────────────────────────── */
QLabel#CursorReadout {{
    color: {_TEXT_DIM};
    font-family: 'Consolas', 'Menlo', monospace;
    font-size: 10px;
    padding: 2px 4px;
}}

/* ── Selection summary ────────────────────────────────────────── */
QLabel#SelectionCount {{
    color: {_TEXT};
    font-weight: 600;
    font-size: 12px;
}}
QLabel#SelectionBreakdown {{
    color: {_TEXT_DIM};
    font-size: 10px;
}}

/* ── Type-filter chips ────────────────────────────────────────── */
QPushButton#TypeChip {{
    background: {_BG_CARD};
    color: {_TEXT_DIM};
    border: 1px solid {_BORDER};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
}}
QPushButton#TypeChip:hover {{
    border-color: {_EMERALD};
    color: {_TEXT};
}}
QPushButton#TypeChip:checked {{
    background: {_EMERALD_DIM};
    color: {_EMERALD};
    border: 1px solid {_EMERALD};
    font-weight: 600;
}}

/* ── Stateful command rows ────────────────────────────────────── */
QLabel#CmdRowLabel {{
    color: {_TEXT_DIM};
    padding: 0 4px 0 2px;
}}
QLabel#CmdRowLabelActive {{
    color: {_BLUE};
    font-weight: 700;
    padding: 0 4px 0 2px;
}}

/* ── Action buttons (Commit / Cancel) ─────────────────────────── */
QPushButton#CommitButton {{
    background: {_EMERALD_DIM};
    color: {_EMERALD};
    border: 1px solid {_EMERALD};
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 11px;
    font-weight: 700;
}}
QPushButton#CommitButton:hover {{
    background: {_EMERALD};
    color: #052e22;
}}
QPushButton#CancelButton {{
    background: transparent;
    color: {_TEXT_DIM};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 11px;
}}
QPushButton#CancelButton:hover {{
    background: {_RED_DIM};
    color: {_RED};
    border-color: {_RED};
}}

/* ── Misc ─────────────────────────────────────────────────────── */
QFrame[role="hr"] {{
    background: {_BORDER};
    max-height: 1px;
    margin: 2px 0;
}}
QScrollArea {{
    background: {_BG};
    border: none;
}}
"""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _hr(parent: QWidget) -> QFrame:
    """A 1-pixel horizontal divider styled by the panel stylesheet."""
    f = QFrame(parent)
    f.setProperty("role", "hr")
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    return f


def _fmt_float(v: Optional[float], decimals: int = 4) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return f"{v:.{decimals}g}"


def _parse_float(s: str, fallback: float) -> float:
    """Lenient numeric parse used by inline geometry edits.

    Trims whitespace and a trailing ``°`` so users can leave angle suffixes in
    place when re-editing a field.
    """
    try:
        return float(s.strip().rstrip("°"))
    except (ValueError, AttributeError):
        return fallback


def _collect_uniform(entities, getter: Callable[[Any], Any]) -> Tuple[Any, bool]:
    """Return ``(value, is_uniform)``.  ``value`` is ``None`` for empty input."""
    seen = set()
    last: Any = None
    for e in entities:
        v = getter(e)
        last = v
        seen.add(v)
        if len(seen) > 1:
            return None, False
    if not seen:
        return None, True
    return last, True


# ---------------------------------------------------------------------------
# Re-usable widgets
# ---------------------------------------------------------------------------

class _AutoSelectLineEdit(QLineEdit):
    """A QLineEdit that selects all text the moment it gains focus.

    ``selectAll()`` is deferred one tick so the mouse-release that follows a
    focus-by-click does not clobber the selection.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._focus_select_token = 0

    def _cancel_pending_focus_select(self) -> None:
        """Invalidate any deferred select-all scheduled by focus changes."""
        self._focus_select_token += 1

    def _maybe_select_all(self, token: int) -> None:
        if token != self._focus_select_token:
            return
        if not self.hasFocus():
            return
        self.selectAll()

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: D401
        super().focusInEvent(event)
        self._focus_select_token += 1
        token = self._focus_select_token
        # For click-focus we still defer one tick so mouse-release doesn't
        # clobber selection. Keyboard/programmatic focus selects immediately.
        if event.reason() == Qt.FocusReason.MouseFocusReason:
            QTimer.singleShot(0, lambda t=token: self._maybe_select_all(t))
            return
        self._maybe_select_all(token)


class _CommandInput(_AutoSelectLineEdit):
    """Command-bar line edit with Up/Down arrow keys for suggestion nav.

    Owned by :class:`PropertiesPanel`; the panel attaches itself via
    :meth:`set_panel` so the line edit can drive the highlighted index in
    the suggestion list and trigger the highlighted command on Enter.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._panel: Optional["PropertiesPanel"] = None

    def set_panel(self, panel: "PropertiesPanel") -> None:
        self._panel = panel

    def keyPressEvent(self, event) -> None:  # noqa: N802
        self._cancel_pending_focus_select()
        panel = self._panel
        if panel is not None and panel._suggestion_buttons:
            key = event.key()
            if key == Qt.Key.Key_Down:
                panel._move_suggestion_cursor(1)
                return
            if key == Qt.Key.Key_Up:
                panel._move_suggestion_cursor(-1)
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and panel._suggestion_index >= 0:
                panel._activate_selected_suggestion()
                return
        super().keyPressEvent(event)


class _CmdInputLineEdit(_AutoSelectLineEdit):
    """Command-row line edit with Up/Down row navigation hooks."""

    activated = Signal()
    navigate_requested = Signal(int)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.activated.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        self._cancel_pending_focus_select()
        key = event.key()
        if key == Qt.Key.Key_Up:
            self.navigate_requested.emit(-1)
            return
        if key == Qt.Key.Key_Down:
            self.navigate_requested.emit(1)
            return
        super().keyPressEvent(event)


class _ColorSwatch(QFrame):
    """16×16 rounded square that previews the current colour string."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._set_swatch(None)

    def set_color(self, value: Optional[str]) -> None:
        self._set_swatch(value)

    def _set_swatch(self, value: Optional[str]) -> None:
        # ByLayer / mixed values render as a hatch-like neutral fill.
        if not value or value in ("ByLayer", _VARIOUS):
            self.setStyleSheet(
                f"background: {_BG_INPUT};"
                f"border: 1px dashed {_BORDER_HI};"
                "border-radius: 3px;"
            )
            return
        qc = QColor(value)
        if not qc.isValid():
            self.setStyleSheet(
                f"background: {_BG_INPUT};"
                f"border: 1px solid {_BORDER};"
                "border-radius: 3px;"
            )
            return
        self.setStyleSheet(
            f"background: {qc.name()};"
            f"border: 1px solid {_BORDER_HI};"
            "border-radius: 3px;"
        )


class _SectionCard(QFrame):
    """Bordered card with a title row and a body grid for property rows."""

    def __init__(self, title: str, parent: QWidget, subtitle: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("SectionCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 8)
        outer.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self.title_label = QLabel(title.upper(), self)
        self.title_label.setObjectName("SectionTitle")
        header.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle, self)
            self.subtitle_label.setObjectName("SectionSubtitle")
            header.addWidget(self.subtitle_label)
        header.addStretch(1)
        outer.addLayout(header)

        self.body = QGridLayout()
        self.body.setContentsMargins(0, 2, 0, 0)
        self.body.setHorizontalSpacing(6)
        self.body.setVerticalSpacing(4)
        self.body.setColumnStretch(1, 1)
        outer.addLayout(self.body)


# ---------------------------------------------------------------------------
# Property rows used inside section cards
# ---------------------------------------------------------------------------

class _PropRow:
    """A label + editable widget stored in a section card grid.

    The row always occupies two columns (key, value).  When ``widget_type`` is
    ``"combo"`` the value column hosts a :class:`QComboBox`; otherwise it hosts
    an :class:`_AutoSelectLineEdit`.
    """

    def __init__(
        self,
        card: _SectionCard,
        row_index: int,
        key: str,
        *,
        widget_type: str = "lineedit",
        options: Optional[List[str]] = None,
        read_only: bool = False,
        numeric: bool = False,
    ) -> None:
        self.key = key
        self.widget_type = widget_type
        self.read_only = read_only

        label = QLabel(key, card)
        label.setProperty("role", "key")
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        card.body.addWidget(label, row_index, 0)

        if widget_type == "combo" and options:
            combo = QComboBox(card)
            combo.addItems(options)
            combo.setEnabled(not read_only)
            self.widget: QWidget = combo
        else:
            edit = _AutoSelectLineEdit(card)
            if numeric and not read_only:
                edit.setValidator(QDoubleValidator(edit))
            if read_only:
                edit.setReadOnly(True)
                edit.setProperty("role", "readout")
            self.widget = edit

        card.body.addWidget(self.widget, row_index, 1)

    # ---- value sync ---------------------------------------------------

    def set_value(self, value: Any, is_uniform: bool) -> None:
        if isinstance(self.widget, QComboBox):
            self._set_combo(value, is_uniform)
        else:
            self._set_line(value, is_uniform)

    def _set_combo(self, value: Any, is_uniform: bool) -> None:
        w: QComboBox = self.widget  # type: ignore[assignment]
        w.blockSignals(True)
        try:
            if not is_uniform:
                if w.itemText(0) != _VARIOUS:
                    w.insertItem(0, _VARIOUS)
                w.setCurrentIndex(0)
                return
            if w.itemText(0) == _VARIOUS:
                w.removeItem(0)
            txt = "" if value is None else str(value)
            idx = w.findText(txt)
            w.setCurrentIndex(max(idx, 0))
        finally:
            w.blockSignals(False)

    def _set_line(self, value: Any, is_uniform: bool) -> None:
        w: QLineEdit = self.widget  # type: ignore[assignment]
        w.blockSignals(True)
        try:
            if not is_uniform:
                w.setText(_VARIOUS)
                w.setProperty("various", "true")
            else:
                w.setProperty("various", "false")
                w.setText("" if value is None else str(value))
            w.style().unpolish(w)
            w.style().polish(w)
        finally:
            w.blockSignals(False)

    # ---- read & wire --------------------------------------------------

    def current_text(self) -> str:
        if isinstance(self.widget, QComboBox):
            return self.widget.currentText()
        return self.widget.text()  # type: ignore[union-attr]

    def is_various(self) -> bool:
        return self.current_text() == _VARIOUS

    def connect_changed(self, slot: Callable[[], None]) -> None:
        if isinstance(self.widget, QComboBox):
            self.widget.currentTextChanged.connect(lambda _t: slot())
        else:
            self.widget.editingFinished.connect(slot)  # type: ignore[union-attr]


class _ColorRow:
    """A swatch + line-edit row for the ``color`` attribute.

    Behaves like :class:`_PropRow` but adds a colour preview in front of the
    text input that updates as the user types.
    """

    def __init__(self, card: _SectionCard, row_index: int) -> None:
        label = QLabel("Color", card)
        label.setProperty("role", "key")
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        card.body.addWidget(label, row_index, 0)

        wrap = QWidget(card)
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.swatch = _ColorSwatch(wrap)
        layout.addWidget(self.swatch)

        self.edit = _AutoSelectLineEdit(wrap)
        self.edit.setPlaceholderText("ByLayer")
        self.edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.edit, 1)

        card.body.addWidget(wrap, row_index, 1)

    def set_value(self, value: Any, is_uniform: bool) -> None:
        self.edit.blockSignals(True)
        try:
            if not is_uniform:
                self.edit.setText(_VARIOUS)
                self.edit.setProperty("various", "true")
                self.swatch.set_color(_VARIOUS)
            else:
                self.edit.setProperty("various", "false")
                txt = "" if value is None else str(value)
                self.edit.setText(txt)
                self.swatch.set_color(txt or "ByLayer")
            self.edit.style().unpolish(self.edit)
            self.edit.style().polish(self.edit)
        finally:
            self.edit.blockSignals(False)

    def current_text(self) -> str:
        return self.edit.text()

    def is_various(self) -> bool:
        return self.edit.text() == _VARIOUS

    def connect_changed(self, slot: Callable[[], None]) -> None:
        self.edit.editingFinished.connect(slot)

    def _on_text_changed(self, text: str) -> None:
        self.swatch.set_color(text or "ByLayer")


# ---------------------------------------------------------------------------
# Stateful command rows
# ---------------------------------------------------------------------------

class _CmdRowBase(QWidget):
    """Common label-styling logic for stateful command rows."""

    activated = Signal()
    advance_requested = Signal()  # emitted when the user presses Enter on the row
    navigate_requested = Signal(int)

    def __init__(self, info: ExportInfo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._info = info
        self._active = False
        self._label = QLabel(info.label, self)
        self._label.setObjectName("CmdRowLabel")

    @property
    def info(self) -> ExportInfo:
        return self._info

    def set_active(self, active: bool) -> None:
        self._active = active
        self._label.setObjectName("CmdRowLabelActive" if active else "CmdRowLabel")
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)
        self._on_active_changed(active)

    def _on_active_changed(self, active: bool) -> None:
        """Subclass hook for active/inactive visual tweaks."""

    # ---- focus helpers ------------------------------------------------

    def focus_input(self) -> None:  # overridden by subclasses
        """Focus the row's primary edit widget and select its text."""

    def append_text(self, text: str) -> None:  # overridden by subclasses
        """Append typed text to the row's active editor."""


class _CmdPointRow(_CmdRowBase):
    """Single parsed textbox row for a point-like (x/y) export."""

    value_changed = Signal(object)
    preview_changed = Signal(object)

    def __init__(
        self,
        info: ExportInfo,
        point_parser: Callable[[str], Vec2 | None],
        *,
        placeholder: str = "x,y",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(info, parent)
        self._point_parser = point_parser

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        layout.addWidget(self._label)

        self._edit = _CmdInputLineEdit(self)
        self._edit.setMinimumWidth(120)
        self._edit.setPlaceholderText(placeholder)
        self._edit.editingFinished.connect(self._on_edit_finished)
        self._edit.returnPressed.connect(self._on_return_pressed)
        self._edit.textChanged.connect(self._on_partial_text_changed)
        self._edit.activated.connect(self.activated.emit)
        self._edit.navigate_requested.connect(self.navigate_requested.emit)
        layout.addWidget(self._edit, 1)

    def set_value(self, value: Any) -> None:
        self._edit.blockSignals(True)
        try:
            if isinstance(value, Vec2):
                self._edit.setText(f"{_fmt_float(value.x)},{_fmt_float(value.y)}")
            elif isinstance(value, PartialPoint):
                x = "" if value.x is None else _fmt_float(value.x)
                y = "" if value.y is None else _fmt_float(value.y)
                self._edit.setText(f"{x},{y}" if (x or y) else "")
            else:
                self._edit.clear()
        finally:
            self._edit.blockSignals(False)

    def focus_input(self) -> None:
        self._edit.setFocus()
        self._edit.selectAll()

    def append_text(self, text: str) -> None:
        if not self._edit.hasFocus():
            self.focus_input()
        self._edit._cancel_pending_focus_select()
        self._edit.insert(text)

    def _on_return_pressed(self) -> None:
        if self._emit_if_valid():
            self.advance_requested.emit()
            return
        self._emit_partial_preview()

    def _on_edit_finished(self) -> None:
        if self._emit_if_valid():
            return
        self._emit_partial_preview()

    def _on_partial_text_changed(self, _text: str) -> None:
        self._emit_partial_preview()

    @staticmethod
    def _parse_partial_point(text: str) -> PartialPoint | None:
        raw = text.strip()
        if raw.startswith("#"):
            raw = raw[1:].strip()
        raw = raw.replace(";", ",")
        if "," not in raw:
            return None
        parts = raw.split(",")
        if len(parts) != 2:
            return None
        x_token = parts[0].strip()
        y_token = parts[1].strip()
        if x_token and y_token:
            return None

        def _parse_optional(token: str) -> float | None:
            if not token:
                return None
            return float(token)

        try:
            x_val = _parse_optional(x_token)
            y_val = _parse_optional(y_token)
        except ValueError:
            return None
        if x_val is None and y_val is None:
            return None
        return PartialPoint(x=x_val, y=y_val)

    def _emit_partial_preview(self) -> bool:
        text = self._edit.text().strip()
        if not text:
            self.preview_changed.emit(None)
            return True

        partial = self._parse_partial_point(text)
        if partial is not None:
            self.preview_changed.emit(partial)
            return True

        point = self._point_parser(text)
        if point is None:
            return False
        self.preview_changed.emit(point)
        return True

    def _emit_if_valid(self) -> bool:
        text = self._edit.text().strip()
        if not text:
            return False
        point = self._point_parser(text)
        if point is None:
            return False
        self.value_changed.emit(point)
        return True


class _CmdScalarRow(_CmdRowBase):
    """Single line-edit row for non-point exports."""

    value_changed = Signal(object)

    def __init__(self, info: ExportInfo, parent: Optional[QWidget] = None) -> None:
        super().__init__(info, parent)
        self._is_numeric = info.input_kind in ("float", "integer", "angle", "length")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        layout.addWidget(self._label)

        self._edit = _CmdInputLineEdit(self)
        if self._is_numeric:
            self._edit.setValidator(QDoubleValidator(self._edit))
        self._edit.editingFinished.connect(self._on_edit_finished)
        self._edit.returnPressed.connect(self._on_return_pressed)
        self._edit.activated.connect(self.activated.emit)
        self._edit.navigate_requested.connect(self.navigate_requested.emit)
        layout.addWidget(self._edit, 1)

    def set_value(self, value: Any) -> None:
        self._edit.blockSignals(True)
        try:
            if value is None:
                self._edit.clear()
            else:
                self._edit.setText(str(value))
        finally:
            self._edit.blockSignals(False)

    def focus_input(self) -> None:
        self._edit.setFocus()
        self._edit.selectAll()

    def append_text(self, text: str) -> None:
        if not self._edit.hasFocus():
            self.focus_input()
        self._edit._cancel_pending_focus_select()
        self._edit.insert(text)

    def _on_return_pressed(self) -> None:
        if self._emit_if_valid():
            self.advance_requested.emit()

    def _on_edit_finished(self) -> None:
        self._emit_if_valid()

    def _emit_if_valid(self) -> bool:
        text = self._edit.text().strip()
        if not text:
            return False
        if self._is_numeric:
            try:
                val = float(text)
                if self._info.input_kind == "integer":
                    val = int(val)
            except ValueError:
                return False
            self.value_changed.emit(val)
        else:
            self.value_changed.emit(text)
        return True


# ---------------------------------------------------------------------------
# Geometry schema — drives the per-kind property card
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _GeoField:
    """Description of one row inside a geometry card.

    ``apply`` is ``None`` for derived/read-only readouts (e.g. line length).
    Otherwise it is a callable receiving ``(entity, raw_text)`` that mutates
    the entity in-place using whatever input parsing it needs.
    """

    label: str
    getter: Callable[[Any], Any]
    apply: Optional[Callable[[Any, str], None]]
    fmt: Callable[[Any], str] = _fmt_float
    numeric: bool = True


# Per-kind schema factories — kept as small functions so closures can
# capture imports lazily and avoid triggering circular imports at module load.

def _line_schema() -> List[_GeoField]:
    def ax(e, s): e.p1 = Vec2(_parse_float(s, e.p1.x), e.p1.y)
    def ay(e, s): e.p1 = Vec2(e.p1.x, _parse_float(s, e.p1.y))
    def bx(e, s): e.p2 = Vec2(_parse_float(s, e.p2.x), e.p2.y)
    def by(e, s): e.p2 = Vec2(e.p2.x, _parse_float(s, e.p2.y))
    return [
        _GeoField("Start X", lambda e: e.p1.x, ax),
        _GeoField("Start Y", lambda e: e.p1.y, ay),
        _GeoField("End X",   lambda e: e.p2.x, bx),
        _GeoField("End Y",   lambda e: e.p2.y, by),
        _GeoField("Length",  lambda e: math.hypot(e.p2.x - e.p1.x, e.p2.y - e.p1.y), None),
    ]


def _circle_schema() -> List[_GeoField]:
    def cx(e, s): e.center = Vec2(_parse_float(s, e.center.x), e.center.y)
    def cy(e, s): e.center = Vec2(e.center.x, _parse_float(s, e.center.y))
    def rad(e, s):
        v = _parse_float(s, e.radius)
        if v > 0:
            e.radius = v
    return [
        _GeoField("Center X", lambda e: e.center.x, cx),
        _GeoField("Center Y", lambda e: e.center.y, cy),
        _GeoField("Radius",   lambda e: e.radius,   rad),
        _GeoField("Diameter", lambda e: e.radius * 2, None),
    ]


def _arc_schema() -> List[_GeoField]:
    from app.entities.arc import _arc_span

    def cx(e, s): e.center = Vec2(_parse_float(s, e.center.x), e.center.y)
    def cy(e, s): e.center = Vec2(e.center.x, _parse_float(s, e.center.y))
    def rad(e, s):
        v = _parse_float(s, e.radius)
        if v > 0:
            e.radius = v
    def sa(e, s): e.start_angle = math.radians(_parse_float(s, math.degrees(e.start_angle)))
    def ea(e, s): e.end_angle = math.radians(_parse_float(s, math.degrees(e.end_angle)))

    return [
        _GeoField("Center X", lambda e: e.center.x, cx),
        _GeoField("Center Y", lambda e: e.center.y, cy),
        _GeoField("Radius", lambda e: e.radius, rad),
        _GeoField("Start angle", lambda e: math.degrees(e.start_angle), sa),
        _GeoField("End angle",   lambda e: math.degrees(e.end_angle),   ea),
        _GeoField(
            "Span",
            lambda e: abs(math.degrees(_arc_span(e.start_angle, e.end_angle, e.ccw))),
            None,
        ),
    ]


def _rect_schema() -> List[_GeoField]:
    def p1x(e, s): e.p1 = Vec2(_parse_float(s, e.p1.x), e.p1.y)
    def p1y(e, s): e.p1 = Vec2(e.p1.x, _parse_float(s, e.p1.y))
    def p2x(e, s): e.p2 = Vec2(_parse_float(s, e.p2.x), e.p2.y)
    def p2y(e, s): e.p2 = Vec2(e.p2.x, _parse_float(s, e.p2.y))
    return [
        _GeoField("Corner 1 X", lambda e: e.p1.x, p1x),
        _GeoField("Corner 1 Y", lambda e: e.p1.y, p1y),
        _GeoField("Corner 2 X", lambda e: e.p2.x, p2x),
        _GeoField("Corner 2 Y", lambda e: e.p2.y, p2y),
        _GeoField("Width",  lambda e: abs(e.p2.x - e.p1.x), None),
        _GeoField("Height", lambda e: abs(e.p2.y - e.p1.y), None),
    ]


def _polyline_schema() -> List[_GeoField]:
    return [
        _GeoField("Points", lambda e: len(e.points), None,
                  fmt=lambda v: str(v), numeric=False),
        _GeoField("Closed", lambda e: e.closed, None,
                  fmt=lambda v: "yes" if v else "no", numeric=False),
    ]


def _text_schema() -> List[_GeoField]:
    def txt(e, s): e.text = s
    def x(e, s): e.position = Vec2(_parse_float(s, e.position.x), e.position.y)
    def y(e, s): e.position = Vec2(e.position.x, _parse_float(s, e.position.y))
    def h(e, s):
        v = _parse_float(s, e.height)
        if v > 0:
            e.height = v
    def rot(e, s): e.rotation = _parse_float(s, e.rotation)
    return [
        _GeoField("Content",  lambda e: e.text,       txt, fmt=str, numeric=False),
        _GeoField("X",        lambda e: e.position.x, x),
        _GeoField("Y",        lambda e: e.position.y, y),
        _GeoField("Height",   lambda e: e.height,     h),
        _GeoField("Rotation", lambda e: e.rotation,   rot),
    ]


def _dimension_schema() -> List[_GeoField]:
    def arrow(e, s): e.arrow_size = max(0.0, _parse_float(s, e.arrow_size))
    def ext(e, s):   e.ext_offset = max(0.0, _parse_float(s, e.ext_offset))
    def dim(e, s):   e.dim_offset = max(0.0, _parse_float(s, e.dim_offset))
    return [
        _GeoField("Type", lambda e: e.dim_type, None, fmt=str, numeric=False),
        _GeoField("Arrow size", lambda e: e.arrow_size, arrow),
        _GeoField("Ext offset", lambda e: e.ext_offset, ext),
        _GeoField("Dim offset", lambda e: e.dim_offset, dim),
    ]


def _hatch_schema() -> List[_GeoField]:
    def scale(e, s):
        v = _parse_float(s, e.pattern_scale)
        if v > 0:
            e.pattern_scale = v
    def angle(e, s): e.pattern_angle = _parse_float(s, e.pattern_angle)
    return [
        _GeoField("Pattern", lambda e: e.pattern, None, fmt=str, numeric=False),
        _GeoField("Scale",   lambda e: e.pattern_scale, scale),
        _GeoField("Angle",   lambda e: e.pattern_angle, angle),
    ]


_GEOMETRY_SCHEMAS: Dict[str, Callable[[], List[_GeoField]]] = {
    "line":      _line_schema,
    "circle":    _circle_schema,
    "arc":       _arc_schema,
    "rect":      _rect_schema,
    "polyline":  _polyline_schema,
    "text":      _text_schema,
    "dimension": _dimension_schema,
    "hatch":     _hatch_schema,
}


_TYPE_TITLES = {
    "line":      "Line",
    "circle":    "Circle",
    "arc":       "Arc",
    "rect":      "Rectangle",
    "polyline":  "Polyline",
    "text":      "Text",
    "dimension": "Dimension",
    "hatch":     "Hatch",
}


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class PropertiesPanel(QWidget):
    """Dockable controller / properties inspector.

    Combines an always-visible command bar at the top with the entity
    properties inspector below.  When a stateful command is active the
    command's exported properties replace the property cards until the
    command commits or is cancelled.
    """

    properties_changed = Signal()
    command_requested = Signal(str)
    property_changed = Signal(str, object)
    property_preview_changed = Signal(str, object)
    header_value_submitted = Signal(str)
    commit_requested = Signal()
    cancel_requested = Signal()
    auto_complete_toggled = Signal(bool)
    repeat_toggled = Signal(bool)

    def __init__(
        self,
        document: DocumentStore,
        editor,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._doc = document
        self._editor = editor

        # Re-entrancy guard: we set this while we mutate the document so the
        # selection-changed → refresh round-trip does not clobber an in-flight
        # widget that just lost focus.
        self._blocked = False

        self._type_filters: Dict[str, QPushButton] = {}
        self._cmd_rows: Dict[str, QWidget] = {}
        self._suggestion_buttons: List[QToolButton] = []
        self._suggestion_index: int = -1   # arrow-key cursor in the suggestion list
        self._all_commands: Dict[str, Any] = {}
        self._cursor_world = Vec2(0, 0)

        self.setStyleSheet(_PANEL_STYLE)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._build_ui()
        self._install_shortcuts()
        self._refresh_cursor_label()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the property cards from the current selection."""
        if self._blocked:
            return
        self._rebuild_selection()

    def bind_stateful_command(self, command: StatefulCommandBase) -> None:
        """Switch the panel into command mode and show ``command``'s exports."""
        self.clear_stateful_command()
        cmd_name = self._format_command_name(getattr(command, "command_name", "Command"))
        self._set_mode_pill(cmd_name, active=True)
        self._set_idle_input_visible(False)
        self._cmd_input.clear()
        self._clear_suggestion_buttons()
        self._set_nav_shortcuts_enabled(True)

        for info in command.exports():
            row: _CmdRowBase
            if info.input_kind in ("point", "vector"):
                parser = self._parse_stateful_point_text
                placeholder = "x,y"
                if info.input_kind == "vector":
                    parser = self._parse_stateful_vector_text
                    placeholder = "dx,dy or n<a"
                row = _CmdPointRow(
                    info,
                    parser,
                    placeholder=placeholder,
                    parent=self._cmd_props_container,
                )
            else:
                row = _CmdScalarRow(info, self._cmd_props_container)

            row.activated.connect(lambda n=info.name: self._set_cmd_active(n))

            row.value_changed.connect(
                lambda v, n=info.name: self.property_changed.emit(n, v)
            )
            if isinstance(row, _CmdPointRow):
                row.preview_changed.connect(
                    lambda v, n=info.name: self.property_preview_changed.emit(n, v)
                )
            # Enter on a row → also move focus forward.  The forward step
            # happens after the editor advances active_export and emits
            # ``stateful_active_export_changed``; the panel listens on that
            # signal in :meth:`set_active_command_property` and focuses the
            # newly-active row.  ``advance_requested`` is therefore a UX
            # nudge: if the editor decides nothing changed (e.g. all
            # exports already set), we still move to the Commit button.
            row.advance_requested.connect(self._focus_after_row_advance)
            row.navigate_requested.connect(self._move_active_command_row)
            self._cmd_props_layout.addWidget(row)
            self._cmd_rows[info.name] = row

        if not command.active_export and self._cmd_rows:
            command.active_export = next(iter(self._cmd_rows.keys()))

        self._sync_cmd_values(command)
        self._sync_cmd_active(command)
        self._update_cmd_input_placeholder(command)
        self._cmd_props_container.show()
        self._cmd_action_row.show()
        self._focus_active_row(command, prefer_row=True)
        QTimer.singleShot(0, lambda c=command: self._focus_row_if_command_still_active(c))

    def clear_stateful_command(self) -> None:
        """Tear down stateful-command rows and return to idle mode."""
        self._cmd_rows.clear()
        while self._cmd_props_layout.count():
            item = self._cmd_props_layout.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cmd_props_container.hide()
        self._cmd_action_row.hide()
        self._set_mode_pill("Ready", active=False)
        self._set_idle_input_visible(True)
        self._cmd_input.setPlaceholderText("Type a command…")
        self._cmd_input.clear()
        self._clear_suggestion_buttons()
        self._set_nav_shortcuts_enabled(False)

    def set_command_property_value(self, name: str, value: Any) -> None:
        row = self._cmd_rows.get(name)
        if row is not None:
            row.set_value(value)  # type: ignore[union-attr]

    def set_active_command_property(self, name: str) -> None:  # noqa: ARG002 — name kept for API compat
        cmd = getattr(self._editor, "active_command", None)
        if isinstance(cmd, StatefulCommandBase):
            self._sync_cmd_active(cmd)
            self._update_cmd_input_placeholder(cmd)
            self._focus_active_row(cmd)

    def update_cursor_world(self, x: float, y: float) -> None:
        self._cursor_world = Vec2(x, y)
        self._refresh_cursor_label()

    def _parse_stateful_point_text(self, text: str) -> Vec2 | None:
        """Parse one point textbox value for stateful point exports.

        Behaviour is intentionally ergonomic for former X/Y rows:
        plain ``x,y`` (or ``x y``) is treated as absolute world coordinates,
        while advanced tokens (``#``, ``<``, ``@``) route through
        :class:`DynamicInputParser`.
        """
        raw = text.strip()
        if not raw:
            return None

        absolute = self._parse_absolute_point_pair(raw)
        if absolute is not None:
            return absolute

        from app.editor.dynamic_input_parser import DynamicInputParser

        base = getattr(self._editor, "snap_from_point", None)
        return DynamicInputParser.parse_vector(
            raw,
            current_pos=self._cursor_world,
            base_point=base,
        )

    def _parse_stateful_vector_text(self, text: str) -> Vec2 | None:
        """Parse one vector textbox value for stateful vector exports.

        Accepts direct components (``dx,dy`` / ``dx dy``) and polar form
        (``distance<angle`` or ``distance@angle``). Returned coordinates are
        vector components relative to ``(0, 0)``.
        """
        raw = text.strip()
        if not raw:
            return None

        from app.editor.dynamic_input_parser import DynamicInputParser

        return DynamicInputParser.parse_vector(
            raw,
            current_pos=self._cursor_world,
            base_point=Vec2(0, 0),
        )

    @staticmethod
    def _parse_absolute_point_pair(text: str) -> Vec2 | None:
        """Parse a direct absolute point pair from ``text``.

        Accepts ``x,y``, ``x;y`` and ``x y`` (with optional leading ``#``).
        Returns ``None`` for non-pair formats so callers can try richer parsers.
        """
        raw = text.strip()
        if raw.startswith("#"):
            raw = raw[1:].strip()
        normalized = raw.replace(";", ",")
        if "," in normalized:
            parts = [p.strip() for p in normalized.split(",")]
        else:
            parts = normalized.split()
        if len(parts) != 2:
            return None
        try:
            return Vec2(float(parts[0]), float(parts[1]))
        except ValueError:
            return None

    def focus_command_input(self) -> None:
        if not self._cmd_input_row.isVisible():
            cmd = getattr(self._editor, "active_command", None)
            if isinstance(cmd, StatefulCommandBase):
                self._focus_active_row(cmd, prefer_row=True)
            return
        self._cmd_input.setFocus()
        self._cmd_input.selectAll()

    def consume_escape_clear_input(self) -> bool:
        """Clear pending panel text on Escape and return True if consumed.

        Escape first clears text in the command search (idle mode) or the
        currently-focused stateful-command input row.  If no text is pending,
        callers should continue with normal Escape behaviour (cancel command,
        clear selection, etc.).
        """
        if self._cmd_input_row.isVisible() and self._cmd_input.text():
            self._cmd_input.clear()
            self._clear_suggestion_buttons()
            self._cmd_input.setFocus()
            return True

        if self._cmd_props_container.isVisible():
            for edit in self._cmd_props_container.findChildren(QLineEdit):
                if edit.hasFocus() and edit.text():
                    edit.clear()
                    return True
        return False

    def inject_text(self, text: str) -> None:
        """Append ``text`` to the command input and focus it.

        Called by :class:`MainWindow` when the canvas forwards a printable
        keystroke.  The user starts typing in the viewport and characters
        flow into the command input without having to click first.
        """
        if not text:
            return
        # Strip any control characters that slipped through.
        text = "".join(ch for ch in text if ch.isprintable())
        if not text:
            return
        cmd = getattr(self._editor, "active_command", None)
        if isinstance(cmd, StatefulCommandBase) and self._append_text_to_active_row(text):
            return
        self._cmd_input.setFocus()
        # Append rather than replace so multiple keystrokes accumulate.
        current = self._cmd_input.text()
        self._cmd_input.setText(current + text)
        self._cmd_input.setCursorPosition(len(self._cmd_input.text()))
        # Trigger the same suggestion refresh that real typing would.
        self._on_cmd_input_text_edited(self._cmd_input.text())

    def set_commands(self, commands: Dict[str, Any]) -> None:
        """Store the command catalog used for idle-mode suggestions."""
        self._all_commands = dict(commands)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        outer.addWidget(self._build_command_section())
        outer.addWidget(self._build_status_section())

        # Filter chip row (hidden until selection has multiple types).
        self._filter_frame = QWidget(self)
        filter_layout = QHBoxLayout(self._filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(4)
        self._filter_layout = filter_layout
        filter_layout.addStretch(1)
        self._filter_frame.setVisible(False)
        outer.addWidget(self._filter_frame)

        # Scrollable content area.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        self._content_layout.addStretch()

        scroll.setWidget(self._content)
        outer.addWidget(scroll, 1)

    # ---- command section ---------------------------------------------

    def _build_command_section(self) -> QWidget:
        wrap = QWidget(self)
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(4)

        # Mode pill row
        pill_row = QHBoxLayout()
        pill_row.setContentsMargins(0, 0, 0, 0)
        pill_row.setSpacing(6)
        self._mode_pill = QLabel("READY", wrap)
        self._mode_pill.setObjectName("ModePillIdle")
        self._mode_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill_row.addWidget(self._mode_pill)
        pill_row.addStretch(1)
        wrap_layout.addLayout(pill_row)

        # Command input row
        self._cmd_input_row = QWidget(wrap)
        input_row = QHBoxLayout(self._cmd_input_row)
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(4)
        self._cmd_prefix = QLabel(">", self._cmd_input_row)
        self._cmd_prefix.setObjectName("CommandPrefix")
        input_row.addWidget(self._cmd_prefix)

        self._cmd_input = _CommandInput(self._cmd_input_row)
        self._cmd_input.set_panel(self)
        self._cmd_input.setObjectName("CommandInput")
        self._cmd_input.setPlaceholderText("Type a command…")
        self._cmd_input.returnPressed.connect(self._on_cmd_input_return)
        self._cmd_input.textEdited.connect(self._on_cmd_input_text_edited)
        input_row.addWidget(self._cmd_input, 1)
        wrap_layout.addWidget(self._cmd_input_row)

        # Suggestions list (vertical, hidden until typing)
        self._suggestion_frame = QWidget(wrap)
        self._suggestion_layout = QVBoxLayout(self._suggestion_frame)
        self._suggestion_layout.setContentsMargins(2, 2, 2, 2)
        self._suggestion_layout.setSpacing(2)
        self._suggestion_frame.setVisible(False)
        wrap_layout.addWidget(self._suggestion_frame)

        # Stateful command properties (hidden until a stateful command runs)
        self._cmd_props_container = QWidget(wrap)
        self._cmd_props_layout = QVBoxLayout(self._cmd_props_container)
        self._cmd_props_layout.setContentsMargins(0, 4, 0, 0)
        self._cmd_props_layout.setSpacing(2)
        self._cmd_props_container.hide()
        wrap_layout.addWidget(self._cmd_props_container)

        # Commit / Cancel action row (hidden until a stateful command runs)
        self._cmd_action_row = QWidget(wrap)
        action_layout = QHBoxLayout(self._cmd_action_row)
        action_layout.setContentsMargins(0, 4, 0, 0)
        action_layout.setSpacing(6)

        self._cmd_cancel_btn = QPushButton("Cancel", self._cmd_action_row)
        self._cmd_cancel_btn.setObjectName("CancelButton")
        self._cmd_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cmd_cancel_btn.setToolTip("Esc")
        self._cmd_cancel_btn.clicked.connect(self.cancel_requested.emit)
        action_layout.addWidget(self._cmd_cancel_btn)

        action_layout.addStretch(1)

        self._cmd_commit_btn = QPushButton("Commit", self._cmd_action_row)
        self._cmd_commit_btn.setObjectName("CommitButton")
        self._cmd_commit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cmd_commit_btn.setToolTip("Enter")
        self._cmd_commit_btn.clicked.connect(self.commit_requested.emit)
        action_layout.addWidget(self._cmd_commit_btn)

        self._cmd_action_row.hide()
        wrap_layout.addWidget(self._cmd_action_row)

        wrap_layout.addWidget(_hr(wrap))
        return wrap

    # ---- status section (cursor + selection summary + toggles) -------

    def _build_status_section(self) -> QWidget:
        wrap = QWidget(self)
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Top row: selection summary on the left, cursor read-out on the right.
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        sel_col = QVBoxLayout()
        sel_col.setContentsMargins(0, 0, 0, 0)
        sel_col.setSpacing(0)
        self._sel_count_label = QLabel("No selection", wrap)
        self._sel_count_label.setObjectName("SelectionCount")
        self._sel_breakdown_label = QLabel("", wrap)
        self._sel_breakdown_label.setObjectName("SelectionBreakdown")
        self._sel_breakdown_label.hide()
        sel_col.addWidget(self._sel_count_label)
        sel_col.addWidget(self._sel_breakdown_label)
        top.addLayout(sel_col, 1)

        self._cursor_label = QLabel("", wrap)
        self._cursor_label.setObjectName("CursorReadout")
        self._cursor_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self._cursor_label, 0, Qt.AlignmentFlag.AlignRight)
        outer.addLayout(top)

        # Bottom row: workflow toggles (Auto-complete, Repeat command).
        toggles = QHBoxLayout()
        toggles.setContentsMargins(0, 0, 0, 0)
        toggles.setSpacing(12)

        self._auto_complete_check = QCheckBox("Auto complete", wrap)
        self._auto_complete_check.setObjectName("WorkflowToggle")
        self._auto_complete_check.setChecked(True)
        self._auto_complete_check.setToolTip(
            "Commit the active command automatically when every property has a value."
        )
        self._auto_complete_check.toggled.connect(self.auto_complete_toggled.emit)
        toggles.addWidget(self._auto_complete_check)

        self._repeat_check = QCheckBox("Repeat command", wrap)
        self._repeat_check.setObjectName("WorkflowToggle")
        self._repeat_check.setChecked(True)
        self._repeat_check.setToolTip(
            "Re-run the same command after each commit (cancel with Escape)."
        )
        self._repeat_check.toggled.connect(self.repeat_toggled.emit)
        toggles.addWidget(self._repeat_check)

        toggles.addStretch(1)
        outer.addLayout(toggles)

        return wrap

    # ------------------------------------------------------------------
    # Selection rebuild
    # ------------------------------------------------------------------

    def _selected_entities(self):
        ids = self._editor.selection.ids
        return [e for e in self._doc.entities if e.id in ids]

    def _rebuild_selection(self) -> None:
        entities = self._selected_entities()
        n = len(entities)

        # ── Selection summary --------------------------------------
        type_counts = Counter(e.type for e in entities)
        if n == 0:
            self._sel_count_label.setText("No selection")
            self._sel_breakdown_label.hide()
        elif n == 1:
            kind = entities[0].type
            self._sel_count_label.setText(f"1 {_TYPE_TITLES.get(kind, kind).lower()}")
            self._sel_breakdown_label.hide()
        else:
            self._sel_count_label.setText(f"{n} objects selected")
            parts = [
                f"{c}× {_TYPE_TITLES.get(t, t.capitalize())}"
                for t, c in sorted(type_counts.items())
            ]
            self._sel_breakdown_label.setText("  ·  ".join(parts))
            self._sel_breakdown_label.show()

        # ── Type-filter chips --------------------------------------
        all_types = sorted(type_counts.keys())
        self._rebuild_type_filters(all_types, type_counts)

        if len(all_types) <= 1:
            active_types = set(all_types)
        else:
            active_types = {t for t, btn in self._type_filters.items() if btn.isChecked()}

        visible = [e for e in entities if e.type in active_types]

        # ── Property cards -----------------------------------------
        self._clear_content()
        if not visible:
            self._content_layout.addStretch()
            return

        self._build_general_card(visible)

        if len(active_types) == 1:
            kind = next(iter(active_types))
            self._build_geometry_card(kind, visible)
        else:
            hint = QLabel(
                "Select a single type to edit geometry.",
                self._content,
            )
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color: {_TEXT_DIM}; font-size: 10px; padding: 8px 0;"
            )
            self._content_layout.addWidget(hint)

        self._content_layout.addStretch()

    def _clear_content(self) -> None:
        layout = self._content_layout
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()

    # ---- type filters -----------------------------------------------

    def _rebuild_type_filters(
        self,
        all_types: List[str],
        counts: Dict[str, int],
    ) -> None:
        show_filters = len(all_types) > 1

        # Drop chips for vanished types
        for t in list(self._type_filters.keys()):
            if t not in all_types:
                btn = self._type_filters.pop(t)
                self._filter_layout.removeWidget(btn)
                btn.deleteLater()

        # Insert chips for new types (preserve existing checked state)
        for t in all_types:
            btn = self._type_filters.get(t)
            if btn is None:
                btn = QPushButton(self._filter_frame)
                btn.setObjectName("TypeChip")
                btn.setCheckable(True)
                btn.setChecked(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.toggled.connect(self._on_filter_toggled)
                self._type_filters[t] = btn
                # Insert before the trailing stretch.
                self._filter_layout.insertWidget(self._filter_layout.count() - 1, btn)
            label = _TYPE_TITLES.get(t, t.capitalize())
            btn.setText(f"{label}  {counts.get(t, 0)}")

        self._filter_frame.setVisible(show_filters)

    def _on_filter_toggled(self, _checked: bool) -> None:
        self._rebuild_selection()

    # ------------------------------------------------------------------
    # General (shared) properties card
    # ------------------------------------------------------------------

    def _build_general_card(self, entities) -> None:
        card = _SectionCard("General", self._content)

        layer_names = ["ByLayer"] + [l.name for l in self._doc.layers]
        row_layer  = _PropRow(card, 0, "Layer",
                              widget_type="combo", options=layer_names)
        row_color  = _ColorRow(card, 1)
        row_weight = _PropRow(card, 2, "Line weight",
                              widget_type="combo", options=_LINE_WEIGHTS)
        row_style  = _PropRow(card, 3, "Line style",
                              widget_type="combo", options=_LINE_STYLES)

        v, u = _collect_uniform(entities, lambda e: getattr(e, "layer", None))
        row_layer.set_value(v, u)

        v, u = _collect_uniform(entities, lambda e: getattr(e, "color", None))
        row_color.set_value("ByLayer" if v is None and u else (v or ""), u)

        v, u = _collect_uniform(entities, lambda e: getattr(e, "line_weight", None))
        row_weight.set_value(
            "ByLayer" if v is None and u else (_fmt_float(v) if v is not None else "ByLayer"),
            u,
        )

        v, u = _collect_uniform(entities, lambda e: getattr(e, "line_style", None))
        row_style.set_value("ByLayer" if v is None and u else (v or "ByLayer"), u)

        row_layer.connect_changed(
            lambda r=row_layer: self._apply_common(entities, "layer", r.current_text())
        )
        row_color.connect_changed(
            lambda r=row_color: self._apply_common(entities, "color", r.current_text())
        )
        row_weight.connect_changed(
            lambda r=row_weight: self._apply_common_weight(entities, r.current_text())
        )
        row_style.connect_changed(
            lambda r=row_style: self._apply_common(entities, "line_style", r.current_text())
        )

        self._content_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Per-kind geometry card (driven by the schema dict)
    # ------------------------------------------------------------------

    def _build_geometry_card(self, kind: str, entities) -> None:
        factory = _GEOMETRY_SCHEMAS.get(kind)
        if factory is None:
            return
        title = _TYPE_TITLES.get(kind, kind.capitalize())
        card = _SectionCard(title, self._content)

        for i, field in enumerate(factory()):
            read_only = field.apply is None
            row = _PropRow(
                card,
                i,
                field.label,
                widget_type="lineedit",
                read_only=read_only,
                numeric=field.numeric,
            )
            v, u = _collect_uniform(entities, field.getter)
            display = field.fmt(v) if u and v is not None else (
                _VARIOUS if not u else ""
            )
            row.set_value(display, u)
            if not read_only and field.apply is not None:
                apply_fn = field.apply
                row.connect_changed(
                    lambda r=row, fn=apply_fn: self._apply_geo(entities, r, fn)
                )

        self._content_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Apply / undo helpers
    # ------------------------------------------------------------------

    def _apply_common(self, entities, attr: str, val: str) -> None:
        if val == _VARIOUS:
            return
        if attr == "layer":
            new = val
        elif attr in ("color", "line_style"):
            new = None if val in ("", "ByLayer") else val
        else:
            new = val or None

        changes = []
        for e in entities:
            old = getattr(e, attr, None)
            if old != new:
                changes.append((e.id, attr, old, new))
        if changes:
            self._push_undo(changes, f"Change {attr}")

    def _apply_common_weight(self, entities, val: str) -> None:
        if val == _VARIOUS:
            return
        new: Optional[float] = None
        if val not in ("", "ByLayer"):
            try:
                new = float(val)
            except ValueError:
                return
        changes = []
        for e in entities:
            old = e.line_weight
            if old != new:
                changes.append((e.id, "line_weight", old, new))
        if changes:
            self._push_undo(changes, "Change line weight")

    def _apply_geo(
        self,
        entities,
        row: _PropRow,
        apply_fn: Callable[[Any, str], None],
    ) -> None:
        """Apply a geometry edit by snapshotting → mutating → diffing.

        Each entity's attributes are captured before *apply_fn* runs.  After
        the call we walk the (possibly mutated) attribute set, record the
        ``(id, attr, old, new)`` tuples, then restore the entity in-place so
        the undo command can re-apply them with full undo semantics.
        """
        if row.is_various():
            return
        text = row.current_text()
        changes: List[Tuple[Any, str, Any, Any]] = []
        for e in entities:
            before = {k: v for k, v in e.__dict__.items() if not k.startswith("_")}
            apply_fn(e, text)
            for k, new_v in e.__dict__.items():
                if k.startswith("_"):
                    continue
                old_v = before.get(k)
                if old_v != new_v:
                    changes.append((e.id, k, old_v, new_v))
            for k, old_v in before.items():
                setattr(e, k, old_v)
        if changes:
            self._push_undo(changes, "Change geometry")

    def _push_undo(self, changes, description: str) -> None:
        self._blocked = True
        try:
            cmd = SetEntityPropertiesUndoCommand(self._doc, changes, description)
            self._editor._undo_stack.push(cmd, execute_on_push=True)
            self._editor.document_changed.emit()
            self.properties_changed.emit()
        finally:
            self._blocked = False

    # ------------------------------------------------------------------
    # Mode pill / cursor read-out
    # ------------------------------------------------------------------

    def _set_idle_input_visible(self, visible: bool) -> None:
        self._cmd_input_row.setVisible(visible)
        self._cmd_input.setEnabled(visible)
        if not visible:
            self._cmd_input.clearFocus()

    def _set_mode_pill(self, text: str, *, active: bool) -> None:
        self._mode_pill.setText(text.upper())
        self._mode_pill.setObjectName("ModePillActive" if active else "ModePillIdle")
        self._mode_pill.style().unpolish(self._mode_pill)
        self._mode_pill.style().polish(self._mode_pill)

    def _refresh_cursor_label(self) -> None:
        self._cursor_label.setText(
            f"{_fmt_float(self._cursor_world.x)} , {_fmt_float(self._cursor_world.y)}"
        )

    # ------------------------------------------------------------------
    # Stateful command sync
    # ------------------------------------------------------------------

    def _sync_cmd_values(self, command: StatefulCommandBase) -> None:
        for name, row in self._cmd_rows.items():
            row.set_value(getattr(command, name, None))  # type: ignore[union-attr]

    def _sync_cmd_active(self, command: StatefulCommandBase) -> None:
        active = command.active_export
        for name, row in self._cmd_rows.items():
            row.set_active(name == active)  # type: ignore[union-attr]

    def _focus_active_row(self, command: StatefulCommandBase, *, prefer_row: bool = False) -> None:
        """Move keyboard focus to the active export's row, or to Commit.

        Called after the editor changes the active export (mouse click in
        viewport, row Enter, etc.).  When every export has a value the
        active export does not move, so we drop focus on the Commit
        button instead — one Enter from there finishes the command.
        """
        active = command.active_export
        # When all exports are set, the editor leaves active_export as-is;
        # we should land focus on Commit so Enter finalises the command.
        if command.all_exports_set() and not prefer_row:
            self._cmd_commit_btn.setFocus()
            return
        row = self._cmd_rows.get(active)
        if not isinstance(row, _CmdRowBase) and self._cmd_rows:
            first_name = next(iter(self._cmd_rows.keys()))
            if active != first_name:
                command.active_export = first_name
                self._sync_cmd_active(command)
                self._update_cmd_input_placeholder(command)
            row = self._cmd_rows.get(first_name)
        if isinstance(row, _CmdRowBase):
            row.focus_input()

    def _focus_row_if_command_still_active(self, command: StatefulCommandBase) -> None:
        if getattr(self._editor, "active_command", None) is command:
            self._focus_active_row(command, prefer_row=True)

    def _focus_after_row_advance(self) -> None:
        """Slot wired to every row's ``advance_requested`` signal.

        The editor's :meth:`set_stateful_property` will also fire
        ``stateful_active_export_changed`` which calls
        :meth:`set_active_command_property` (and therefore moves focus).
        This handler is a fallback for the case where no signal arrives
        (e.g. the user pressed Enter on a row that did not produce a new
        value) — we still want focus to land on the next sensible widget.
        """
        cmd = getattr(self._editor, "active_command", None)
        if isinstance(cmd, StatefulCommandBase):
            self._focus_active_row(cmd)

    def _set_cmd_active(self, name: str) -> None:
        cmd = getattr(self._editor, "active_command", None)
        if isinstance(cmd, StatefulCommandBase):
            cmd.active_export = name
            self._sync_cmd_active(cmd)
            self._update_cmd_input_placeholder(cmd)

    def _move_active_command_row(self, delta: int) -> None:
        cmd = getattr(self._editor, "active_command", None)
        if not isinstance(cmd, StatefulCommandBase):
            return
        names = list(self._cmd_rows.keys())
        if not names:
            return
        if cmd.active_export in names:
            idx = names.index(cmd.active_export)
        else:
            idx = 0
        idx = (idx + delta) % len(names)
        self._set_cmd_active(names[idx])
        self._focus_active_row(cmd, prefer_row=True)

    def _append_text_to_active_row(self, text: str) -> bool:
        cmd = getattr(self._editor, "active_command", None)
        if not isinstance(cmd, StatefulCommandBase):
            return False
        row = self._cmd_rows.get(cmd.active_export)
        if not isinstance(row, _CmdRowBase) and self._cmd_rows:
            first_name = next(iter(self._cmd_rows.keys()))
            self._set_cmd_active(first_name)
            row = self._cmd_rows.get(first_name)
        if not isinstance(row, _CmdRowBase):
            return False
        self._focus_active_row(cmd, prefer_row=True)
        row.append_text(text)
        return True

    def _install_shortcuts(self) -> None:
        self._cmd_nav_up_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        self._cmd_nav_up_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._cmd_nav_up_shortcut.activated.connect(lambda: self._move_active_command_row(-1))
        self._cmd_nav_down_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        self._cmd_nav_down_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._cmd_nav_down_shortcut.activated.connect(lambda: self._move_active_command_row(1))
        self._set_nav_shortcuts_enabled(False)

    def _set_nav_shortcuts_enabled(self, enabled: bool) -> None:
        self._cmd_nav_up_shortcut.setEnabled(enabled)
        self._cmd_nav_down_shortcut.setEnabled(enabled)

    def _update_cmd_input_placeholder(self, command: StatefulCommandBase) -> None:
        active = command.active_export
        for info in command.exports():
            if info.name == active:
                self._cmd_input.setPlaceholderText(f"{info.label}…")
                return
        self._cmd_input.setPlaceholderText("Type a value…")

    @staticmethod
    def _format_command_name(raw: str) -> str:
        """Pretty-print a registered command id like ``core.DrawLineCommand``."""
        return (
            raw.replace("core.", "")
               .replace("Command", "")
               .replace("_", " ")
               .strip()
               .title()
            or "Command"
        )

    # ------------------------------------------------------------------
    # Command input + idle-mode suggestions
    # ------------------------------------------------------------------

    def _on_cmd_input_return(self) -> None:
        text = self._cmd_input.text().strip()
        if not text:
            return
        cmd = getattr(self._editor, "active_command", None)
        if isinstance(cmd, StatefulCommandBase):
            self._cmd_input.clear()
            self.header_value_submitted.emit(text)
            return
        if self._suggestion_buttons and 0 <= self._suggestion_index < len(self._suggestion_buttons):
            self._activate_selected_suggestion()
            return
        # Idle mode: run the best match and clear suggestions.
        self._run_matched_command(text)
        self._cmd_input.clear()
        self._clear_suggestion_buttons()

    def _on_cmd_input_text_edited(self, text: str) -> None:
        cmd = getattr(self._editor, "active_command", None)
        if isinstance(cmd, StatefulCommandBase):
            self._clear_suggestion_buttons()
            return
        self._refresh_suggestion_buttons(text)

    def _command_score(self, cmd_id: str, spec: Any, typed: str) -> Optional[int]:
        """Return a sort key for how well ``cmd_id`` / ``spec`` matches ``typed``.

        Lower is better.  ``None`` means no match.
        """
        if not typed:
            return None
        label = getattr(spec, "display_name", cmd_id)
        aliases = tuple(getattr(spec, "aliases", ()))
        cid_l = cmd_id.lower()
        lab_l = label.lower()
        ali_l = tuple(a.lower() for a in aliases)
        if cid_l == typed:                          return 0
        if typed in ali_l:                          return 1
        if lab_l == typed:                          return 2
        if lab_l.startswith(typed):                 return 3
        if cid_l.startswith(typed):                 return 4
        if any(a.startswith(typed) for a in ali_l): return 5
        if typed in lab_l:                          return 6
        if typed in cid_l:                          return 7
        return None

    def _refresh_suggestion_buttons(self, text: str) -> None:
        self._clear_suggestion_buttons()
        typed = text.strip().lower()
        if not typed:
            self._suggestion_frame.setVisible(False)
            return

        matches: List[Tuple[int, str, str, Tuple[str, ...]]] = []
        for cmd_id, spec in self._all_commands.items():
            score = self._command_score(cmd_id, spec, typed)
            if score is None:
                continue
            label = getattr(spec, "display_name", cmd_id)
            aliases = tuple(getattr(spec, "aliases", ()))
            matches.append((score, cmd_id, label, aliases))
        matches.sort(key=lambda t: (t[0], t[2].lower()))
        matches = matches[:5]

        for _score, cmd_id, label, aliases in matches:
            btn = QToolButton(self._suggestion_frame)
            btn.setObjectName("SuggestionButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setToolTip(cmd_id)
            alias_hint = f"  ({', '.join(aliases)})" if aliases else ""
            btn.setText(f"{label}{alias_hint}")
            btn.clicked.connect(
                lambda _checked=False, cid=cmd_id: self._run_command(cid)
            )
            self._suggestion_layout.addWidget(btn)
            self._suggestion_buttons.append(btn)

        self._suggestion_frame.setVisible(bool(self._suggestion_buttons))
        # Pre-select the top match so a single Enter runs it.
        self._suggestion_index = 0 if self._suggestion_buttons else -1
        self._refresh_suggestion_highlight()

    def _clear_suggestion_buttons(self) -> None:
        for btn in self._suggestion_buttons:
            self._suggestion_layout.removeWidget(btn)
            btn.deleteLater()
        self._suggestion_buttons.clear()
        self._suggestion_index = -1
        self._suggestion_frame.setVisible(False)

    def _move_suggestion_cursor(self, delta: int) -> None:
        if not self._suggestion_buttons:
            return
        n = len(self._suggestion_buttons)
        if self._suggestion_index < 0:
            self._suggestion_index = 0 if delta > 0 else n - 1
        else:
            self._suggestion_index = (self._suggestion_index + delta) % n
        self._refresh_suggestion_highlight()

    def _activate_selected_suggestion(self) -> None:
        if 0 <= self._suggestion_index < len(self._suggestion_buttons):
            self._suggestion_buttons[self._suggestion_index].click()

    def _refresh_suggestion_highlight(self) -> None:
        for i, btn in enumerate(self._suggestion_buttons):
            btn.setProperty("selected", "true" if i == self._suggestion_index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _run_matched_command(self, text: str) -> None:
        typed = text.strip().lower()
        if not typed:
            return
        best_id: Optional[str] = None
        best_score = 999
        for cmd_id, spec in self._all_commands.items():
            score = self._command_score(cmd_id, spec, typed)
            if score is not None and score < best_score:
                best_score = score
                best_id = cmd_id
        if best_id is not None:
            self._run_command(best_id)

    def _run_command(self, cmd_id: str) -> None:
        self._cmd_input.clear()
        self._clear_suggestion_buttons()
        self.command_requested.emit(cmd_id)
