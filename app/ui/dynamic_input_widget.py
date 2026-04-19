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

Per-mode behaviour (labels, placeholders, submission parsing) is encapsulated
in :class:`_ModeStrategy` subclasses so the main widget class is not
responsible for branching on every input mode.
"""
from __future__ import annotations

from enum import Enum
from math import atan2, degrees, sqrt
from typing import Any, Optional

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
# Input mode strategies
# ---------------------------------------------------------------------------

class _ModeStrategy:
    """Base class for per-mode input behaviour.

    Subclasses encapsulate the label text, placeholder computation, and
    submission parsing for each editor input mode so that
    :class:`DynamicInputWidget` never branches on mode names directly.

    Attributes
    ----------
    is_two_field:
        ``True`` only for :class:`_PointMode`.  Controls whether the widget
        shows a second field and uses the two-column layout.
    is_choice:
        ``True`` only for :class:`_ChoiceMode`.  Single keypress submits
        immediately without waiting for Enter.
    """

    is_two_field: bool = False
    is_choice: bool = False

    def apply_labels(
        self,
        f1: "_Field",
        f2: "_Field",
        *,
        fmt: InputFormat = InputFormat.RELATIVE,
        widget: "DynamicInputWidget | None" = None,
    ) -> None:
        """Set label text on *f1* and *f2*.  Called on mode activation and after
        a format-change (``#``, ``<`` prefixes in point mode)."""

    def update_placeholders(
        self,
        f1: "_Field",
        f2: "_Field",
        widget: "DynamicInputWidget",
    ) -> None:
        """Refresh placeholder text from the current cursor world position."""

    def submit(
        self,
        f1_text: str,
        f2_text: str,
        widget: "DynamicInputWidget",
    ) -> Any:
        """Parse typed text and return a value, or ``None`` to cancel / use cursor."""
        return None


class _PointMode(_ModeStrategy):
    is_two_field = True

    def apply_labels(self, f1, f2, *, fmt=InputFormat.RELATIVE, widget=None):
        if fmt == InputFormat.POLAR:
            f1.label, f2.label = "Dist", "Ang"
        elif fmt == InputFormat.ABSOLUTE:
            f1.label, f2.label = "X", "Y"
        else:
            f1.label, f2.label = "dX", "dY"

    def update_placeholders(self, f1, f2, w):
        pos = w._current_pos
        if w._input_format == InputFormat.ABSOLUTE:
            f1.placeholder = f"{pos.x:.2f}"
            f2.placeholder = f"{pos.y:.2f}"
        elif w._input_format == InputFormat.POLAR:
            bp = w._base_point or Vec2(0, 0)
            dx, dy = pos.x - bp.x, pos.y - bp.y
            f1.placeholder = f"{sqrt(dx * dx + dy * dy):.2f}"
            f2.placeholder = f"{degrees(atan2(dy, dx)):.1f}\u00B0"
        else:                                # RELATIVE
            bp = w._base_point or Vec2(0, 0)
            f1.placeholder = f"{pos.x - bp.x:.2f}"
            f2.placeholder = f"{pos.y - bp.y:.2f}"

    def submit(self, f1_text, f2_text, w):
        if not f1_text and not f2_text:
            return None  # caller will emit current_pos instead
        t1 = f1_text or w._field_1.placeholder.rstrip("\u00B0")
        t2 = f2_text or w._field_2.placeholder.rstrip("\u00B0")
        if w._input_format == InputFormat.ABSOLUTE:
            input_str = f"#{t1},{t2}"
        elif w._input_format == InputFormat.POLAR:
            input_str = f"{t1}<{t2}"
        else:
            input_str = f"{t1},{t2}"
        return DynamicInputParser.parse_vector(
            input_str, w._current_pos, base_point=w._base_point)


class _IntegerMode(_ModeStrategy):
    def apply_labels(self, f1, f2, *, fmt=InputFormat.RELATIVE, widget=None):
        f1.label = "Val"

    def update_placeholders(self, f1, f2, w):
        f1.placeholder = ""

    def submit(self, f1_text, f2_text, w):
        if not f1_text:
            return None
        try:
            return int(f1_text)
        except ValueError:
            return None


class _FloatMode(_ModeStrategy):
    def apply_labels(self, f1, f2, *, fmt=InputFormat.RELATIVE, widget=None):
        f1.label = "Val"

    def update_placeholders(self, f1, f2, w):
        f1.placeholder = ""

    def submit(self, f1_text, f2_text, w):
        if not f1_text:
            return None
        try:
            return float(f1_text)
        except ValueError:
            return None


class _AngleMode(_ModeStrategy):
    def apply_labels(self, f1, f2, *, fmt=InputFormat.RELATIVE, widget=None):
        f1.label = "Ang"

    def update_placeholders(self, f1, f2, w):
        center = w._angle_center or Vec2(0, 0)
        dx = w._current_pos.x - center.x
        dy = w._current_pos.y - center.y
        f1.placeholder = f"{degrees(atan2(dy, dx)):.1f}\u00B0"

    def submit(self, f1_text, f2_text, w):
        if f1_text:
            try:
                return float(f1_text)
            except ValueError:
                pass
        center = w._angle_center or Vec2(0, 0)
        dx = w._current_pos.x - center.x
        dy = w._current_pos.y - center.y
        return degrees(atan2(dy, dx))


class _LengthMode(_ModeStrategy):
    def apply_labels(self, f1, f2, *, fmt=InputFormat.RELATIVE, widget=None):
        f1.label = "Len"

    def update_placeholders(self, f1, f2, w):
        base = w._length_base or Vec2(0, 0)
        dx = w._current_pos.x - base.x
        dy = w._current_pos.y - base.y
        f1.placeholder = f"{sqrt(dx * dx + dy * dy):.2f}"

    def submit(self, f1_text, f2_text, w):
        if f1_text:
            try:
                return float(f1_text)
            except ValueError:
                pass
        base = w._length_base or Vec2(0, 0)
        dx = w._current_pos.x - base.x
        dy = w._current_pos.y - base.y
        return sqrt(dx * dx + dy * dy)


class _StringMode(_ModeStrategy):
    def apply_labels(self, f1, f2, *, fmt=InputFormat.RELATIVE, widget=None):
        f1.label = "Text"

    def update_placeholders(self, f1, f2, w):
        f1.placeholder = ""

    def submit(self, f1_text, f2_text, w):
        return f1_text if f1_text else None


class _ChoiceMode(_ModeStrategy):
    is_choice = True

    def apply_labels(self, f1, f2, *, fmt=InputFormat.RELATIVE, widget=None):
        f1.label = ""
        f1.placeholder = ""

    def update_placeholders(self, f1, f2, w):
        f1.placeholder = ""

    def submit(self, f1_text, f2_text, w):
        idx = getattr(w, "_choice_index", 0)
        opts = w._choice_options
        return opts[idx] if opts else None


# Map mode name strings to strategy classes.
_MODE_STRATEGIES: dict[str, type[_ModeStrategy]] = {
    "point":   _PointMode,
    "integer": _IntegerMode,
    "float":   _FloatMode,
    "angle":   _AngleMode,
    "length":  _LengthMode,
    "string":  _StringMode,
    "choice":  _ChoiceMode,
}


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
        self._input_mode: str = "none"   # kept for backwards compat; prefer _mode_strategy
        self._mode_strategy: Optional[_ModeStrategy] = None
        self._choice_options: list[str] = []
        self._input_format = InputFormat.RELATIVE
        self._current_pos = Vec2(0, 0)   # world cursor position
        self._base_point: Optional[Vec2] = None
        self._angle_center: Optional[Vec2] = None
        self._length_base: Optional[Vec2] = None

        # Choice-mode navigation index
        self._choice_index: int = 0

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
        choice_options: Optional[list[str]] = None,
        angle_center: Optional[Vec2] = None,
        length_base: Optional[Vec2] = None,
    ) -> None:
        """Activate the widget for *mode* ("point", "integer", "float", "string", "choice", "angle", "length")."""
        self._input_mode = mode
        self._current_pos = current_pos
        self._base_point = base_point if base_point is not None else Vec2(0, 0)
        self._choice_options = list(choice_options or [])
        self._choice_index = 0
        self._angle_center = angle_center
        self._length_base = length_base

        strategy_cls = _MODE_STRATEGIES.get(mode)
        if strategy_cls is None:
            self._mode_strategy = None
            self.hide()
            return
        self._mode_strategy = strategy_cls()

        # Reset fields
        self._input_format = InputFormat.RELATIVE
        for f in (self._field_1, self._field_2):
            f.text = ""
            f.user_edited = False
        self._field_1.active = True
        self._field_2.active = False

        self._mode_strategy.apply_labels(
            self._field_1, self._field_2,
            fmt=self._input_format, widget=self,
        )
        self._update_placeholders()
        self._resize_to_content()
        self.show()
        self.raise_()
        self._blink_timer.start()
        self._cursor_visible = True
        self.update()

    def update_cursor_position(self, pos: Vec2) -> None:
        """Called when the mouse moves — refreshes placeholder values."""
        if self._mode_strategy is None or not self.isVisible():
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
        self._mode_strategy = None
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
        if self._mode_strategy is not None and self._mode_strategy.is_choice:
            w, h = self._choice_size()
        elif self._mode_strategy is not None and self._mode_strategy.is_two_field:
            w = _PAD_X * 2 + self._field_group_width(self._field_1) + _GROUP_GAP + self._field_group_width(self._field_2)
            h = _PAD_Y * 2 + _FIELD_H
        else:
            w = _PAD_X * 2 + self._field_group_width(self._field_1)
            h = _PAD_Y * 2 + _FIELD_H
        self.setFixedSize(int(w), int(h))

    def sizeHint(self) -> QSize:  # noqa: N802
        if self._mode_strategy is not None and self._mode_strategy.is_choice:
            w, h = self._choice_size()
        elif self._mode_strategy is not None and self._mode_strategy.is_two_field:
            w = _PAD_X * 2 + self._field_group_width(self._field_1) + _GROUP_GAP + self._field_group_width(self._field_2)
            h = _PAD_Y * 2 + _FIELD_H
        else:
            w = _PAD_X * 2 + self._field_group_width(self._field_1)
            h = _PAD_Y * 2 + _FIELD_H
        return QSize(int(w), int(h))

    def _choice_size(self) -> tuple[int, int]:
        """Return (w, h) for the choice list widget."""
        n = max(len(self._choice_options), 1)
        max_w = max(
            (self._fm.horizontalAdvance(o) for o in self._choice_options),
            default=60,
        )
        w = int(_PAD_X * 2 + max_w + 20)   # 20px for the arrow indicator
        h = int(_PAD_Y * 2 + n * (_FIELD_H + 2))
        return w, h

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._mode_strategy is not None and self._mode_strategy.is_choice:
            self._paint_choice_list(p)
            p.end()
            return

        # --- fields ---
        x = _PAD_X
        y = _PAD_Y
        self._paint_field(p, self._field_1, x, y)

        if self._mode_strategy is not None and self._mode_strategy.is_two_field:
            x += self._field_group_width(self._field_1) + _GROUP_GAP
            self._paint_field(p, self._field_2, x, y)

        p.end()

    def _paint_choice_list(self, p: QPainter) -> None:
        """Paint a vertical stack of choice options."""
        from PySide6.QtGui import QColor
        row_h = _FIELD_H + 2
        y = _PAD_Y
        p.setFont(self._font)
        for i, opt in enumerate(self._choice_options):
            row_rect = QRectF(_PAD_X, y, self.width() - _PAD_X * 2, _FIELD_H)
            if i == self._choice_index:
                # Highlight selected row
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#1e3a5f"))
                p.drawRoundedRect(row_rect, 2, 2)
                # Arrow indicator
                p.setPen(QPen(_UNDERLINE_ACTIVE_COLOR))
                p.drawText(QRectF(_PAD_X, y, 14, _FIELD_H),
                           Qt.AlignVCenter | Qt.AlignLeft, "\u25b6")
                p.setPen(QPen(_TEXT_COLOR))
            else:
                p.setPen(QPen(_PLACEHOLDER_COLOR))
            text_rect = QRectF(_PAD_X + 16, y, self.width() - _PAD_X * 2 - 16, _FIELD_H)
            p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, opt)
            y += row_h

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

        # --- Choice mode: Up/Down navigate, Enter confirms -------------------
        if self._mode_strategy is not None and self._mode_strategy.is_choice:
            if key == Qt.Key_Up:
                if self._choice_options:
                    self._choice_index = (self._choice_index - 1) % len(self._choice_options)
                    self.update()
                return
            if key == Qt.Key_Down:
                if self._choice_options:
                    self._choice_index = (self._choice_index + 1) % len(self._choice_options)
                    self.update()
                return
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._on_submit()
                return
            return

        # --- 'd' resets to relative (dX/dY) when in point mode ---------------
        if key == Qt.Key_D and self._mode_strategy is not None and self._mode_strategy.is_two_field:
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
            if self._mode_strategy is not None and self._mode_strategy.is_two_field:
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
            if ch == "<" and af is self._field_1 and self._mode_strategy is not None and self._mode_strategy.is_two_field:
                # everything already typed becomes the distance
                self._switch_format(InputFormat.POLAR)
                self._field_2.text = ""
                self._field_2.user_edited = False
                self._set_active(self._field_2)
                continue

            # --- comma/space moves focus to second field in point mode -------
            if ch in (",", " ") and af is self._field_1 and self._mode_strategy is not None and self._mode_strategy.is_two_field:
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
        if self._mode_strategy is not None:
            self._mode_strategy.apply_labels(
                self._field_1, self._field_2,
                fmt=self._input_format, widget=self,
            )

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
        if self._mode_strategy is not None:
            self._mode_strategy.update_placeholders(self._field_1, self._field_2, self)

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    @Slot()
    def _on_submit(self) -> None:
        self._blink_timer.stop()

        if self._mode_strategy is None:
            return

        result = self._mode_strategy.submit(
            self._field_1.text, self._field_2.text, self
        )

        if result is not None:
            self.input_submitted.emit(result)
            self.clear()
        elif self._mode_strategy.is_two_field:
            # Point mode with no typed text → emit current cursor position
            self.input_submitted.emit(self._current_pos)
            self.clear()
        else:
            self.input_cancelled.emit()
            self.clear()

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
