"""
Properties Panel — dockable inspector for selected entities.

Shows editable properties for the current selection:
- Common properties (layer, color, line weight, line style) for all types.
- Type-specific geometry properties per entity kind.
- "Various" placeholder when selected entities of the same type have differing
  values for a field.
- Type-filter checkboxes when more than one entity kind is selected, so the
  user can narrow which types are displayed/edited.

Wiring (done in MainWindow):
    panel = PropertiesPanel(document, editor, parent=self)
    editor.selection.changed.connect(panel.refresh)
    dock = QDockWidget("Properties", self)
    dock.setWidget(panel)
    self.addDockWidget(Qt.RightDockWidgetArea, dock)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QFrame, QScrollArea, QCheckBox, QSizePolicy,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFocusEvent

from app.document import DocumentStore
from app.editor.undo import SetEntityPropertiesUndoCommand


# ---------------------------------------------------------------------------
# Constants / palette (matches existing dark theme)
# ---------------------------------------------------------------------------

_BG       = "#2d2d2d"
_BG_INNER = "#252525"
_BORDER   = "#3a3a3a"
_TEXT     = "#e0e0e0"
_TEXT_DIM = "#777"
_EMERALD  = "#0FB881"
_BTN_BG   = "#353535"

_VARIOUS  = "various"   # sentinel display string for mixed values

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
QLabel[role="header"] {{
    color: {_EMERALD};
    font-weight: bold;
    font-size: 10px;
    padding: 4px 0 2px 0;
}}
QLabel[role="key"] {{
    color: {_TEXT_DIM};
    padding-right: 4px;
}}
QLineEdit {{
    background: {_BG_INNER};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 3px;
    padding: 2px 5px;
    min-height: 20px;
}}
QLineEdit:focus {{
    border-color: {_EMERALD};
}}
QLineEdit[various="true"] {{
    color: {_TEXT_DIM};
    font-style: italic;
}}
QComboBox {{
    background: {_BTN_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 3px;
    padding: 2px 6px;
    min-height: 20px;
}}
QComboBox:focus {{
    border-color: {_EMERALD};
}}
QComboBox::drop-down {{
    border: none;
    width: 14px;
}}
QComboBox QAbstractItemView {{
    background: #333;
    color: {_TEXT};
    border: 1px solid #444;
    selection-background-color: {_EMERALD};
    outline: none;
}}
QCheckBox {{
    color: {_TEXT};
    spacing: 5px;
}}
QCheckBox::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {_BORDER};
    border-radius: 2px;
    background: {_BG_INNER};
}}
QCheckBox::indicator:checked {{
    background: {_EMERALD};
    border-color: {_EMERALD};
}}
QFrame[role="separator"] {{
    background: {_BORDER};
    max-height: 1px;
    margin: 4px 0;
}}
"""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _sep(parent: QWidget) -> QFrame:
    """Thin horizontal divider."""
    f = QFrame(parent)
    f.setProperty("role", "separator")
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    return f


def _header(text: str, parent: QWidget) -> QLabel:
    lbl = QLabel(text.upper(), parent)
    lbl.setProperty("role", "header")
    return lbl


def _key_label(text: str, parent: QWidget) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setProperty("role", "key")
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return lbl


def _collect_values(entities, attr: str) -> Tuple[Any, bool]:
    """Return (value, is_uniform).  value is None when empty."""
    values = {getattr(e, attr, None) for e in entities}
    if len(values) == 0:
        return None, True
    if len(values) == 1:
        return next(iter(values)), True
    return None, False  # various


def _fmt_float(v: Optional[float], decimals: int = 4) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return f"{v:.{decimals}g}"


def _fmt_vec(v) -> str:
    if v is None:
        return ""
    return f"{_fmt_float(v.x)}, {_fmt_float(v.y)}"


def _fmt_angle_deg(v: Optional[float]) -> str:
    if v is None:
        return ""
    return f"{math.degrees(v):.4g}°"


# ---------------------------------------------------------------------------
# Auto-selecting line edit — selects all text when focused by click or Tab
# ---------------------------------------------------------------------------

