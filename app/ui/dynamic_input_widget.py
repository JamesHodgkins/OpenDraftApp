"""
Dynamic input — custom-painted dynamic input widget that follows the cursor.

Replaces native QLineEdit controls with fully custom-drawn input fields.
Each field has an "active" state; key presses are routed to the active field
without any text selection behaviour.  When a field has no user input it
displays the current cursor world position (cartesian or polar).

Supports the same input format tokens as the old dynamic input:
  - ``#``  prefix  → absolute coordinates
  - ``<``  token   → polar  (distance < angle)
  - plain digits   → relative  (dX, dY)

Tab / Shift-Tab cycles focus between the two fields in point mode.
"""
from __future__ import annotations

from enum import Enum
from math import atan2, degrees, sqrt
from typing import Optional

from PySide6.QtCore import (
    QPoint,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QWidget

from app.editor.dynamic_input_parser import DynamicInputParser
from app.entities import Vec2


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class InputFormat(Enum):
    RELATIVE = "relative"
    ABSOLUTE = "absolute"
    POLAR = "polar"


# Colours
_TEXT_COLOR = QColor("#FFFFFF")
_PLACEHOLDER_COLOR = QColor("#777777")
_LABEL_COLOR = QColor("#999999")
_CURSOR_COLOR = QColor("#FFFFFF")
_UNDERLINE_COLOR = QColor("#555555")
_UNDERLINE_ACTIVE_COLOR = QColor("#0E9CD8")

# Geometry
_FIELD_W = 64
_FIELD_H = 20
_LABEL_GAP = 6        # gap between label and value text
_GROUP_GAP = 14        # gap between the two field groups
_PAD_X = 4            # horizontal padding inside widget
_PAD_Y = 2            # vertical padding inside widget
_UNDERLINE_W = 1.0    # underline thickness
_UNDERLINE_ACTIVE_W = 1.5  # active underline thickness

# Cursor blink
_CURSOR_BLINK_MS = 530


# ---------------------------------------------------------------------------
# Internal data for a single "field"
# ---------------------------------------------------------------------------
class _Field:
    """Lightweight data holder for one input field."""

    __slots__ = ("label", "text", "placeholder", "active", "user_edited", "rect")

    def __init__(self, label: str = "") -> None:
        self.label: str = label
        self.text: str = ""              # user-typed content
        self.placeholder: str = ""       # world-pos default when empty
        self.active: bool = False
        self.user_edited: bool = False   # True once the user types anything
        self.rect: QRectF = QRectF()     # painted bounds (set during paint)


# ---------------------------------------------------------------------------
# DynamicInputWidget
# ---------------------------------------------------------------------------
class DynamicInputWidget(QWidget):
    """Custom-painted dynamic input widget displayed near the cursor.

    The widget owns zero native child widgets; everything is drawn via
    QPainter and keyboard input is routed explicitly to the active field.
    """

    # Emitted when input is submitted (user presses Enter)
    input_submitted = Signal(object)  # Vec2, int, float or str
    # Emitted when input is cancelled (user presses Escape)
    input_cancelled = Signal()

    CURSOR_OFFSET_X = 20
    CURSOR_OFFSET_Y = 20

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # No window flags — as a child widget we already have no frame.
        # Keeping it a true child ensures focus and event routing work
        # properly through the parent canvas.
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # Focus stays on the canvas; it forwards key events to us directly.
        self.setFocusPolicy(Qt.NoFocus)

        # ---- Fonts -----------------------------------------------------------
        self._font = QFont("Consolas", 10)
        self._font.setStyleHint(QFont.Monospace)
        self._label_font = QFont("Segoe UI", 8)
        self._fm = QFontMetricsF(self._font)
        self._label_fm = QFontMetricsF(self._label_font)

        # ---- State -----------------------------------------------------------
        self._input_mode: str = "none"   # "none" | "point" | "integer" | "float" | "string"
        self._input_format = InputFormat.RELATIVE
        self._current_pos = Vec2(0, 0)   # world cursor position
        self._base_point: Optional[Vec2] = None

        # Two fields (second hidden in scalar modes)
        self._field_1 = _Field("dX")
        self._field_2 = _Field("dY")
        self._field_1.active = True      # field 1 starts active

        # Cursor blink timer
        self._cursor_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_cursor)
        self._blink_timer.setInterval(_CURSOR_BLINK_MS)

    # ------------------------------------------------------------------
    # Public API — mirrors the old DynamicInputWidget interface
    # ------------------------------------------------------------------

    def set_input_mode(
        self,
        mode: str,
        current_pos: Vec2,
        base_point: Optional[Vec2] = None,
    ) -> None:
        """Activate the widget for *mode* ("point", "integer", "float", "string")."""
        self._input_mode = mode
        self._current_pos = current_pos
        self._base_point = base_point if base_point is not None else Vec2(0, 0)

        # Reset fields
        self._input_format = InputFormat.RELATIVE
        for f in (self._field_1, self._field_2):
            f.text = ""
            f.user_edited = False
        self._field_1.active = True
        self._field_2.active = False

        if mode == "point":
            self._apply_labels()
        elif mode in ("integer", "float"):
            self._field_1.label = "Val"
        elif mode == "string":
            self._field_1.label = "Text"
        else:
            self.hide()
            return

        self._update_placeholders()
        self._resize_to_content()
        self.show()
        self.raise_()
        self._blink_timer.start()
        self._cursor_visible = True
        self.update()

    def update_cursor_position(self, pos: Vec2) -> None:
        """Called when the mouse moves — refreshes placeholder values."""
        if self._input_mode == "none" or not self.isVisible():
            return
        self._current_pos = pos
        self._update_placeholders()
        self.update()

    def update_screen_position(self, screen_pos: QPoint) -> None:
        """Reposition the widget near the cursor."""
        self.move(
            screen_pos.x() + self.CURSOR_OFFSET_X,
            screen_pos.y() + self.CURSOR_OFFSET_Y,
        )

    def clear(self) -> None:
        """Reset and hide."""
        self._field_1.text = ""
        self._field_2.text = ""
        self._field_1.user_edited = False
        self._field_2.user_edited = False
        self._input_mode = "none"
        self._blink_timer.stop()
        self.hide()

    # ------------------------------------------------------------------
    # Size
    # ------------------------------------------------------------------

    def _field_group_width(self, field: _Field) -> float:
        """Width of one label+value group, measured dynamically."""
        label_w = self._label_fm.horizontalAdvance(field.label) + _LABEL_GAP
        return label_w + _FIELD_W

    def _resize_to_content(self) -> None:
        """Set widget size based on current mode."""
        if self._input_mode == "point":
            w = _PAD_X * 2 + self._field_group_width(self._field_1) + _GROUP_GAP + self._field_group_width(self._field_2)
        else:
            w = _PAD_X * 2 + self._field_group_width(self._field_1)
        h = _PAD_Y * 2 + _FIELD_H
        self.setFixedSize(int(w), int(h))

    def sizeHint(self) -> QSize:  # noqa: N802
        if self._input_mode == "point":
            w = _PAD_X * 2 + self._field_group_width(self._field_1) + _GROUP_GAP + self._field_group_width(self._field_2)
        else:
            w = _PAD_X * 2 + self._field_group_width(self._field_1)
        h = _PAD_Y * 2 + _FIELD_H
        return QSize(int(w), int(h))

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # No background — fully transparent, text floats over the canvas.

        # --- fields ---
        x = _PAD_X
        y = _PAD_Y
        self._paint_field(p, self._field_1, x, y)

        if self._input_mode == "point":
            x += self._field_group_width(self._field_1) + _GROUP_GAP
            self._paint_field(p, self._field_2, x, y)

        p.end()

    def _paint_field(self, p: QPainter, field: _Field, x: float, y: float) -> None:
        """Draw one label + underlined value at (x, y)."""
        # --- inline label ---
        p.setFont(self._label_font)
        p.setPen(QPen(_LABEL_COLOR))
        label_w = self._label_fm.horizontalAdvance(field.label)
        label_rect = QRectF(x, y, label_w, _FIELD_H)
        p.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, field.label)

        # --- value area (no box, just text + underline) ---
        vx = x + label_w + _LABEL_GAP
        field_rect = QRectF(vx, y, _FIELD_W, _FIELD_H)
        field.rect = field_rect

        # --- text or placeholder ---
        p.setFont(self._font)
        if field.text:
            p.setPen(QPen(_TEXT_COLOR))
            p.drawText(field_rect, Qt.AlignVCenter | Qt.AlignLeft, field.text)
        else:
            p.setPen(QPen(_PLACEHOLDER_COLOR))
            p.drawText(field_rect, Qt.AlignVCenter | Qt.AlignLeft, field.placeholder)

        # --- underline ---
        underline_y = y + _FIELD_H - 1
        if field.active:
            p.setPen(QPen(_UNDERLINE_ACTIVE_COLOR, _UNDERLINE_ACTIVE_W))
        else:
            p.setPen(QPen(_UNDERLINE_COLOR, _UNDERLINE_W))
        p.drawLine(int(vx), int(underline_y), int(vx + _FIELD_W), int(underline_y))

        # --- cursor ---
        if field.active and self._cursor_visible:
            p.setFont(self._font)
            tw = self._fm.horizontalAdvance(field.text) if field.text else 0
            cx = vx + tw + 1
            cy_top = y + 3
            cy_bot = y + _FIELD_H - 3
            if cx < vx + _FIELD_W:
                p.setPen(QPen(_CURSOR_COLOR, 1))
                p.drawLine(int(cx), int(cy_top), int(cx), int(cy_bot))

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()

        # --- Escape → cancel -------------------------------------------------
        if key == Qt.Key_Escape:
            self.input_cancelled.emit()
            self.clear()
            return

        # --- 'd' resets to relative (dX/dY) when in point mode ---------------
        if key == Qt.Key_D and self._input_mode == "point":
            # switch format and clear any typed text, mimicking user intent
            self._switch_format(InputFormat.RELATIVE)
            self._field_1.text = ""
            self._field_1.user_edited = False
            self._field_2.text = ""
            self._field_2.user_edited = False
            self._set_active(self._field_1)
            self._update_placeholders()
            self.update()
            return

        # --- Enter / Return → submit ----------------------------------------
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._on_submit()
            return

        # --- Tab / Shift-Tab → cycle fields ----------------------------------
        if key in (Qt.Key_Tab, Qt.Key_Backtab):
            if self._input_mode == "point":
                self._toggle_active_field()
            return

        # --- Backspace -------------------------------------------------------
        if key == Qt.Key_Backspace:
            af = self._active_field()
            if af.text:
                af.text = af.text[:-1]
                if not af.text:
                    af.user_edited = False
            self._restart_blink()
            self.update()
            return

        # --- Delete (clear field) --------------------------------------------
        if key == Qt.Key_Delete:
            af = self._active_field()
            af.text = ""
            af.user_edited = False
            self._restart_blink()
            self.update()
            return

        # --- Printable text input -------------------------------------------
        text = event.text()
        if text and text.isprintable():
            self._insert_text(text)
            self._restart_blink()
            self.update()
            return

        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Text insertion & format detection
    # ------------------------------------------------------------------

    def _insert_text(self, chars: str) -> None:
        """Insert *chars* into the active field, detecting format tokens."""
        af = self._active_field()

        for ch in chars:
            # --- '#' when typed first in field 1 → absolute ---
            if ch == "#" and af is self._field_1 and not af.text:
                self._switch_format(InputFormat.ABSOLUTE)
                continue  # consume the '#'

            # --- '<' in field 1 → polar (splits into two fields) ---
            if ch == "<" and af is self._field_1 and self._input_mode == "point":
                # everything already typed becomes the distance
                self._switch_format(InputFormat.POLAR)
                self._field_2.text = ""
                self._field_2.user_edited = False
                self._set_active(self._field_2)
                continue

            # --- comma/space moves focus to second field in point mode -------
            if ch in (",", " ") and af is self._field_1 and self._input_mode == "point":
                # switch without inserting the separator character
                self._set_active(self._field_2)
                continue

            af.text += ch
            af.user_edited = True

    # ------------------------------------------------------------------
    # Field management helpers
    # ------------------------------------------------------------------

    def _active_field(self) -> _Field:
        return self._field_1 if self._field_1.active else self._field_2

    def _set_active(self, field: _Field) -> None:
        self._field_1.active = (field is self._field_1)
        self._field_2.active = (field is self._field_2)
        self._restart_blink()

    def _toggle_active_field(self) -> None:
        if self._field_1.active:
            self._set_active(self._field_2)
        else:
            self._set_active(self._field_1)
        self.update()

    # ------------------------------------------------------------------
    # Format / labels
    # ------------------------------------------------------------------

    def _apply_labels(self) -> None:
        if self._input_format == InputFormat.POLAR:
            self._field_1.label = "Dist"
            self._field_2.label = "Ang"
        elif self._input_format == InputFormat.ABSOLUTE:
            self._field_1.label = "X"
            self._field_2.label = "Y"
        else:
            self._field_1.label = "dX"
            self._field_2.label = "dY"

    def _switch_format(self, fmt: InputFormat) -> None:
        if self._input_format == fmt:
            return
        self._input_format = fmt
        self._apply_labels()
        self._update_placeholders()
        self.update()

    # ------------------------------------------------------------------
    # Placeholders (default display)
    # ------------------------------------------------------------------

    def _update_placeholders(self) -> None:
        """Recalculate placeholder text from the current world position."""
        if self._input_mode == "point":
            if self._input_format == InputFormat.ABSOLUTE:
                self._field_1.placeholder = f"{self._current_pos.x:.2f}"
                self._field_2.placeholder = f"{self._current_pos.y:.2f}"
            elif self._input_format == InputFormat.POLAR:
                bp = self._base_point or Vec2(0, 0)
                dx = self._current_pos.x - bp.x
                dy = self._current_pos.y - bp.y
                dist = sqrt(dx * dx + dy * dy)
                angle = degrees(atan2(dy, dx))
                self._field_1.placeholder = f"{dist:.2f}"
                self._field_2.placeholder = f"{angle:.1f}\u00B0"
            else:  # RELATIVE
                bp = self._base_point or Vec2(0, 0)
                dx = self._current_pos.x - bp.x
                dy = self._current_pos.y - bp.y
                self._field_1.placeholder = f"{dx:.2f}"
                self._field_2.placeholder = f"{dy:.2f}"
        elif self._input_mode in ("integer", "float"):
            self._field_1.placeholder = ""
        elif self._input_mode == "string":
            self._field_1.placeholder = ""

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    @Slot()
    def _on_submit(self) -> None:
        self._blink_timer.stop()

        if self._input_mode == "point":
            result = self._parse_vector_input()
        elif self._input_mode == "integer":
            try:
                result = int(self._field_1.text) if self._field_1.text else None
            except ValueError:
                result = None
        elif self._input_mode == "float":
            try:
                result = float(self._field_1.text) if self._field_1.text else None
            except ValueError:
                result = None
        elif self._input_mode == "string":
            result = self._field_1.text if self._field_1.text else None
        else:
            result = None

        if result is not None:
            self.input_submitted.emit(result)
            self.clear()
        else:
            # If no user text was typed, submit the current cursor position
            if self._input_mode == "point":
                self.input_submitted.emit(self._current_pos)
                self.clear()
            else:
                self.input_cancelled.emit()
                self.clear()

    def _parse_vector_input(self) -> Optional[Vec2]:
        """Parse the two fields into a Vec2, respecting the current format."""
        t1 = self._field_1.text
        t2 = self._field_2.text

        # If nothing was typed, return None (caller will use current_pos)
        if not t1 and not t2:
            return None

        # Use placeholder (world-pos default) for any un-typed field
        if not t1:
            t1 = self._field_1.placeholder.rstrip("\u00B0")
        if not t2:
            t2 = self._field_2.placeholder.rstrip("\u00B0")

        if self._input_format == InputFormat.ABSOLUTE:
            input_str = f"#{t1},{t2}"
        elif self._input_format == InputFormat.POLAR:
            input_str = f"{t1}<{t2}"
        else:
            input_str = f"{t1},{t2}"

        return DynamicInputParser.parse_vector(
            input_str,
            self._current_pos,
            base_point=self._base_point,
        )

    # ------------------------------------------------------------------
    # Cursor blink
    # ------------------------------------------------------------------

    def _toggle_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.update()

    def _restart_blink(self) -> None:
        """Reset blink so cursor is visible immediately after a keypress."""
        self._cursor_visible = True
        self._blink_timer.start()

    # ------------------------------------------------------------------
    # Focus handling
    # ------------------------------------------------------------------

    def focusOutEvent(self, event) -> None:  # noqa: N802
        # Focus is managed by the canvas — never hide here.
        super().focusOutEvent(event)
