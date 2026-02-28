"""
Dynamic input widget — appears near cursor during point/value input.

Displays input fields that follow the cursor position and allow the user
to override the default value with typed input. Supports multiple input
formats (relative, absolute, polar for vectors; direct values for scalars).
"""
from __future__ import annotations

from typing import Optional, Callable, Any
from enum import Enum

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QSize, Signal, Slot, QTimer, QObject, QEvent
)
from PySide6.QtGui import QColor, QFont

from app.entities import Vec2
from app.editor.dynamic_input_parser import DynamicInputParser


class InputFormat(Enum):
    RELATIVE = "relative"
    ABSOLUTE = "absolute"
    POLAR    = "polar"


class FieldTabFilter(QObject):
    """Event filter that handles Tab/Shift+Tab navigation between input fields.
    
    This filter ensures that Tab key presses don't escape the dynamic input
    widget but instead cycle between the two input fields.
    """

    def __init__(self, field_1: QLineEdit, field_2: QLineEdit, parent_widget: "DynamicInputWidget") -> None:
        super().__init__()
        self.field_1 = field_1
        self.field_2 = field_2
        self.parent_widget = parent_widget

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Intercept Tab / Shift+Tab so focus never escapes the two fields."""
        if event.type() != QEvent.KeyPress:
            return super().eventFilter(obj, event)

        key = event.key()
        if key not in (Qt.Key_Tab, Qt.Key_Backtab):
            return super().eventFilter(obj, event)

        pw = self.parent_widget
        if pw._input_mode != "point":
            return True  # absorb Tab in scalar mode

        forward = key == Qt.Key_Tab  # Backtab == Shift+Tab

        if forward:
            if obj is self.field_1:
                self.field_2.setFocus()
                self.field_2.selectAll()
            else:
                self.field_1.setFocus()
                self.field_1.selectAll()
        else:
            if obj is self.field_2:
                self.field_1.setFocus()
                self.field_1.selectAll()
            else:
                self.field_2.setFocus()
                self.field_2.selectAll()

        return True


class DynamicInputWidget(QWidget):
    """Widget that appears next to cursor for dynamic input during commands.

    Displays one or more input fields depending on the input mode:
    - Point mode: 2 fields (for vector input)
    - Integer/Float mode: 1 field (for scalar input)
    - String mode: 1 field

    User can cycle between input formats (for vectors) using Tab.
    """

    # Emitted when input is submitted (user presses Enter)
    input_submitted = Signal(object)  # Vec2, int, float, or str
    # Emitted when input is cancelled (user presses Escape)
    input_cancelled = Signal()

    # Offset from cursor where the widget appears (in screen pixels)
    CURSOR_OFFSET_X = 15
    CURSOR_OFFSET_Y = -20

    # Maximum distance from cursor before widget hides automatically
    HIDE_DISTANCE = 200

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        # Mouse events pass through the widget to the canvas underneath so that
        # hovering over the input box never interrupts cursor tracking.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Current input mode and state
        self._input_mode: str = "none"  # "none", "point", "integer", "float", "string"
        self._input_format = InputFormat.RELATIVE
        self._current_pos = Vec2(0, 0)
        self._base_point: Optional[Vec2] = None  # For relative/polar input

        # UI components
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(4)

        # For point input: two fields (e.g., "dx" and "dy")
        self._field_layout = QHBoxLayout()
        self._field_layout.setContentsMargins(0, 0, 0, 0)
        self._field_layout.setSpacing(6)

        self._label_1 = QLabel("")
        self._field_1 = QLineEdit()
        self._field_1.setMaximumWidth(70)
        self._field_1.returnPressed.connect(self._on_submit)
        self._field_1.setFocus()

        self._label_2 = QLabel("")
        self._field_2 = QLineEdit()
        self._field_2.setMaximumWidth(70)
        self._field_2.returnPressed.connect(self._on_submit)

        # Install Tab key event filter on both fields to lock focus between them
        self._tab_filter = FieldTabFilter(self._field_1, self._field_2, self)
        self._field_1.installEventFilter(self._tab_filter)
        self._field_2.installEventFilter(self._tab_filter)

        # Track when the user has manually typed into each field so that
        # mouse-move updates don't overwrite what they've typed.
        # textEdited fires only on user input, never on programmatic setText.
        self._field_1_user_edited = False
        self._field_2_user_edited = False
        self._field_1.textEdited.connect(self._on_field1_edited)
        self._field_2.textEdited.connect(self._on_field2_edited)

        self._field_layout.addWidget(self._label_1)
        self._field_layout.addWidget(self._field_1)
        self._field_layout.addWidget(self._label_2)
        self._field_layout.addWidget(self._field_2)
        self._field_layout.addStretch()

        self._layout.addLayout(self._field_layout)

        # Styling
        self.setStyleSheet("""
            QWidget {
                background-color: #2E2E2E;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QLineEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #444;
                border-radius: 2px;
                padding: 2px 4px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #0E639C;
                color: #FFFFFF;
            }
            QLabel {
                color: #CCCCCC;
                font-size: 11px;
                font-weight: bold;
            }
        """)

        # Keyboard input handling
        self.setFocusPolicy(Qt.StrongFocus)

        # Timer for auto-hide if cursor moves too far
        self._hide_timer = QTimer()
        self._hide_timer.timeout.connect(self._check_cursor_distance)
        self._hide_timer.setInterval(100)

    def set_input_mode(
        self,
        mode: str,
        current_pos: Vec2,
        base_point: Optional[Vec2] = None,
    ) -> None:
        """Set the input mode and update the UI accordingly.

        Parameters
        ----------
        mode:
            "point", "integer", "float", or "string".

        current_pos:
            Current world position (usually cursor position).

        base_point:
            Reference point for relative coordinates (in point mode).
        """
        self._input_mode = mode
        self._current_pos = current_pos
        self._base_point = base_point if base_point is not None else Vec2(0, 0)

        # Reset input format and user-edit flags when mode changes
        self._input_format = InputFormat.RELATIVE
        self._field_1_user_edited = False
        self._field_2_user_edited = False

        if mode == "point":
            self._setup_vector_input()
        elif mode in ("integer", "float", "string"):
            self._setup_scalar_input(mode)
        else:
            self.hide()
            return

        self._update_field_values()
        self.show()
        # Defer focus + selection until after Qt processes the show event,
        # otherwise selectAll() has no effect on a freshly shown widget.
        QTimer.singleShot(0, self._focus_field_1)
        self._hide_timer.start()

    def _focus_field_1(self) -> None:
        """Give keyboard focus to field 1 and select all its text."""
        self._field_1.setFocus()
        self._field_1.selectAll()

    def _setup_vector_input(self) -> None:
        """Configure UI for point (vector) input."""
        self._input_format = InputFormat.RELATIVE
        self._apply_labels()
        self._label_2.show()
        self._field_2.show()

    def _setup_scalar_input(self, mode: str) -> None:
        """Configure UI for scalar (integer/float/string) input."""
        self._label_1.setText("Text" if mode == "string" else "Value")
        self._label_2.hide()
        self._field_2.hide()

    def _update_field_values(self, force: bool = False) -> None:
        """Update the displayed values based on current position and format.

        Fields the user has manually edited are left untouched unless *force*
        is True (used when switching coordinate formats).
        """
        if self._input_mode == "point":
            val1, val2 = DynamicInputParser.format_vector_for_display(
                self._current_pos,
                format_type=self._input_format.value,
                base_point=self._base_point,
            )
            if force or not self._field_1_user_edited:
                self._field_1.setText(val1)
            if force or not self._field_2_user_edited:
                self._field_2.setText(val2)
        else:
            # For scalar inputs, only update if the user hasn't started typing
            if force or not self._field_1_user_edited:
                self._field_1.clear()

    def _apply_labels(self) -> None:
        """Set label text to match the current coordinate format."""
        if self._input_format == InputFormat.POLAR:
            self._label_1.setText("Dist")
            self._label_2.setText("Ang")
        elif self._input_format == InputFormat.ABSOLUTE:
            self._label_1.setText("X")
            self._label_2.setText("Y")
        else:
            self._label_1.setText("dX")
            self._label_2.setText("dY")

    @Slot(str)
    def _on_field1_edited(self, text: str) -> None:
        """Detect '#' and '<' tokens to switch coordinate format."""
        self._field_1_user_edited = True

        if self._input_mode != "point":
            return

        if "<" in text:
            # Split on first '<': left → Dist field, right → Ang field
            left, _, right = text.partition("<")
            self._switch_format(InputFormat.POLAR)
            self._field_1.blockSignals(True)
            self._field_1.setText(left)
            self._field_1.blockSignals(False)
            self._field_2.blockSignals(True)
            self._field_2.setText(right)
            self._field_2.blockSignals(False)
            self._field_2_user_edited = bool(right)
            self._field_2.setFocus()
            if right:
                self._field_2.setCursorPosition(len(right))
            return

        if text.startswith("#"):
            # '#' prefix switches to absolute; strip the '#' from the field
            self._switch_format(InputFormat.ABSOLUTE)
            self._field_1.blockSignals(True)
            self._field_1.setText(text[1:])
            self._field_1.blockSignals(False)
            return

        # Field cleared without a token → reset to relative
        if not text and self._input_format != InputFormat.POLAR:
            self._switch_format(InputFormat.RELATIVE)

    @Slot(str)
    def _on_field2_edited(self, _text: str) -> None:
        self._field_2_user_edited = True

    def _switch_format(self, fmt: InputFormat) -> None:
        """Change coordinate format and update labels (does NOT touch field text)."""
        if self._input_format == fmt:
            return
        self._input_format = fmt
        self._apply_labels()

    def update_cursor_position(self, pos: Vec2) -> None:
        """Update the widget position and displayed values as cursor moves.

        Parameters
        ----------
        pos:
            Current world-space cursor position.
        """
        if self._input_mode == "none" or not self.isVisible():
            return

        self._current_pos = pos
        self._update_field_values()  # respects user-edited flags

    def update_screen_position(self, screen_pos: QPoint) -> None:
        """Update the screen position of the widget.

        Parameters
        ----------
        screen_pos:
            Current cursor screen position (widget will appear nearby).
        """
        # On Windows, move() can trigger a WM_KILLFOCUS on the focused child
        # (QLineEdit), silently dropping the caret. Save and restore focus.
        focused = QApplication.focusWidget()
        had_child_focus = focused is not None and self.isAncestorOf(focused)

        self.move(
            screen_pos.x() + self.CURSOR_OFFSET_X,
            screen_pos.y() + self.CURSOR_OFFSET_Y,
        )

        if had_child_focus:
            focused.setFocus()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Handle keyboard input."""
        if event.key() == Qt.Key_Escape:
            self.input_cancelled.emit()
            self.hide()
            self._hide_timer.stop()
            return

        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        """Hide only if focus has moved completely outside this widget."""
        # isAncestorOf() returns True when focus moved to a child (e.g. the
        # other QLineEdit), so in that case we must NOT hide.
        focused_widget = QApplication.focusWidget()
        if focused_widget is not None and self.isAncestorOf(focused_widget):
            super().focusOutEvent(event)
            return
        self.hide()
        self._hide_timer.stop()
        super().focusOutEvent(event)

    def _check_cursor_distance(self) -> None:
        """Auto-hide if cursor moves too far from the widget."""
        # This is a safety feature; for now, we just keep the timer running
        # and rely on parent to update position. Real implementation would
        # check distance from widget to last known cursor position.
        pass

    @Slot()
    def _on_submit(self) -> None:
        """Parse and submit the current input."""
        self._hide_timer.stop()

        if self._input_mode == "point":
            result = self._parse_vector_input()
        elif self._input_mode == "integer":
            try:
                result = int(self._field_1.text())
            except ValueError:
                self.input_cancelled.emit()
                self.hide()
                return
        elif self._input_mode == "float":
            try:
                result = float(self._field_1.text())
            except ValueError:
                self.input_cancelled.emit()
                self.hide()
                return
        elif self._input_mode == "string":
            result = self._field_1.text()
        else:
            result = None

        if result is not None:
            self.input_submitted.emit(result)
            self.hide()
        else:
            self.input_cancelled.emit()
            self.hide()

    def _parse_vector_input(self) -> Optional[Vec2]:
        """Parse vector input from the two fields."""
        field1_text = self._field_1.text()
        field2_text = self._field_2.text()

        if not field1_text or not field2_text:
            return None

        # Reconstruct the input string based on format
        if self._input_format == InputFormat.ABSOLUTE:
            input_str = f"#{field1_text},{field2_text}"
        elif self._input_format == InputFormat.POLAR:
            input_str = f"{field1_text}<{field2_text}"
        else:  # RELATIVE
            input_str = f"{field1_text},{field2_text}"

        return DynamicInputParser.parse_vector(
            input_str,
            self._current_pos,
            base_point=self._base_point,
        )

    def clear(self) -> None:
        """Clear all fields and reset state."""
        self._field_1.clear()
        self._field_2.clear()
        self._input_mode = "none"
        self._hide_timer.stop()
        self.hide()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(220, 36)
