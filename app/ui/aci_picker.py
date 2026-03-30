"""
ACI Colour Picker widget — a grid of clickable ACI colour swatches.

Laid out to resemble the standard AutoCAD indexed-colour dialog:
* Row of standard colours (1–9) across the top.
* Main 24×10 hue/shade grid (indices 10–249).
* Greyscale strip (250–255) along the bottom.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSizePolicy, QToolTip,
)
from PySide6.QtGui import QColor, QPainter, QMouseEvent, QPen, QBrush, QFontMetrics
from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint

from app.colors.aci import ACI_COLORS, aci_to_hex


# ---------------------------------------------------------------------------
# Individual colour cell
# ---------------------------------------------------------------------------

class _ACICell(QWidget):
    """A single clickable ACI colour swatch."""

    clicked = Signal(int)  # emits the ACI index

    def __init__(self, aci_index: int, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._index = aci_index
        r, g, b = ACI_COLORS[aci_index]
        self._color = QColor(r, g, b)
        self._hover = False
        self._selected = False
        self.setFixedSize(QSize(18, 18))
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"ACI {aci_index}  ({r}, {g}, {b})")

    @property
    def aci_index(self) -> int:
        return self._index

    def set_selected(self, val: bool) -> None:
        self._selected = val
        self.update()

    # -- events --

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._index)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        r = self.rect().adjusted(0, 0, -1, -1)

        # Fill
        p.fillRect(r, self._color)

        # Outline
        if self._selected:
            p.setPen(QPen(QColor(255, 255, 255), 2))
            p.drawRect(r.adjusted(1, 1, -1, -1))
        elif self._hover:
            p.setPen(QPen(QColor(200, 200, 200), 1))
            p.drawRect(r)
        else:
            p.setPen(QPen(QColor(60, 60, 60), 1))
            p.drawRect(r)

        p.end()


# ---------------------------------------------------------------------------
# ACI Picker composite widget
# ---------------------------------------------------------------------------

class ACIPickerWidget(QWidget):
    """Full ACI palette grid widget.

    Signals
    -------
    colorSelected(int):
        Emitted when the user clicks a swatch; carries the ACI index.
    """

    colorSelected = Signal(int)

    def __init__(self, selected_index: Optional[int] = None, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._selected_index = selected_index
        self._cells: dict[int, _ACICell] = {}
        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Standard colours (1–9) ────────────────────────────────
        std_label = QLabel("Standard Colours")
        std_label.setStyleSheet("color: #bbb; font-weight: bold; font-size: 9pt;")
        layout.addWidget(std_label)

        std_row = QHBoxLayout()
        std_row.setSpacing(2)
        for idx in range(1, 10):
            cell = self._make_cell(idx)
            cell.setFixedSize(QSize(28, 28))
            std_row.addWidget(cell)
        std_row.addStretch()
        layout.addLayout(std_row)

        # ── Separator ─────────────────────────────────────────────
        layout.addSpacing(4)

        # ── Main palette (10–249): 24 columns × 10 rows ──────────
        palette_label = QLabel("Full Palette")
        palette_label.setStyleSheet("color: #bbb; font-weight: bold; font-size: 9pt;")
        layout.addWidget(palette_label)

        grid = QGridLayout()
        grid.setSpacing(1)
        grid.setContentsMargins(0, 0, 0, 0)
        # The palette is arranged as 24 hue columns × 10 shade rows.
        # Each hue group has 10 shades (indices N+0 … N+9).
        # Hue groups start at 10, 20, 30, … 240.
        for hue_col in range(24):
            base = 10 + hue_col * 10
            for shade_row in range(10):
                idx = base + shade_row
                cell = self._make_cell(idx)
                grid.addWidget(cell, shade_row, hue_col)
        # Absorb extra horizontal space so cell spacing stays uniform
        grid.setColumnStretch(24, 1)
        layout.addLayout(grid)

        # ── Greyscale ramp (250–255) ──────────────────────────────
        layout.addSpacing(4)
        grey_label = QLabel("Greyscale")
        grey_label.setStyleSheet("color: #bbb; font-weight: bold; font-size: 9pt;")
        layout.addWidget(grey_label)

        grey_row = QHBoxLayout()
        grey_row.setSpacing(2)
        for idx in range(250, 256):
            cell = self._make_cell(idx)
            cell.setFixedSize(QSize(28, 28))
            grey_row.addWidget(cell)
        grey_row.addStretch()
        layout.addLayout(grey_row)

        # ── Preview / info ────────────────────────────────────────
        layout.addSpacing(4)
        self._info_label = QLabel()
        self._info_label.setStyleSheet("color: #aaa; font-size: 9pt;")
        self._update_info()
        layout.addWidget(self._info_label)

    def _make_cell(self, idx: int) -> _ACICell:
        cell = _ACICell(idx, self)
        cell.set_selected(idx == self._selected_index)
        cell.clicked.connect(self._on_cell_clicked)
        self._cells[idx] = cell
        return cell

    def _on_cell_clicked(self, idx: int) -> None:
        # Deselect old
        if self._selected_index is not None and self._selected_index in self._cells:
            self._cells[self._selected_index].set_selected(False)
        # Select new
        self._selected_index = idx
        if idx in self._cells:
            self._cells[idx].set_selected(True)
        self._update_info()
        self.colorSelected.emit(idx)

    def _update_info(self) -> None:
        if self._selected_index is not None and self._selected_index in ACI_COLORS:
            r, g, b = ACI_COLORS[self._selected_index]
            hex_str = aci_to_hex(self._selected_index)
            self._info_label.setText(
                f"ACI {self._selected_index}    RGB({r}, {g}, {b})    {hex_str}"
            )
        else:
            self._info_label.setText("No colour selected")

    def selected_aci(self) -> Optional[int]:
        return self._selected_index

    def set_selected(self, idx: Optional[int]) -> None:
        if self._selected_index is not None and self._selected_index in self._cells:
            self._cells[self._selected_index].set_selected(False)
        self._selected_index = idx
        if idx is not None and idx in self._cells:
            self._cells[idx].set_selected(True)
        self._update_info()
