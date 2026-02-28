"""
Status bar widget — the bottom toolbar of the OpenDraft application.

Provides three visual sections from left to right:

1. **Editor message** — mirrors ``editor.status_message`` (command prompts /
   error text).
2. **OSNAP toggles** — MAS (master on/off), END, MID, CEN, PER, NEA.
   Left-click toggles the individual snap type; right-click on any
   individual button opens a future settings flyout.
3. **Tool toggles** — ORTHO, DM (Draftmate).  Left-click toggles,
   right-click on DM opens the Draftmate settings dialog.
4. **Coordinates** — ``X: … Y: …`` display (rightmost).

Each toggle button is a tiny ``QLabel`` subclass with click handling,
styled via objectName so the QSS theme can override colours.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from app.entities.snap_types import SnapType


# ---------------------------------------------------------------------------
# Tiny toggle "button" (really a styled QLabel)
# ---------------------------------------------------------------------------

class _ToggleLabel(QLabel):
    """A clickable label that toggles between *on* and *off* states.

    Signals
    -------
    toggled(bool)
        Emitted after every left-click with the **new** state.
    right_clicked()
        Emitted on a right-click (for opening settings / flyouts).
    """

    toggled = Signal(bool)
    right_clicked = Signal()

    def __init__(
        self,
        text: str,
        *,
        on: bool = True,
        tooltip: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self._on = on
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self._apply_style()

    # -- state ---------------------------------------------------------------

    @property
    def on(self) -> bool:
        return self._on

    @on.setter
    def on(self, value: bool) -> None:
        if value != self._on:
            self._on = value
            self._apply_style()

    # -- visual --------------------------------------------------------------

    _ON_SS = (
        "QLabel { padding: 1px 5px; color: #22c55e; font-weight: bold;"
        " font-size: 11px; font-family: 'Segoe UI', sans-serif; }"
    )
    _OFF_SS = (
        "QLabel { padding: 1px 5px; color: #9ca3af; font-size: 11px;"
        " font-family: 'Segoe UI', sans-serif; }"
    )

    def _apply_style(self) -> None:
        self.setStyleSheet(self._ON_SS if self._on else self._OFF_SS)

    # -- events --------------------------------------------------------------

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._on = not self._on
            self._apply_style()
            self.toggled.emit(self._on)
        elif ev.button() == Qt.RightButton:
            self.right_clicked.emit()


# ---------------------------------------------------------------------------
# Thin vertical separator
# ---------------------------------------------------------------------------

def _vsep(parent: Optional[QWidget] = None) -> QFrame:
    f = QFrame(parent)
    f.setFrameShape(QFrame.VLine)
    f.setFrameShadow(QFrame.Plain)
    f.setFixedWidth(1)
    f.setStyleSheet("QFrame { color: #d1d5db; }")
    return f


# ---------------------------------------------------------------------------
# StatusBarWidget
# ---------------------------------------------------------------------------

class StatusBarWidget(QWidget):
    """Composite widget placed inside ``QMainWindow.statusBar()``.

    The widget is *not* a ``QStatusBar`` — it is a plain ``QWidget`` that
    lives as the sole permanent child of the real status bar, giving us full
    control over layout without fighting Qt's built-in message area.
    """

    # Convenience signal re-emitted when DM right-click occurs.
    draftmate_settings_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        root = QHBoxLayout(self)
        root.setContentsMargins(4, 0, 4, 0)
        root.setSpacing(0)

        # ---- 1. Editor message label (stretches) --------------------------
        self.cmd_label = QLabel("")
        self.cmd_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.cmd_label.setStyleSheet(
            "QLabel { padding: 0 4px; font-size: 11px;"
            " font-family: 'Segoe UI', sans-serif; color: #4b5563; }"
        )
        root.addWidget(self.cmd_label)

        # ---- 2. OSNAP section ---------------------------------------------
        root.addWidget(_vsep())
        self._snap_section_label = QLabel("SNAP")
        self._snap_section_label.setStyleSheet(
            "QLabel { padding: 0 4px; font-size: 10px; color: #6b7280;"
            " font-family: 'Segoe UI', sans-serif; }"
        )
        root.addWidget(self._snap_section_label)

        # Master snap toggle
        self.btn_mas = _ToggleLabel("MAS", on=True, tooltip="Master OSNAP on/off")
        root.addWidget(self.btn_mas)

        # Individual snap-type toggles
        self._snap_btns: Dict[SnapType, _ToggleLabel] = {}
        snap_defs = [
            (SnapType.ENDPOINT,      "END", "Endpoint snap"),
            (SnapType.MIDPOINT,      "MID", "Midpoint snap"),
            (SnapType.CENTER,        "CEN", "Center snap"),
            (SnapType.PERPENDICULAR, "PER", "Perpendicular snap"),
            (SnapType.NEAREST,       "NEA", "Nearest snap"),
        ]
        for st, label, tip in snap_defs:
            btn = _ToggleLabel(label, on=True, tooltip=tip)
            self._snap_btns[st] = btn
            root.addWidget(btn)

        # ---- 3. Tools section ---------------------------------------------
        root.addWidget(_vsep())
        self._tools_label = QLabel("TOOLS")
        self._tools_label.setStyleSheet(
            "QLabel { padding: 0 4px; font-size: 10px; color: #6b7280;"
            " font-family: 'Segoe UI', sans-serif; }"
        )
        root.addWidget(self._tools_label)

        self.btn_ortho = _ToggleLabel("ORTHO", on=False, tooltip="Ortho mode (F8)")
        root.addWidget(self.btn_ortho)

        self.btn_dm = _ToggleLabel("DM", on=False, tooltip="Draftmate — F10 toggle, right-click for settings")
        self.btn_dm.right_clicked.connect(self.draftmate_settings_requested.emit)
        root.addWidget(self.btn_dm)

        # ---- 4. Coordinates (right-most) ----------------------------------
        root.addWidget(_vsep())
        self.coord_label = QLabel("X: 0.00  Y: 0.00")
        self.coord_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.coord_label.setStyleSheet(
            "QLabel { padding: 0 4px; font-size: 11px;"
            " font-family: 'Consolas', monospace; color: #4b5563; }"
        )
        self.coord_label.setMinimumWidth(160)
        root.addWidget(self.coord_label)

    # -- convenience helpers -------------------------------------------------

    def snap_button(self, st: SnapType) -> Optional[_ToggleLabel]:
        """Return the toggle label for a specific snap type, or ``None``."""
        return self._snap_btns.get(st)

    def set_snap_state(self, st: SnapType, on: bool) -> None:
        btn = self._snap_btns.get(st)
        if btn is not None:
            btn.on = on

    def set_master_snap(self, on: bool) -> None:
        self.btn_mas.on = on

    def set_draftmate(self, on: bool) -> None:
        self.btn_dm.on = on

    def set_ortho(self, on: bool) -> None:
        self.btn_ortho.on = on

    def update_coords(self, x: float, y: float) -> None:
        self.coord_label.setText(f"X: {x:.2f}  Y: {y:.2f}")
