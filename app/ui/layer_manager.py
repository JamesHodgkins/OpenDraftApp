"""
Layer Manager Dialog.

A floating dialog that lets the user create, delete, rename and configure
drawing layers — including colour, visibility and active-layer selection.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QComboBox,
    QWidget, QStyledItemDelegate,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal

from app.document import DocumentStore, Layer
from app.colors.color import Color as _Color
from app.ui.color_picker import ColorPickerDialog


# ─── Custom delegate for the thin active-layer indicator bar ─────────
class _BarDelegate(QStyledItemDelegate):
    """Paints a vertical emerald accent bar for the active layer row."""

    _EMERALD = QColor("#0FB881")
    _INACTIVE = QColor("#252525")

    def paint(self, painter, option, index):
        r = option.rect
        painter.fillRect(r, self._INACTIVE)
        if index.data(Qt.UserRole + 1):
            painter.fillRect(r.x(), r.y(), 3, r.height(), self._EMERALD)


class LayerManagerDialog(QDialog):
    """Modal dialog for managing drawing layers.

    Signals
    -------
    layers_changed:
        Emitted whenever any layer property is modified (visibility, colour,
        rename, add, delete, active-layer change).  Connect this to the
        canvas's ``refresh`` slot so the viewport updates live.
    """

    layers_changed = Signal()

    # ── Column indices ────────────────────────────────────────────────
    COL_INDICATOR = 0
    COL_VISIBLE   = 1
    COL_COLOR     = 2
    COL_NAME      = 3
    COL_STYLE     = 4
    COL_WEIGHT    = 5
    HEADERS       = ["", "", "Color", "Name", "Line Style", "Weight"]

    # Recognised line-style names (must match canvas._LINE_STYLE_MAP keys)
    _LINE_STYLES = ["solid", "dashed", "dotted", "dashdot", "dashdotdot", "center", "phantom", "hidden"]
    # Common line weight choices (displayed as mm/px units; internal store is float)
    _LINE_WEIGHTS = ["0.25", "0.5", "0.75", "1.0", "1.25", "1.5", "2.0", "2.5", "3.0"]

    # ── Colours ───────────────────────────────────────────────────────
    _EMERALD  = "#0FB881"
    _BG       = "#2d2d2d"
    _BG_TABLE = "#252525"
    _BORDER   = "#3a3a3a"
    _TEXT     = "#e0e0e0"
    _TEXT_DIM = "#888"
    _BTN_BG   = "#353535"

    # ── Stylesheet ────────────────────────────────────────────────────
    _DIALOG_STYLE = f"""
        * {{
            outline: none;
        }}
        QDialog {{
            background: {_BG};
            color: {_TEXT};
        }}
        QTableWidget {{
            background: {_BG_TABLE};
            color: {_TEXT};
            gridline-color: transparent;
            border: 1px solid {_BORDER};
            border-radius: 6px;
            outline: none;
        }}
        QTableWidget:focus {{
            border: 1px solid {_BORDER};
        }}
        QTableWidget::item {{
            padding: 4px 6px;
            border: none;
            border-bottom: 1px solid #303030;
        }}
        QTableWidget::item:selected {{
            background: transparent;
            color: {_TEXT};
        }}
        QTableWidget::item:focus {{
            border: none;
            border-bottom: 1px solid #303030;
        }}
        QTableWidget::item:hover {{
            background: #2e2e2e;
        }}
        QHeaderView::section {{
            background: {_BG_TABLE};
            color: #777;
            padding: 6px 4px;
            border: none;
            border-bottom: 1px solid {_BORDER};
            font-size: 11px;
            font-weight: bold;
        }}
        QTableWidget QComboBox {{
            background: {_BTN_BG};
            color: {_TEXT};
            border: 1px solid #444;
            border-radius: 3px;
            padding: 2px 6px;
            min-height: 18px;
            outline: none;
        }}
        QTableWidget QComboBox:hover {{
            border-color: #777;
        }}
        QTableWidget QComboBox:focus {{
            border: 1px solid #444;
            outline: none;
        }}
        QTableWidget QComboBox:on {{
            border: 1px solid #444;
        }}
        QTableWidget QComboBox::drop-down {{
            border: none;
            width: 16px;
        }}
        QTableWidget QComboBox QAbstractItemView {{
            background: #333;
            color: {_TEXT};
            border: 1px solid #444;
            selection-background-color: {_EMERALD};
            outline: none;
        }}
        QTableWidget QComboBox QAbstractItemView::item:focus {{
            border: none;
            outline: none;
        }}
        QPushButton {{
            background: {_BTN_BG};
            color: {_TEXT};
            border: 1px solid #444;
            border-radius: 4px;
            padding: 5px 14px;
            font-weight: bold;
            outline: none;
        }}
        QPushButton:focus {{
            border: 1px solid #444;
        }}
        QPushButton:hover {{
            border-color: #777;
            background: #3e3e3e;
        }}
        QPushButton:pressed {{
            background: #333;
            border-color: #555;
        }}
    """

    _VIS_BUTTON_STYLE = f"""
        QPushButton {{
            background: {_BTN_BG};
            border: 1px solid #555;
            border-radius: 3px;
            color: {_EMERALD};
            font-size: 14px;
            font-weight: bold;
            min-width: 18px; max-width: 18px;
            min-height: 18px; max-height: 18px;
            padding: 0px;
        }}
        QPushButton:hover {{
            border-color: #777;
        }}
    """

    def __init__(self, document: DocumentStore, parent=None, editor=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Layer Manager")
        self.setMinimumSize(680, 360)
        self.setStyleSheet(self._DIALOG_STYLE)
        self._doc = document
        self._editor = editor
        self._build_ui()
        self._populate()

    # ──────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── layer table ──────────────────────────────────────────────
        self._table = QTableWidget(0, len(self.HEADERS))
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.NoFocus)

        # Indicator delegate for col 0
        self._table.setItemDelegateForColumn(
            self.COL_INDICATOR, _BarDelegate(self._table),
        )

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_INDICATOR, QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_INDICATOR, 16)
        hdr.setSectionResizeMode(self.COL_VISIBLE, QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_VISIBLE, 36)
        hdr.setSectionResizeMode(self.COL_COLOR, QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_COLOR, 40)
        hdr.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        hdr.setSectionResizeMode(self.COL_STYLE, QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_STYLE, 110)
        hdr.setSectionResizeMode(self.COL_WEIGHT, QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_WEIGHT, 80)
        self._table.verticalHeader().setVisible(False)

        self._table.itemChanged.connect(self._on_item_changed)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        root.addWidget(self._table)

        # ── hint label ───────────────────────────────────────────────
        hint = QPushButton()
        hint.setEnabled(False)
        hint.setText(
            "Click a row to set active layer  \u00b7  "
            "Double-click colour to change  \u00b7  "
            "Double-click name to rename"
        )
        hint.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: #888; font-size: 9pt; padding: 0; }"
        )
        root.addWidget(hint)

        # ── action buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_add    = QPushButton("Add Layer")
        self._btn_delete = QPushButton("Delete Layer")
        btn_close        = QPushButton("Close")

        self._btn_add.clicked.connect(self._add_layer)
        self._btn_delete.clicked.connect(self._delete_layer)
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_delete)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    # ──────────────────────────────────────────────────────────────────
    # Table population
    # ──────────────────────────────────────────────────────────────────

    def _populate(self) -> None:
        """Rebuild the table from the current document layer list."""
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for layer in self._doc.layers:
            self._append_row(layer)
        self._table.blockSignals(False)

    def _append_row(self, layer: Layer) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 32)
        is_active = layer.name == self._doc.active_layer

        # ── Indicator (painted by _BarDelegate) ──────────────────────
        ind_item = QTableWidgetItem()
        ind_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        ind_item.setData(Qt.UserRole, layer.name)
        ind_item.setData(Qt.UserRole + 1, is_active)
        self._table.setItem(row, self.COL_INDICATOR, ind_item)

        # ── Visibility (checkable button with emerald tick) ────────
        vis_btn = QPushButton("\u2713" if layer.visible else "")
        vis_btn.setCheckable(True)
        vis_btn.setChecked(layer.visible)
        vis_btn.setStyleSheet(self._VIS_BUTTON_STYLE)
        vis_btn.setProperty("layerName", layer.name)
        vis_btn.toggled.connect(
            lambda checked, b=vis_btn: b.setText("\u2713" if checked else "")
        )
        vis_btn.toggled.connect(self._on_visibility_toggled)

        vis_wrapper = QWidget()
        vis_wrapper.setStyleSheet("background: transparent;")
        vis_layout = QHBoxLayout(vis_wrapper)
        vis_layout.setContentsMargins(0, 0, 0, 0)
        vis_layout.setAlignment(Qt.AlignCenter)
        vis_layout.addWidget(vis_btn)
        self._table.setCellWidget(row, self.COL_VISIBLE, vis_wrapper)

        # Data item for visibility (needed for UserRole storage)
        vis_item = QTableWidgetItem()
        vis_item.setFlags(Qt.ItemIsEnabled)
        vis_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_VISIBLE, vis_item)

        # ── Color swatch (cell widget for reliable colour display)
        try:
            resolved = _Color.from_string(layer.color).to_hex()
        except Exception:
            resolved = layer.color
        swatch = QWidget()
        swatch.setStyleSheet(
            f"background: {resolved}; border-radius: 3px; margin: 4px 2px;"
        )
        self._table.setCellWidget(row, self.COL_COLOR, swatch)

        color_item = QTableWidgetItem()
        color_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        color_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_COLOR, color_item)

        # ── Name — editable (except for the "default" layer)
        name_item = QTableWidgetItem(layer.name)
        if layer.name == "default":
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        name_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_NAME, name_item)

        # ── Line style — dropdown
        style_combo = QComboBox()
        style_combo.addItems(self._LINE_STYLES)
        if layer.line_style in self._LINE_STYLES:
            style_combo.setCurrentText(layer.line_style)
        else:
            style_combo.setCurrentIndex(0)
        style_combo.setProperty("layerName", layer.name)
        def _on_style_change(text, _combo=style_combo):
            ln = _combo.property("layerName")
            if self._editor is not None:
                self._editor.set_layer_property(
                    ln, "line_style", text,
                    description=f"Layer '{ln}' line style",
                )
            else:
                l = self._doc.get_layer(ln)
                if l is None:
                    return
                l.line_style = text
            self.layers_changed.emit()
        style_combo.currentTextChanged.connect(_on_style_change)
        self._table.setCellWidget(row, self.COL_STYLE, style_combo)

        # ── Line weight — dropdown
        weight_combo = QComboBox()
        weight_combo.addItems(self._LINE_WEIGHTS)
        cur_w = str(layer.thickness)
        if cur_w in self._LINE_WEIGHTS:
            weight_combo.setCurrentText(cur_w)
        else:
            try:
                vals = [float(x) for x in self._LINE_WEIGHTS]
                idx = min(range(len(vals)), key=lambda i: abs(vals[i] - float(layer.thickness)))
                weight_combo.setCurrentIndex(idx)
            except Exception:
                weight_combo.setCurrentIndex(0)
        weight_combo.setProperty("layerName", layer.name)
        def _on_weight_change(text, _combo=weight_combo):
            ln = _combo.property("layerName")
            try:
                new_val = float(text)
            except (ValueError, TypeError):
                return
            if self._editor is not None:
                self._editor.set_layer_property(
                    ln, "thickness", new_val,
                    description=f"Layer '{ln}' weight",
                )
            else:
                l = self._doc.get_layer(ln)
                if l is None:
                    return
                l.thickness = new_val
            self.layers_changed.emit()
        weight_combo.currentTextChanged.connect(_on_weight_change)
        self._table.setCellWidget(row, self.COL_WEIGHT, weight_combo)

    # ──────────────────────────────────────────────────────────────────
    # Active-layer indicator
    # ──────────────────────────────────────────────────────────────────

    def _refresh_indicators(self) -> None:
        """Update all indicator bars to reflect the current active layer."""
        self._table.blockSignals(True)
        for r in range(self._table.rowCount()):
            item = self._table.item(r, self.COL_INDICATOR)
            if item is None:
                continue
            layer_name = item.data(Qt.UserRole)
            item.setData(Qt.UserRole + 1, layer_name == self._doc.active_layer)
        self._table.blockSignals(False)
        self._table.viewport().update()

    # ──────────────────────────────────────────────────────────────────
    # Event handlers
    # ──────────────────────────────────────────────────────────────────

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Clicking a row sets it as the active layer."""
        name_item = self._table.item(row, self.COL_NAME)
        if name_item is None:
            return
        layer_name = name_item.data(Qt.UserRole)
        if layer_name == self._doc.active_layer:
            return
        if self._editor is not None:
            self._editor.set_active_layer(layer_name)
        else:
            self._doc.active_layer = layer_name
        self._refresh_indicators()
        self.layers_changed.emit()

    def _on_visibility_toggled(self, checked: bool) -> None:
        """Handle visibility checkbox toggle."""
        cb = self.sender()
        if cb is None:
            return
        layer_name = cb.property("layerName")
        if self._editor is not None:
            self._editor.set_layer_property(
                layer_name, "visible", checked,
                description=f"Layer '{layer_name}' visibility",
            )
        else:
            layer = self._doc.get_layer(layer_name)
            if layer is None:
                return
            layer.visible = checked
        self.layers_changed.emit()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        col        = self._table.column(item)
        row        = self._table.row(item)
        layer_name = item.data(Qt.UserRole)
        layer      = self._doc.get_layer(layer_name)
        if layer is None:
            return

        if col == self.COL_NAME:
            new_name = item.text().strip()
            if not new_name or new_name == layer_name:
                return
            # Reject if the name is already taken
            if self._doc.get_layer(new_name):
                self._table.blockSignals(True)
                item.setText(layer_name)
                self._table.blockSignals(False)
                return
            # Apply the rename (undoable)
            if self._editor is not None:
                self._editor.rename_layer(layer_name, new_name)
            else:
                layer.name = new_name
                if self._doc.active_layer == layer_name:
                    self._doc.active_layer = new_name
            # Update the stored key in every cell of this row and any widgets
            self._table.blockSignals(True)
            for c in range(self._table.columnCount()):
                cell = self._table.item(row, c)
                if cell is not None:
                    cell.setData(Qt.UserRole, new_name)
                widget = self._table.cellWidget(row, c)
                if widget is not None:
                    widget.setProperty("layerName", new_name)
                    # Update the QPushButton inside the visibility wrapper
                    btn = widget.findChild(QPushButton)
                    if btn is not None:
                        btn.setProperty("layerName", new_name)
            self._table.blockSignals(False)
            self.layers_changed.emit()

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """Handle double-click on colour swatch."""
        if col != self.COL_COLOR:
            return
        item = self._table.item(row, col)
        if item is None:
            return
        layer_name = item.data(Qt.UserRole)
        layer = self._doc.get_layer(layer_name)
        if layer is None:
            return

        try:
            initial = _Color.from_string(layer.color)
        except Exception:
            initial = _Color(aci=7)
        dlg = ColorPickerDialog(
            initial=initial, parent=self,
            title=f"Choose colour \u2014 {layer_name}",
        )
        if dlg.exec() == QDialog.Accepted:
            chosen = dlg.chosen_color()
            if chosen is not None:
                color_str = chosen.to_string()
                if self._editor is not None:
                    self._editor.set_layer_property(
                        layer_name, "color", color_str,
                        description=f"Layer '{layer_name}' colour",
                    )
                else:
                    layer.color = color_str
                resolved = chosen.to_hex()
                swatch = self._table.cellWidget(row, self.COL_COLOR)
                if swatch is not None:
                    swatch.setStyleSheet(
                        f"background: {resolved}; border-radius: 3px; margin: 4px 2px;"
                    )
                self.layers_changed.emit()

    # ──────────────────────────────────────────────────────────────────
    # Toolbar actions
    # ──────────────────────────────────────────────────────────────────

    def _add_layer(self) -> None:
        """Add a new layer with a unique generated name."""
        base = "Layer"
        idx  = len(self._doc.layers)
        name = f"{base} {idx}"
        while self._doc.get_layer(name):
            idx += 1
            name = f"{base} {idx}"
        layer = Layer(name=name)
        if self._editor is not None:
            self._editor.add_layer(layer)
        else:
            self._doc.add_layer(layer)
        self._table.blockSignals(True)
        self._append_row(layer)
        self._table.blockSignals(False)
        self.layers_changed.emit()

    def _delete_layer(self) -> None:
        """Delete the selected layer, moving its entities to 'default'."""
        row = self._table.currentRow()
        if row < 0:
            return
        name_item  = self._table.item(row, self.COL_NAME)
        if name_item is None:
            return
        layer_name_any = name_item.data(Qt.UserRole)
        layer_name = (
            layer_name_any
            if isinstance(layer_name_any, str)
            else name_item.text()
        )

        if layer_name == "default":
            QMessageBox.warning(
                self, "Cannot Delete",
                "The 'default' layer cannot be deleted."
            )
            return

        result = QMessageBox.question(
            self, "Delete Layer",
            f"Delete layer '{layer_name}'?\n\n"
            "Entities on this layer will be moved to 'default'.",
        )
        if result != QMessageBox.Yes:
            return

        if self._editor is not None:
            self._editor.remove_layer_undoable(layer_name, reassign_to="default")
        else:
            # Reassign entities
            for e in list(self._doc.entities_on_layer(layer_name)):
                e.layer = "default"
            self._doc.remove_layer(layer_name)
            if self._doc.active_layer == layer_name:
                self._doc.active_layer = "default"

        self._table.removeRow(row)
        self._refresh_indicators()
        self.layers_changed.emit()
