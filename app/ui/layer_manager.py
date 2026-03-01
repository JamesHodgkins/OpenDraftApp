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
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal

from app.document import DocumentStore, Layer
from app.colors.color import Color as _Color
from app.ui.color_picker import ColorPickerDialog


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
    COL_ACTIVE  = 0
    COL_VISIBLE = 1
    COL_COLOR   = 2
    COL_NAME    = 3
    COL_STYLE   = 4
    COL_WEIGHT  = 5
    HEADERS     = ["Active", "Visible", "Color", "Name", "Line Style", "Weight"]

    # Recognised line-style names (must match canvas._LINE_STYLE_MAP keys)
    _LINE_STYLES = ["solid", "dashed", "dotted", "dashdot", "dashdotdot", "center", "phantom", "hidden"]
    # Common line weight choices (displayed as mm/px units; internal store is float)
    _LINE_WEIGHTS = ["0.25", "0.5", "0.75", "1.0", "1.25", "1.5", "2.0", "2.5", "3.0"]

    # ── Stylesheet ────────────────────────────────────────────────────
    _DIALOG_STYLE = """
        QDialog {
            background: #2d2d2d;
            color: #e0e0e0;
        }
        QTableWidget {
            background: #252525;
            color: #e0e0e0;
            gridline-color: #3a3a3a;
            border: 1px solid #3a3a3a;
            selection-background-color: #3a6ea5;
        }
        QHeaderView::section {
            background: #2d2d2d;
            color: #bbb;
            padding: 4px;
            border: none;
            border-bottom: 1px solid #3a3a3a;
            font-weight: bold;
        }
        QPushButton {
            background: #3a3a3a;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 4px 10px;
        }
        QPushButton:hover  { background: #4a4a4a; }
        QPushButton:pressed { background: #222; }
    """

    def __init__(self, document: DocumentStore, parent=None, editor=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Layer Manager")
        self.setMinimumSize(680, 320)
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
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── layer table ──────────────────────────────────────────────
        self._table = QTableWidget(0, len(self.HEADERS))
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_ACTIVE,  QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_VISIBLE, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_COLOR,   QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_COLOR, 50)
        hdr.setSectionResizeMode(self.COL_NAME,    QHeaderView.Stretch)
        hdr.setSectionResizeMode(self.COL_STYLE,   QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_STYLE, 100)
        hdr.setSectionResizeMode(self.COL_WEIGHT,  QHeaderView.Fixed)
        self._table.setColumnWidth(self.COL_WEIGHT, 80)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        root.addWidget(self._table)

        # ── hint label ───────────────────────────────────────────────
        hint_label = QPushButton()
        hint_label.setEnabled(False)
        hint_label.setText(
            "Double-click a colour swatch to change colour.  "
            "Double-click Line Style to change it.  "
            "Click Weight to edit thickness.  "
            "Double-click a name to rename."
        )
        hint_label.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: #888; font-size: 9pt; padding: 0; }"
        )
        root.addWidget(hint_label)

        # ── action buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

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

        # Active (checkable; only one row should be checked at a time)
        active_item = QTableWidgetItem()
        active_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        active_item.setCheckState(
            Qt.Checked if layer.name == self._doc.active_layer else Qt.Unchecked
        )
        active_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_ACTIVE, active_item)

        # Visible
        vis_item = QTableWidgetItem()
        vis_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        vis_item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)
        vis_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_VISIBLE, vis_item)

        # Color swatch — read-only; double-click opens colour picker
        color_item = QTableWidgetItem()
        color_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        try:
            resolved = _Color.from_string(layer.color).to_hex()
        except Exception:
            resolved = layer.color
        color_item.setBackground(QColor(resolved))
        color_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_COLOR, color_item)

        # Name — editable (except for the "default" layer)
        name_item = QTableWidgetItem(layer.name)
        if layer.name == "default":
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        name_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_NAME, name_item)

        # Line style — dropdown
        style_combo = QComboBox()
        style_combo.addItems(self._LINE_STYLES)
        if layer.line_style in self._LINE_STYLES:
            style_combo.setCurrentText(layer.line_style)
        else:
            style_combo.setCurrentIndex(0)
        style_combo.setProperty("layerName", layer.name)
        def _on_style_change(text):
            ln = style_combo.property("layerName")
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

        # Line weight — dropdown
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
        def _on_weight_change(text):
            ln = weight_combo.property("layerName")
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
    # Event handlers
    # ──────────────────────────────────────────────────────────────────

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        col        = self._table.column(item)
        row        = self._table.row(item)
        layer_name = item.data(Qt.UserRole)
        layer      = self._doc.get_layer(layer_name)
        if layer is None:
            return

        if col == self.COL_ACTIVE:
            if item.checkState() == Qt.Checked:
                if self._editor is not None:
                    self._editor.set_active_layer(layer_name)
                else:
                    self._doc.active_layer = layer_name
                # Uncheck all other rows
                self._table.blockSignals(True)
                for r in range(self._table.rowCount()):
                    if r != row:
                        self._table.item(r, self.COL_ACTIVE).setCheckState(Qt.Unchecked)
                self._table.blockSignals(False)
                self.layers_changed.emit()
            else:
                # Don't allow deactivating the only checked row without
                # another one being selected — silently re-check it.
                self._table.blockSignals(True)
                item.setCheckState(Qt.Checked)
                self._table.blockSignals(False)

        elif col == self.COL_VISIBLE:
            new_vis = item.checkState() == Qt.Checked
            if self._editor is not None:
                self._editor.set_layer_property(
                    layer_name, "visible", new_vis,
                    description=f"Layer '{layer_name}' visibility",
                )
            else:
                layer.visible = new_vis
            self.layers_changed.emit()

        elif col == self.COL_NAME:
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
            self._table.blockSignals(False)
            self.layers_changed.emit()
        # Weight is edited via the dropdown widget; no QTableWidgetItem handling

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """Handle double-click on colour swatch or line-style cells."""
        item = self._table.item(row, col)
        if item is None:
            return
        layer_name = item.data(Qt.UserRole)
        layer = self._doc.get_layer(layer_name)
        if layer is None:
            return

        if col == self.COL_COLOR:
            try:
                initial = _Color.from_string(layer.color)
            except Exception:
                initial = _Color(aci=7)
            dlg = ColorPickerDialog(
                initial=initial, parent=self,
                title=f"Choose colour — {layer_name}",
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
                    self._table.blockSignals(True)
                    item.setBackground(QColor(resolved))
                    self._table.blockSignals(False)
                    self.layers_changed.emit()

        # Line style is edited in-table via a QComboBox; nothing to do here

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
        layer_name = name_item.data(Qt.UserRole)

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
            was_active = self._doc.active_layer == layer_name
            self._editor.remove_layer_undoable(layer_name, reassign_to="default")
            if was_active:
                # Fix the Active checkboxes in the table
                self._table.blockSignals(True)
                for r in range(self._table.rowCount()):
                    lname = self._table.item(r, self.COL_ACTIVE).data(Qt.UserRole)
                    state = Qt.Checked if lname == "default" else Qt.Unchecked
                    self._table.item(r, self.COL_ACTIVE).setCheckState(state)
                self._table.blockSignals(False)
        else:
            # Reassign entities
            for e in list(self._doc.entities_on_layer(layer_name)):
                e.layer = "default"

            self._doc.remove_layer(layer_name)
            if self._doc.active_layer == layer_name:
                self._doc.active_layer = "default"
                # Fix the Active checkboxes in the table
                self._table.blockSignals(True)
                for r in range(self._table.rowCount()):
                    lname = self._table.item(r, self.COL_ACTIVE).data(Qt.UserRole)
                    state = Qt.Checked if lname == "default" else Qt.Unchecked
                    self._table.item(r, self.COL_ACTIVE).setCheckState(state)
                self._table.blockSignals(False)

        self._table.removeRow(row)
        self.layers_changed.emit()
