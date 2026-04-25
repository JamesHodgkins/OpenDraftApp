"""
Tabbed Colour Picker Dialog.

Two tabs:
1. **Index Colour** (ACI) — the default tab shown on open.
2. **True Colour** — a standard Qt colour picker for arbitrary hex colours.

Returns a :class:`~app.colors.color.Color` via :meth:`chosen_color`.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QWidget, QColorDialog, QFrame,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from app.colors.color import Color
from app.colors.aci import aci_to_hex, hex_to_nearest_aci, ACI_COLORS
from app.ui.aci_picker import ACIPickerWidget


# ---------------------------------------------------------------------------
# True Colour tab — wraps QColorDialog as an embedded widget
# ---------------------------------------------------------------------------

class _TrueColorTab(QWidget):
    """Embedded true-colour picker (standard Qt colour wheel)."""

    def __init__(self, initial: QColor, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Use QColorDialog embedded directly as a child widget
        self._cd = QColorDialog(initial, self)
        self._cd.setWindowFlags(Qt.Widget)        # strip dialog frame
        self._cd.setOptions(
            QColorDialog.DontUseNativeDialog | QColorDialog.NoButtons
        )
        layout.addWidget(self._cd)

    def current_color(self) -> QColor:
        return self._cd.currentColor()

    def set_color(self, c: QColor) -> None:
        self._cd.setCurrentColor(c)


# ---------------------------------------------------------------------------
# Main tabbed dialog
# ---------------------------------------------------------------------------

class ColorPickerDialog(QDialog):
    """Modal colour picker with ACI (tab 0) and True Colour (tab 1) tabs.

    Usage::

        dlg = ColorPickerDialog(initial=Color(aci=3), parent=self)
        if dlg.exec() == QDialog.Accepted:
            chosen = dlg.chosen_color()  # Color instance
    """

    _STYLE = """
        QDialog {
            background: #2d2d2d;
            color: #e0e0e0;
        }
        QTabWidget::pane {
            border: 1px solid #3a3a3a;
            background: #2d2d2d;
        }
        QTabBar::tab {
            background: #353535;
            color: #bbb;
            padding: 6px 16px;
            border: 1px solid #3a3a3a;
            border-bottom: none;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #2d2d2d;
            color: #fff;
        }
        QTabBar::tab:hover:!selected {
            background: #404040;
        }
        QPushButton {
            background: #3a3a3a;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 6px 18px;
        }
        QPushButton:hover  { background: #4a4a4a; }
        QPushButton:pressed { background: #222; }
        QLabel { color: #ccc; }
    """

    def __init__(
        self,
        initial: Optional[Color] = None,
        parent: Optional[QWidget] = None,
        title: str = "Choose Colour",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(self._STYLE)
        self.setMinimumSize(520, 480)

        self._initial = initial or Color(aci=7)
        self._result: Optional[Color] = None

        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Tab widget ────────────────────────────────────────────
        self._tabs = QTabWidget()
        root.addWidget(self._tabs, stretch=1)

        # Tab 0: ACI picker
        initial_aci = self._initial.aci if self._initial.is_aci else None
        self._aci_picker = ACIPickerWidget(selected_index=initial_aci)
        self._tabs.addTab(self._aci_picker, "Index Colour (ACI)")

        # Tab 1: True colour
        initial_qcolor = QColor(self._initial.to_hex())
        self._true_color_tab = _TrueColorTab(initial_qcolor)
        self._tabs.addTab(self._true_color_tab, "True Colour")

        # Always default to the ACI tab
        self._tabs.setCurrentIndex(0)

        # ── Preview strip ─────────────────────────────────────────
        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)

        lbl = QLabel("Preview:")
        lbl.setStyleSheet("font-weight: bold;")
        preview_row.addWidget(lbl)

        self._preview_frame = QFrame()
        self._preview_frame.setFixedSize(120, 28)
        self._preview_frame.setFrameShape(QFrame.Box)
        self._preview_frame.setStyleSheet(
            f"background: {self._initial.to_hex()}; border: 1px solid #666;"
        )
        preview_row.addWidget(self._preview_frame)

        self._preview_label = QLabel(self._initial.display_name)
        self._preview_label.setStyleSheet("color: #aaa; font-size: 9pt;")
        preview_row.addWidget(self._preview_label)
        preview_row.addStretch()

        root.addLayout(preview_row)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_bylayer = QPushButton("By Layer")
        btn_bylayer.setToolTip("Remove colour override — use the layer colour instead")
        btn_bylayer.clicked.connect(self._accept_bylayer)
        btn_row.addWidget(btn_bylayer)
        btn_row.addStretch()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

        # ── Live preview connections ──────────────────────────────
        self._aci_picker.colorSelected.connect(self._on_aci_selected)
        self._true_color_tab._cd.currentColorChanged.connect(self._on_true_color_changed)

    # ------------------------------------------------------------------
    # Preview updates
    # ------------------------------------------------------------------

    def _on_aci_selected(self, idx: int) -> None:
        c = Color.from_aci(idx)
        self._update_preview(c)

    def _on_true_color_changed(self, qc: QColor) -> None:
        c = Color.from_hex(qc.name())
        self._update_preview(c)

    def _update_preview(self, color: Color) -> None:
        self._preview_frame.setStyleSheet(
            f"background: {color.to_hex()}; border: 1px solid #666;"
        )
        self._preview_label.setText(color.display_name)

    # ------------------------------------------------------------------
    # Accept / result
    # ------------------------------------------------------------------

    def _accept_bylayer(self) -> None:
        self._result = None  # sentinel: caller should clear the override
        self.accept()

    def _accept(self) -> None:
        tab = self._tabs.currentIndex()
        if tab == 0:
            idx = self._aci_picker.selected_aci()
            if idx is not None:
                self._result = Color.from_aci(idx)
            else:
                self._result = self._initial
        else:
            qc = self._true_color_tab.current_color()
            self._result = Color.from_hex(qc.name())
        self.accept()

    def chosen_color(self) -> Optional[Color]:
        """Return the user's chosen :class:`Color`, or ``None`` if cancelled."""
        return self._result
