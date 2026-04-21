"""
Quick (compact) colour popup for the ribbon swatch.

This is a lightweight alternative to the full tabbed :class:`ColorPickerDialog`:
- Common swatches (AutoCAD ACI 1–9 mapped to hex)
- "By Layer" (clear override)
- "More…" to open the full picker
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.colors.aci import aci_to_hex


@dataclass(frozen=True)
class _Swatch:
    label: str
    color: Optional[str]  # hex string or None (= by layer)


class QuickColorPopup(QFrame):
    """Small popup showing common colours and a 'More…' affordance.

    Signals
    -------
    colorPicked(str | None):
        Emits a hex colour string (``"#rrggbb"``) or ``None`` for "By Layer".
    moreRequested():
        Emits when the user clicks "More…" (caller should open full picker).
    """

    colorPicked = Signal(object)  # Optional[str]
    moreRequested = Signal()

    def __init__(self, initial: Optional[str], parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("QuickColorPopup")
        self._initial = (initial or "").lower() or None

        self.setStyleSheet(
            "QFrame#QuickColorPopup { background: #2d2d2d; border: 1px solid #3a3a3a; }"
            "QLabel { color: #cbd5e1; font-size: 9pt; }"
            "QPushButton { background: #3a3a3a; color: #e0e0e0; border: 1px solid #555;"
            "  border-radius: 3px; padding: 4px 10px; }"
            "QPushButton:hover { background: #4a4a4a; }"
            "QPushButton:pressed { background: #222; }"
            "QToolButton#QuickSwatch { border: 1px solid #444; border-radius: 3px;"
            "  padding: 0px; min-width: 18px; min-height: 18px; }"
            "QToolButton#QuickSwatch:hover { border: 1px solid #cbd5e1; }"
            "QToolButton#QuickSwatch[active='true'] { border: 2px solid #ffffff; }"
        )

        self._build()

    # ------------------------------------------------------------------

    def popup_below(self, anchor: QWidget) -> None:
        """Show the popup positioned under *anchor*, clamped to the screen."""
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(0, anchor.height()))
        screen = anchor.screen()
        if screen:
            sr = screen.availableGeometry()
            if pos.x() + self.width() > sr.right():
                pos.setX(sr.right() - self.width())
            if pos.y() + self.height() > sr.bottom():
                pos = anchor.mapToGlobal(QPoint(0, -self.height()))
        self.move(pos)
        self.show()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QLabel("Colour")
        title.setStyleSheet("font-weight: bold; color: #e5e7eb;")
        root.addWidget(title)

        # ACI 1–9 are the familiar "standard" colours. We map them to hex
        # so the rest of the app can stay on the existing hex-string path.
        swatches = [
            _Swatch("Red", aci_to_hex(1)),
            _Swatch("Yellow", aci_to_hex(2)),
            _Swatch("Green", aci_to_hex(3)),
            _Swatch("Cyan", aci_to_hex(4)),
            _Swatch("Blue", aci_to_hex(5)),
            _Swatch("Magenta", aci_to_hex(6)),
            _Swatch("White", aci_to_hex(7)),
            _Swatch("Dark Grey", aci_to_hex(8)),
            _Swatch("Light Grey", aci_to_hex(9)),
        ]

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        cols = 9
        for i, sw in enumerate(swatches):
            btn = self._make_swatch_btn(sw)
            grid.addWidget(btn, 0, i % cols)
        root.addLayout(grid)

        # Actions row: ByLayer on the left, More on the right.
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        bylayer = QPushButton("By Layer")
        bylayer.setToolTip("Remove colour override — use the layer colour instead")
        bylayer.clicked.connect(self._pick_bylayer)
        actions.addWidget(bylayer)

        actions.addStretch(1)

        more = QPushButton("More…")
        more.setToolTip("Open the full colour picker")
        more.clicked.connect(self._request_more)
        actions.addWidget(more)

        root.addLayout(actions)

    def _make_swatch_btn(self, sw: _Swatch) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("QuickSwatch")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(sw.label)
        if sw.color:
            btn.setStyleSheet(
                f"QToolButton#QuickSwatch {{ background: {sw.color}; }}"
            )
        if self._is_active(sw.color):
            btn.setProperty("active", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        btn.clicked.connect(lambda checked=False, c=sw.color: self._pick_color(c))
        return btn

    def _is_active(self, color: Optional[str]) -> bool:
        if color is None:
            return self._initial is None
        return (self._initial or "").lower() == color.lower()

    def _pick_color(self, color: Optional[str]) -> None:
        self.colorPicked.emit(color)
        self.close()

    def _pick_bylayer(self) -> None:
        self._pick_color(None)

    def _request_more(self) -> None:
        self.moreRequested.emit()
        self.close()