class _AutoSelectLineEdit(QLineEdit):
    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        # selectAll() called directly here is clobbered by the mouse-release
        # that follows a click, so defer it one event-loop tick.
        QTimer.singleShot(0, self.selectAll)


# ---------------------------------------------------------------------------
# Row factory — one label + one editable widget
# ---------------------------------------------------------------------------

class _PropRow:
    """A key/value row in the grid."""

    def __init__(
        self,
        grid: QGridLayout,
        row: int,
        key: str,
        *,
        widget_type: str = "lineedit",  # "lineedit" | "combo"
        options: Optional[List[str]] = None,
        parent: QWidget,
        read_only: bool = False,
    ) -> None:
        self.key = key
        self.widget_type = widget_type
        self._parent = parent

        lbl = _key_label(key, parent)
        grid.addWidget(lbl, row, 0)

        if widget_type == "combo" and options:
            self.widget: QWidget = QComboBox(parent)
            self.widget.addItems(options)
            self.widget.setFixedHeight(22)
            # Disable if read_only (combos don't have a read-only mode)
            self.widget.setEnabled(not read_only)
        else:
            self.widget = _AutoSelectLineEdit(parent)
            self.widget.setFixedHeight(22)
            if read_only:
                self.widget.setReadOnly(True)

        grid.addWidget(self.widget, row, 1)

    def set_value(self, value: Any, is_uniform: bool) -> None:
        if self.widget_type == "combo":
            w: QComboBox = self.widget  # type: ignore[assignment]
            w.blockSignals(True)
            if not is_uniform:
                # Insert a transient "(various)" item at top if not already there
                if w.itemText(0) != _VARIOUS:
                    w.insertItem(0, _VARIOUS)
                w.setCurrentIndex(0)
            else:
                # Remove transient "(various)" item if present
                if w.itemText(0) == _VARIOUS:
                    w.removeItem(0)
                txt = str(value) if value is not None else ""
                idx = w.findText(txt)
                if idx >= 0:
                    w.setCurrentIndex(idx)
                else:
                    w.setCurrentIndex(0)
            w.blockSignals(False)
        else:
            w: QLineEdit = self.widget  # type: ignore[assignment]
            w.blockSignals(True)
            if not is_uniform:
                w.setText(_VARIOUS)
                w.setProperty("various", "true")
            else:
                w.setProperty("various", "false")
                w.setText(str(value) if value is not None else "")
            # Force stylesheet re-evaluation
            w.style().unpolish(w)
            w.style().polish(w)
            w.blockSignals(False)

    def current_text(self) -> str:
        if self.widget_type == "combo":
            return self.widget.currentText()  # type: ignore[union-attr]
        return self.widget.text()  # type: ignore[union-attr]

    def is_various(self) -> bool:
        if self.widget_type == "combo":
            return self.widget.currentText() == _VARIOUS  # type: ignore[union-attr]
        return self.widget.text() == _VARIOUS  # type: ignore[union-attr]

    def connect_changed(self, slot) -> None:
        if self.widget_type == "combo":
            # currentTextChanged passes the new text as an argument; wrap so
            # all callers receive a consistent zero-argument call.
            self.widget.currentTextChanged.connect(lambda _: slot())  # type: ignore[union-attr]
        else:
            self.widget.editingFinished.connect(slot)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class PropertiesPanel(QWidget):
    """Dockable properties inspector.

    Parameters
    ----------
    document:
        The live :class:`DocumentStore`.
    editor:
        The :class:`Editor` — used to push undo commands and access selection.
    """

    properties_changed = Signal()

    def __init__(self, document: DocumentStore, editor, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._doc = document
        self._editor = editor
        self._blocked = False           # prevent re-entrant refresh from our own changes
        self._active_types: Set[str] = set()  # entity kinds currently shown
        self._type_filters: Dict[str, QCheckBox] = {}

        self.setStyleSheet(_PANEL_STYLE)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        # ── Title / entity count label ──────────────────────────────
        self._count_label = QLabel("No selection", self)
        self._count_label.setAlignment(Qt.AlignCenter)
        self._count_label.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px; padding: 2px 0;")
        outer.addWidget(self._count_label)

        outer.addWidget(_sep(self))

        # ── Type-filter row (hidden when only one type) ─────────────
        self._filter_frame = QFrame(self)
        self._filter_layout = QVBoxLayout(self._filter_frame)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_layout.setSpacing(2)
        self._filter_frame.setVisible(False)
        outer.addWidget(self._filter_frame)

        self._filter_sep = _sep(self)
        self._filter_sep.setVisible(False)
        outer.addWidget(self._filter_sep)

        # ── Scrollable content area ──────────────────────────────────
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {_BG}; border: none; }}")

        self._content = QWidget()
        self._content.setStyleSheet(f"background: {_BG};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)
        self._content_layout.addStretch()

        scroll.setWidget(self._content)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public refresh entry point
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the panel from the current selection."""
        if self._blocked:
            return
        self._rebuild()

    # ------------------------------------------------------------------
    # Internal rebuild
    # ------------------------------------------------------------------

    def _selected_entities(self):
        ids = self._editor.selection.ids
        return [e for e in self._doc.entities if e.id in ids]

    def _rebuild(self) -> None:
        entities = self._selected_entities()

        # ── Count label ────────────────────────────────────────────
        n = len(entities)
        if n == 0:
            self._count_label.setText("No selection")
        elif n == 1:
            self._count_label.setText(f"1 {entities[0].type}")
        else:
            self._count_label.setText(f"{n} objects selected")

        # ── Determine entity types present ─────────────────────────
        all_types: List[str] = sorted({e.type for e in entities})

        # ── Update / create type-filter checkboxes ──────────────────
        self._rebuild_type_filters(all_types)

        # ── Determine which types are active (enabled by filter) ────
        if len(all_types) <= 1:
            active_types = set(all_types)
        else:
            active_types = {t for t, cb in self._type_filters.items() if cb.isChecked()}

        self._active_types = active_types

        # ── Filter entities to only active types ────────────────────
        visible = [e for e in entities if e.type in active_types]

        # ── Clear and rebuild content area ──────────────────────────
        self._clear_content()
        if not visible:
            self._content_layout.addStretch()
            return

        # Common properties section (always shown for any selection)
        self._build_common_section(visible)

        # Geometry section — only when all visible entities share one type.
        # When multiple types are active the filter checkboxes let the user
        # narrow down to a single type; until then only common fields apply.
        if len(active_types) == 1:
            kind = next(iter(active_types))
            self._build_type_section(kind, visible)
        else:
            hint = QLabel("Select a single type\nto see geometry properties.", self._content)
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px; padding: 8px 0;")
            self._content_layout.addWidget(hint)

        self._content_layout.addStretch()

    # ------------------------------------------------------------------
    # Type-filter checkboxes
    # ------------------------------------------------------------------

    def _rebuild_type_filters(self, all_types: List[str]) -> None:
        show_filters = len(all_types) > 1

        # Remove stale checkboxes
        for t in list(self._type_filters.keys()):
            if t not in all_types:
                cb = self._type_filters.pop(t)
                self._filter_layout.removeWidget(cb)
                cb.deleteLater()

        # Add missing checkboxes
        for t in all_types:
            if t not in self._type_filters:
                cb = QCheckBox(t.capitalize(), self._filter_frame)
                cb.setChecked(True)
                cb.toggled.connect(self._on_filter_toggled)
                self._type_filters[t] = cb
                self._filter_layout.addWidget(cb)

        self._filter_frame.setVisible(show_filters)
        self._filter_sep.setVisible(show_filters)

    def _on_filter_toggled(self, _checked: bool) -> None:
        self._rebuild()

    # ------------------------------------------------------------------
    # Content clearing
    # ------------------------------------------------------------------

    def _clear_content(self) -> None:
        layout = self._content_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    # Common section (layer, color, line weight, line style)
    # ------------------------------------------------------------------

    def _build_common_section(self, entities) -> None:
        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)

        hdr = _header("General", frame)
        grid.addWidget(hdr, 0, 0, 1, 2)

        layer_names = ["ByLayer"] + [l.name for l in self._doc.layers]
        row_layer  = _PropRow(grid, 1, "Layer",       widget_type="combo", options=layer_names, parent=frame)
        row_color  = _PropRow(grid, 2, "Color",       widget_type="lineedit", parent=frame)
        row_weight = _PropRow(grid, 3, "Line weight", widget_type="combo",    options=_LINE_WEIGHTS, parent=frame)
        row_style  = _PropRow(grid, 4, "Line style",  widget_type="combo",    options=_LINE_STYLES,  parent=frame)

        # Populate
        v, u = _collect_values(entities, "layer")
        row_layer.set_value(v, u)

        v, u = _collect_values(entities, "color")
        row_color.set_value("ByLayer" if v is None and u else (v or ""), u)

        v, u = _collect_values(entities, "line_weight")
        row_weight.set_value("ByLayer" if v is None and u else (_fmt_float(v) if v is not None else "ByLayer"), u)

        v, u = _collect_values(entities, "line_style")
        row_style.set_value("ByLayer" if v is None and u else (v or "ByLayer"), u)

        # Wire changes
        row_layer.connect_changed(
            lambda row=row_layer: self._apply_common(entities, "layer", row.current_text()))
        row_color.connect_changed(
            lambda row=row_color: self._apply_common(entities, "color", row.current_text()))
        row_weight.connect_changed(
            lambda row=row_weight: self._apply_common_weight(entities, row.current_text()))
        row_style.connect_changed(
            lambda row=row_style: self._apply_common(entities, "line_style", row.current_text()))

        self._content_layout.addWidget(frame)

    # ------------------------------------------------------------------
    # Per-type geometry section
    # ------------------------------------------------------------------

    def _build_type_section(self, kind: str, entities) -> None:
        builders = {
            "line":      self._build_line_section,
            "circle":    self._build_circle_section,
            "arc":       self._build_arc_section,
            "rect":      self._build_rect_section,
            "polyline":  self._build_polyline_section,
            "text":      self._build_text_section,
            "dimension": self._build_dimension_section,
            "hatch":     self._build_hatch_section,
        }
        builder = builders.get(kind)
        if builder:
            builder(entities)

    def _make_section_frame(self) -> QWidget:
        f = QWidget(self._content)
        f.setStyleSheet(f"background: {_BG_INNER}; border-radius: 4px;")
        return f

    def _add_geo_section(self, title: str, rows_spec: List[Tuple], entities) -> None:
        """Generic geometry section builder.

        rows_spec: list of (display_key, attr, fmt_fn, read_only, apply_fn_or_None)
        fmt_fn(value) → str
        apply_fn(entities, new_str) → None   (None means read-only)
        """
        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)

        hdr = _header(title, frame)
        grid.addWidget(hdr, 0, 0, 1, 2)

        for i, (key, attr, fmt_fn, read_only, apply_fn) in enumerate(rows_spec, start=1):
            r = _PropRow(grid, i, key, widget_type="lineedit", parent=frame, read_only=read_only)
            # Collect and format
            raw_values = [getattr(e, attr, None) for e in entities]
            unique = set()
            for rv in raw_values:
                unique.add(rv)
            is_uniform = len(unique) == 1
            display_val = fmt_fn(raw_values[0]) if is_uniform else _VARIOUS
            r.set_value(display_val, is_uniform)

            if apply_fn is not None and not read_only:
                r.connect_changed(
                    lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn)
                )

        self._content_layout.addWidget(frame)

    def _apply_geo(self, entities, row: _PropRow, apply_fn) -> None:
        """Apply a geometry mutation via apply_fn, building an undo-able change list."""
        if row.is_various():
            return
        text = row.current_text()
        changes = []
        for e in entities:
            # Snapshot every attribute before mutation so we can diff after.
            before = {k: v for k, v in e.__dict__.items() if not k.startswith("_")}
            apply_fn(e, text)
            after = e.__dict__
            for k, new_v in after.items():
                if k.startswith("_"):
                    continue
                old_v = before.get(k)
                if old_v != new_v:
                    changes.append((e.id, k, old_v, new_v))
            # Restore: undo command will re-apply via setattr on redo
            for k, old_v in before.items():
                setattr(e, k, old_v)
        if changes:
            self._push_undo(changes, "Change geometry", execute=True)

    # ------------------------------------------------------------------
    # Apply helpers
    # ------------------------------------------------------------------

    def _apply_common(self, entities, attr: str, val: str, _rows=()) -> None:
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
            self._push_undo(changes, f"Change {attr}", execute=True)

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
            self._push_undo(changes, "Change line weight", execute=True)

    def _push_undo(self, changes, description: str, *, execute: bool = True) -> None:
        self._blocked = True
        try:
            cmd = SetEntityPropertiesUndoCommand(self._doc, changes, description)
            self._editor._undo_stack.push(cmd, execute_on_push=execute)
            self._editor.document_changed.emit()
            self.properties_changed.emit()
        finally:
            self._blocked = False

    # ------------------------------------------------------------------
    # Per-type section builders
    # ------------------------------------------------------------------

    def _build_line_section(self, entities) -> None:
        from app.entities import Vec2

        def _apply_p1_x(e, s): e.p1 = Vec2(_parse_float(s, e.p1.x), e.p1.y)
        def _apply_p1_y(e, s): e.p1 = Vec2(e.p1.x, _parse_float(s, e.p1.y))
        def _apply_p2_x(e, s): e.p2 = Vec2(_parse_float(s, e.p2.x), e.p2.y)
        def _apply_p2_y(e, s): e.p2 = Vec2(e.p2.x, _parse_float(s, e.p2.y))

        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Line", frame), 0, 0, 1, 2)

        specs = [
            ("Start X", lambda e: e.p1.x, _apply_p1_x),
            ("Start Y", lambda e: e.p1.y, _apply_p1_y),
            ("End X",   lambda e: e.p2.x, _apply_p2_x),
            ("End Y",   lambda e: e.p2.y, _apply_p2_y),
            ("Length",  lambda e: math.hypot(e.p2.x - e.p1.x, e.p2.y - e.p1.y), None),
        ]
        for i, (key, getter, apply_fn) in enumerate(specs, start=1):
            ro = apply_fn is None
            r = _PropRow(grid, i, key, parent=frame, read_only=ro)
            raw = [getter(e) for e in entities]
            is_u = len(set(raw)) == 1
            r.set_value(_fmt_float(raw[0]) if is_u else _VARIOUS, is_u)
            if apply_fn:
                r.connect_changed(
                    lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn))

        self._content_layout.addWidget(frame)

    def _build_circle_section(self, entities) -> None:
        from app.entities import Vec2

        def _apply_cx(e, s): e.center = Vec2(_parse_float(s, e.center.x), e.center.y)
        def _apply_cy(e, s): e.center = Vec2(e.center.x, _parse_float(s, e.center.y))
        def _apply_r(e, s):
            v = _parse_float(s, e.radius)
            if v > 0:
                e.radius = v

        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Circle", frame), 0, 0, 1, 2)

        specs = [
            ("Center X", lambda e: e.center.x, _apply_cx),
            ("Center Y", lambda e: e.center.y, _apply_cy),
            ("Radius",   lambda e: e.radius,   _apply_r),
            ("Diameter", lambda e: e.radius * 2, None),
        ]
        for i, (key, getter, apply_fn) in enumerate(specs, start=1):
            ro = apply_fn is None
            r = _PropRow(grid, i, key, parent=frame, read_only=ro)
            raw = [getter(e) for e in entities]
            is_u = len(set(raw)) == 1
            r.set_value(_fmt_float(raw[0]) if is_u else _VARIOUS, is_u)
            if apply_fn:
                r.connect_changed(
                    lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn))

        self._content_layout.addWidget(frame)

    def _build_arc_section(self, entities) -> None:
        from app.entities import Vec2

        def _apply_cx(e, s): e.center = Vec2(_parse_float(s, e.center.x), e.center.y)
        def _apply_cy(e, s): e.center = Vec2(e.center.x, _parse_float(s, e.center.y))
        def _apply_r(e, s):
            v = _parse_float(s, e.radius)
            if v > 0:
                e.radius = v
        def _apply_sa(e, s): e.start_angle = math.radians(_parse_float(s, math.degrees(e.start_angle)))
        def _apply_ea(e, s): e.end_angle   = math.radians(_parse_float(s, math.degrees(e.end_angle)))

        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Arc", frame), 0, 0, 1, 2)

        from app.entities.arc import _arc_span as _arc_span_fn

        specs = [
            ("Center X",    lambda e: e.center.x,                                _apply_cx),
            ("Center Y",    lambda e: e.center.y,                                _apply_cy),
            ("Radius",      lambda e: e.radius,                                  _apply_r),
            ("Start angle", lambda e: math.degrees(e.start_angle),              _apply_sa),
            ("End angle",   lambda e: math.degrees(e.end_angle),                _apply_ea),
            ("Span",        lambda e: abs(math.degrees(
                _arc_span_fn(e.start_angle, e.end_angle, e.ccw))),               None),
        ]
        for i, (key, getter, apply_fn) in enumerate(specs, start=1):
            ro = apply_fn is None
            r = _PropRow(grid, i, key, parent=frame, read_only=ro)
            raw = [getter(e) for e in entities]
            is_u = len(set(raw)) == 1
            r.set_value(_fmt_float(raw[0]) if is_u else _VARIOUS, is_u)
            if apply_fn:
                r.connect_changed(
                    lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn))

        self._content_layout.addWidget(frame)

    def _build_rect_section(self, entities) -> None:
        from app.entities import Vec2

        def _apply_p1x(e, s): e.p1 = Vec2(_parse_float(s, e.p1.x), e.p1.y)
        def _apply_p1y(e, s): e.p1 = Vec2(e.p1.x, _parse_float(s, e.p1.y))
        def _apply_p2x(e, s): e.p2 = Vec2(_parse_float(s, e.p2.x), e.p2.y)
        def _apply_p2y(e, s): e.p2 = Vec2(e.p2.x, _parse_float(s, e.p2.y))

        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Rectangle", frame), 0, 0, 1, 2)

        specs = [
            ("Corner 1 X", lambda e: e.p1.x, _apply_p1x),
            ("Corner 1 Y", lambda e: e.p1.y, _apply_p1y),
            ("Corner 2 X", lambda e: e.p2.x, _apply_p2x),
            ("Corner 2 Y", lambda e: e.p2.y, _apply_p2y),
            ("Width",  lambda e: abs(e.p2.x - e.p1.x), None),
            ("Height", lambda e: abs(e.p2.y - e.p1.y), None),
        ]
        for i, (key, getter, apply_fn) in enumerate(specs, start=1):
            ro = apply_fn is None
            r = _PropRow(grid, i, key, parent=frame, read_only=ro)
            raw = [getter(e) for e in entities]
            is_u = len(set(raw)) == 1
            r.set_value(_fmt_float(raw[0]) if is_u else _VARIOUS, is_u)
            if apply_fn:
                r.connect_changed(
                    lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn))

        self._content_layout.addWidget(frame)

    def _build_polyline_section(self, entities) -> None:
        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Polyline", frame), 0, 0, 1, 2)

        r_pts = _PropRow(grid, 1, "Points", parent=frame, read_only=True)
        counts = [len(e.points) for e in entities]
        is_u = len(set(counts)) == 1
        r_pts.set_value(str(counts[0]) if is_u else _VARIOUS, is_u)

        r_closed = _PropRow(grid, 2, "Closed", parent=frame, read_only=True)
        closed = [e.closed for e in entities]
        is_u = len(set(closed)) == 1
        r_closed.set_value(str(closed[0]) if is_u else _VARIOUS, is_u)

        self._content_layout.addWidget(frame)

    def _build_text_section(self, entities) -> None:
        from app.entities import Vec2

        def _apply_txt(e, s): e.text = s
        def _apply_x(e, s): e.position = Vec2(_parse_float(s, e.position.x), e.position.y)
        def _apply_y(e, s): e.position = Vec2(e.position.x, _parse_float(s, e.position.y))
        def _apply_h(e, s):
            v = _parse_float(s, e.height)
            if v > 0:
                e.height = v
        def _apply_rot(e, s): e.rotation = _parse_float(s, e.rotation)

        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Text", frame), 0, 0, 1, 2)

        specs_str = [
            ("Content", lambda e: e.text,     _apply_txt),
            ("X",       lambda e: e.position.x, _apply_x),
            ("Y",       lambda e: e.position.y, _apply_y),
            ("Height",  lambda e: e.height,   _apply_h),
            ("Rotation",lambda e: e.rotation, _apply_rot),
        ]
        for i, (key, getter, apply_fn) in enumerate(specs_str, start=1):
            r = _PropRow(grid, i, key, parent=frame, read_only=False)
            raw = [getter(e) for e in entities]
            is_u = len(set(raw)) == 1
            raw_val = raw[0]
            display = str(raw_val) if is_u else _VARIOUS
            if is_u and isinstance(raw_val, float):
                display = _fmt_float(raw_val)
            r.set_value(display, is_u)
            r.connect_changed(
                lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn))

        self._content_layout.addWidget(frame)

    def _build_dimension_section(self, entities) -> None:
        def _apply_ext_offset(e, s): e.ext_offset = max(0.0, _parse_float(s, e.ext_offset))
        def _apply_dim_offset(e, s): e.dim_offset = max(0.0, _parse_float(s, e.dim_offset))
        def _apply_arrow_size(e, s): e.arrow_size = max(0.0, _parse_float(s, e.arrow_size))
        def _apply_mark_type(e, s):
            if s in ("arrow", "mark", "none"):
                e.mark_type = s

        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Dimension", frame), 0, 0, 1, 2)

        r_type = _PropRow(grid, 1, "Type", parent=frame, read_only=True)
        types = [e.dim_type for e in entities]
        is_u = len(set(types)) == 1
        r_type.set_value(types[0] if is_u else _VARIOUS, is_u)

        r_mark = _PropRow(grid, 2, "Mark", widget_type="combo",
                          options=["arrow", "mark", "none"], parent=frame)
        marks = [e.mark_type for e in entities]
        is_u = len(set(marks)) == 1
        r_mark.set_value(marks[0] if is_u else _VARIOUS, is_u)
        r_mark.connect_changed(
            lambda row=r_mark, fn=_apply_mark_type: self._apply_geo(entities, row, fn))

        specs = [
            ("Arrow size",  lambda e: e.arrow_size,  _apply_arrow_size),
            ("Ext offset",  lambda e: e.ext_offset,  _apply_ext_offset),
            ("Dim offset",  lambda e: e.dim_offset,  _apply_dim_offset),
        ]
        for i, (key, getter, apply_fn) in enumerate(specs, start=3):
            r = _PropRow(grid, i, key, parent=frame)
            raw = [getter(e) for e in entities]
            is_u = len(set(raw)) == 1
            r.set_value(_fmt_float(raw[0]) if is_u else _VARIOUS, is_u)
            r.connect_changed(
                lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn))

        self._content_layout.addWidget(frame)

    def _build_hatch_section(self, entities) -> None:
        def _apply_scale(e, s):
            v = _parse_float(s, e.pattern_scale)
            if v > 0:
                e.pattern_scale = v
        def _apply_angle(e, s): e.pattern_angle = _parse_float(s, e.pattern_angle)

        frame = self._make_section_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(4, 2, 4, 4)
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.addWidget(_header("Hatch", frame), 0, 0, 1, 2)

        specs = [
            ("Pattern",   lambda e: e.pattern,       None),
            ("Scale",     lambda e: e.pattern_scale, _apply_scale),
            ("Angle",     lambda e: e.pattern_angle, _apply_angle),
        ]
        for i, (key, getter, apply_fn) in enumerate(specs, start=1):
            ro = apply_fn is None
            r = _PropRow(grid, i, key, parent=frame, read_only=ro)
            raw = [getter(e) for e in entities]
            is_u = len(set(raw)) == 1
            raw_val = raw[0]
            display = str(raw_val) if is_u else _VARIOUS
            if is_u and isinstance(raw_val, float):
                display = _fmt_float(raw_val)
            r.set_value(display, is_u)
            if apply_fn:
                r.connect_changed(
                    lambda row=r, fn=apply_fn: self._apply_geo(entities, row, fn))

        self._content_layout.addWidget(frame)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _parse_float(s: str, fallback: float) -> float:
    try:
        return float(s.strip().rstrip("°"))
    except (ValueError, AttributeError):
        return fallback
