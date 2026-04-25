"""
Command palette — a floating search widget that lets the user type to filter
and launch registered commands.

Triggered by pressing any alphanumeric key when idle (the key becomes the
first character of the query).  Dismissed by Escape.
"""
from __future__ import annotations

import re
from typing import Any, List, Optional

from PySide6.QtCore import Qt, Signal, QRectF, QTimer
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QKeyEvent, QMouseEvent, QPainter, QPen,
)
from PySide6.QtWidgets import QWidget


# ---------------------------------------------------------------------------
# Colours / geometry constants
# ---------------------------------------------------------------------------
_BG          = QColor("#1E1E1E")
_BORDER      = QColor("#3A3A3A")
_INPUT_BG    = QColor("#2A2A2A")
_INPUT_FG    = QColor("#FFFFFF")
_PLACEHOLDER = QColor("#666666")
_ITEM_FG     = QColor("#CCCCCC")
_ITEM_MATCH  = QColor("#4FC3F7")   # highlighted matched chars
_ITEM_SEL_BG = QColor("#0E4D70")
_SEPARATOR   = QColor("#333333")

_WIDTH       = 360
_INPUT_H     = 36
_ITEM_H      = 28
_MAX_VISIBLE = 8
_CORNER_R    = 8.0
_PAD_X       = 12
_CURSOR_W    = 2


def _command_display_name(key: str) -> str:
    """Convert 'lineCommand' / 'moveCommand' → 'Line' / 'Move'."""
    # Strip trailing 'Command' suffix (case-insensitive)
    label = re.sub(r'(?i)command$', '', key)
    # Split on camelCase / underscores
    parts = re.sub(r'([A-Z])', r' \1', label).replace('_', ' ').split()
    return ' '.join(p.capitalize() for p in parts) if parts else key


def _label_for_command_entry(key: str, entry: Any) -> str:
    """Resolve a user-visible label for a command registry entry."""
    display_name = getattr(entry, "display_name", None)
    if isinstance(display_name, str) and display_name.strip():
        return display_name
    return _command_display_name(key)


class CommandPaletteWidget(QWidget):
    """Custom-painted command palette overlay.

    Signals
    -------
    command_selected(str):
        Emitted when the user commits a command.  The value is the registry
        key (e.g. ``"lineCommand"``), not the display label.
    dismissed:
        Emitted when the palette closes without a selection.
    """

    command_selected = Signal(str)
    dismissed        = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.NoFocus)   # canvas forwards keys directly
        self.hide()

        self._query:    str          = ""
        self._all:      List[tuple]  = []   # [(key, label), ...]
        self._filtered: List[tuple]  = []
        self._sel:      int          = 0    # selected index in _filtered

        self._cursor_visible: bool = True
        self._blink = QTimer(self)
        self._blink.setInterval(530)
        self._blink.timeout.connect(self._toggle_cursor)

        self._font = QFont("Segoe UI", 10)
        self._font_bold = QFont("Segoe UI", 10, QFont.Bold)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(self, commands: dict[str, Any]) -> None:
        """Load command registry/spec dict keyed by command id."""
        self._all = sorted(
            [(_k, _label_for_command_entry(_k, _v)) for _k, _v in commands.items()],
            key=lambda t: t[1].lower(),
        )

    def open(self, seed: str = "") -> None:
        """Show the palette, reset state, and position over parent centre.

        Parameters
        ----------
        seed:
            Optional character(s) to pre-fill the query field with.
        """
        self._query    = seed
        self._sel      = 0
        self._cursor_visible = True
        self._apply_filter()
        self._blink.start()
        self._reposition()
        self.show()
        self.raise_()
        self.update()

    def close_palette(self, emit_dismissed: bool = True) -> None:
        self._blink.stop()
        self.hide()
        if emit_dismissed:
            self.dismissed.emit()

    # ------------------------------------------------------------------
    # Key handling (called directly from canvas.keyPressEvent)
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()

        if key == Qt.Key_Escape:
            self.close_palette()
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._commit()
            return

        if key == Qt.Key_Up:
            self._sel = max(0, self._sel - 1)
            self.update()
            return

        if key == Qt.Key_Down:
            self._sel = min(len(self._filtered) - 1, self._sel + 1)
            self.update()
            return

        if key == Qt.Key_Backspace:
            self._query = self._query[:-1]
        elif event.text() and event.text().isprintable():
            self._query += event.text()

        self._apply_filter()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            y = event.position().y() if hasattr(event, "position") else event.y()
            if y >= _INPUT_H:
                row = int((y - _INPUT_H) / _ITEM_H)
                if 0 <= row < len(self._filtered):
                    self._sel = row
                    self._commit()
                    return
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _commit(self) -> None:
        if self._filtered:
            key, _ = self._filtered[self._sel]
            self.close_palette(emit_dismissed=False)
            self.command_selected.emit(key)

    def _apply_filter(self) -> None:
        q = self._query.lower()
        if not q:
            self._filtered = list(self._all)
        else:
            self._filtered = [
                (k, lbl) for k, lbl in self._all
                if q in lbl.lower() or q in k.lower()
            ]
        self._sel = 0

    def _reposition(self) -> None:
        p = self.parentWidget()
        if p is None:
            return
        visible_rows = min(len(self._filtered), _MAX_VISIBLE)
        h = _INPUT_H + visible_rows * _ITEM_H + 8   # 8px bottom pad
        x = (p.width() - _WIDTH) // 2
        y = max(8, p.height() // 5)
        self.setGeometry(x, y, _WIDTH, h)

    def _toggle_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        visible_rows = min(len(self._filtered), _MAX_VISIBLE)
        h = _INPUT_H + visible_rows * _ITEM_H + 8

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background + border
        painter.setPen(QPen(_BORDER, 1.0))
        painter.setBrush(_BG)
        painter.drawRoundedRect(QRectF(0.5, 0.5, _WIDTH - 1, h - 1), _CORNER_R, _CORNER_R)

        # ---- Input area --------------------------------------------------
        painter.setPen(Qt.NoPen)
        painter.setBrush(_INPUT_BG)
        painter.drawRoundedRect(QRectF(6, 6, _WIDTH - 12, _INPUT_H - 6), 4, 4)

        painter.setFont(self._font)
        fm = QFontMetricsF(self._font)

        text_y = 6 + (_INPUT_H - 6) / 2 + fm.ascent() / 2 - fm.descent() / 2

        if self._query:
            painter.setPen(_INPUT_FG)
            painter.drawText(int(_PAD_X + 4), int(text_y), self._query)
            # cursor
            if self._cursor_visible:
                cx = _PAD_X + 4 + int(fm.horizontalAdvance(self._query))
                painter.setPen(QPen(_INPUT_FG, _CURSOR_W))
                painter.drawLine(cx, int(text_y - fm.ascent()), cx, int(text_y + fm.descent()))
        else:
            painter.setPen(_PLACEHOLDER)
            painter.drawText(int(_PAD_X + 4), int(text_y), "Type a command…")
            if self._cursor_visible:
                painter.setPen(QPen(_INPUT_FG, _CURSOR_W))
                painter.drawLine(_PAD_X + 4, int(text_y - fm.ascent()),
                                 _PAD_X + 4, int(text_y + fm.descent()))

        # ---- Separator ---------------------------------------------------
        if visible_rows:
            painter.setPen(QPen(_SEPARATOR, 1))
            painter.drawLine(_PAD_X, _INPUT_H, _WIDTH - _PAD_X, _INPUT_H)

        # ---- Result rows -------------------------------------------------
        q_lower = self._query.lower()
        for i in range(visible_rows):
            key, label = self._filtered[i]
            row_y = _INPUT_H + i * _ITEM_H

            # Selection highlight
            if i == self._sel:
                painter.setPen(Qt.NoPen)
                painter.setBrush(_ITEM_SEL_BG)
                is_last = (i == visible_rows - 1)
                if is_last:
                    painter.drawRoundedRect(
                        QRectF(1, row_y, _WIDTH - 2, _ITEM_H + 4), 0, 0)
                else:
                    painter.drawRect(int(1), row_y, _WIDTH - 2, _ITEM_H)

            item_text_y = row_y + _ITEM_H / 2 + fm.ascent() / 2 - fm.descent() / 2

            # Draw label with matched chars highlighted
            self._draw_highlighted(painter, fm, label, q_lower,
                                   _PAD_X + 4, int(item_text_y))

        painter.end()

    def _draw_highlighted(
        self,
        painter: QPainter,
        fm: QFontMetricsF,
        label: str,
        query: str,
        x: int,
        y: int,
    ) -> None:
        """Draw *label* with characters matching *query* in highlight colour."""
        if not query:
            painter.setFont(self._font)
            painter.setPen(_ITEM_FG)
            painter.drawText(x, y, label)
            return

        # Find the first occurrence of the query substring
        idx = label.lower().find(query)
        if idx == -1:
            painter.setFont(self._font)
            painter.setPen(_ITEM_FG)
            painter.drawText(x, y, label)
            return

        before = label[:idx]
        match  = label[idx: idx + len(query)]
        after  = label[idx + len(query):]

        painter.setFont(self._font)
        cx = x
        if before:
            painter.setPen(_ITEM_FG)
            painter.drawText(cx, y, before)
            cx += int(fm.horizontalAdvance(before))
        painter.setFont(self._font_bold)
        painter.setPen(_ITEM_MATCH)
        painter.drawText(cx, y, match)
        cx += int(QFontMetricsF(self._font_bold).horizontalAdvance(match))
        if after:
            painter.setFont(self._font)
            painter.setPen(_ITEM_FG)
            painter.drawText(cx, y, after)
