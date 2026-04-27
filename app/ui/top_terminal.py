"""
Top terminal — consolidated command input + scrollback.

Replaces the floating command palette and cursor-following dynamic input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtCore import QEvent, Qt, Signal, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.editor.dynamic_input_parser import DynamicInputParser
from app.entities import Vec2


@dataclass(frozen=True)
class _CommandEntry:
    command_id: str
    label: str
    aliases: tuple[str, ...] = ()


def _command_display_name(key: str) -> str:
    # Keep the existing palette semantics: strip trailing "Command" suffix and
    # split camelCase/underscores into title case.
    import re

    label = re.sub(r"(?i)command$", "", key)
    parts = re.sub(r"([A-Z])", r" \1", label).replace("_", " ").split()
    return " ".join(p.capitalize() for p in parts) if parts else key


def _label_for_command_entry(key: str, entry: Any) -> str:
    display_name = getattr(entry, "display_name", None)
    if isinstance(display_name, str) and display_name.strip():
        return display_name
    return _command_display_name(key)


class TopTerminalWidget(QFrame):
    """Compact top-center terminal with expandable output + suggestions."""

    command_requested = Signal(str)  # command id to run (idle mode)

    def __init__(self, *, editor, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._editor = editor

        self.setObjectName("TopTerminalWidget")
        self.setFrameShape(QFrame.Shape.NoFrame)
        # This widget is parented to the canvas (crosshair cursor). Override
        # cursor explicitly so the terminal feels like UI chrome, not drawing.
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Fixed compact geometry (dropdown is a separate sibling overlay).
        self.setFixedHeight(44)

        self._cursor_world: Vec2 = Vec2(0, 0)
        self._base_point: Vec2 | None = None

        self._all_commands: list[_CommandEntry] = []
        self._filtered_commands: list[_CommandEntry] = []
        self._match_buttons: list[QToolButton] = []
        self._visible_match_command_ids: list[str] = []
        self._selected_match_idx: int = -1
        self._suppress_next_empty_enter_input: bool = False

        self._history: list[str] = []
        self._history_idx: int = -1
        self._history_draft: str | None = None
        self._output: list[str] = []

        # --- Input row (this widget) ----------------------------------------
        root = QHBoxLayout(self)
        # The terminal frame is styled as the "textbox"; keep layout padding
        # minimal so the QLineEdit sits flush inside it.
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._mode_label = QLabel("")
        self._mode_label.setObjectName("TopTerminalModeLabel")
        # Hidden by default; when shown it should size to contents so it doesn't
        # create a permanent empty gutter.
        self._mode_label.hide()
        self._mode_label.setCursor(Qt.CursorShape.ArrowCursor)
        root.addWidget(self._mode_label)

        self._input = QLineEdit()
        self._input.setObjectName("TopTerminalInput")
        self._input.setPlaceholderText("Type a command…")
        self._input.returnPressed.connect(self._on_enter)
        self._input.textEdited.connect(self._on_text_edited)
        self._input.installEventFilter(self)
        self._input.setCursor(Qt.CursorShape.IBeamCursor)
        root.addWidget(self._input, 1)

        # Inline command matches (buttons) to the right of the input.
        self._matches_bar = QWidget(self)
        self._matches_bar.setObjectName("TopTerminalMatchesBar")
        self._matches_bar.setCursor(Qt.CursorShape.ArrowCursor)
        self._matches_layout = QHBoxLayout(self._matches_bar)
        self._matches_layout.setContentsMargins(0, 0, 0, 0)
        self._matches_layout.setSpacing(6)
        root.addWidget(self._matches_bar, 0)

        self._expand_btn = QToolButton()
        self._expand_btn.setObjectName("TopTerminalExpandButton")
        self._expand_btn.setText("▾")
        self._expand_btn.setCheckable(True)
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.toggled.connect(self._set_expanded)
        root.addWidget(self._expand_btn)

        # --- Expandable panel (sibling overlay, parented to the canvas) -----
        # NOTE: This must *not* be a child of the compact terminal widget,
        # otherwise it will be clipped by the terminal's geometry.
        self._panel = QFrame(self.parentWidget() or self)
        self._panel.setObjectName("TopTerminalPanel")
        self._panel.setCursor(Qt.CursorShape.ArrowCursor)
        self._panel.hide()
        self._panel.setFixedHeight(240)
        self._panel.setFixedWidth(800)
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(10, 6, 10, 10)
        panel_layout.setSpacing(6)

        self._output_list = QListWidget()
        self._output_list.setObjectName("TopTerminalOutputList")
        self._output_list.setCursor(Qt.CursorShape.ArrowCursor)
        panel_layout.addWidget(self._output_list, 1)

        clear_row = QHBoxLayout()
        clear_row.setContentsMargins(0, 0, 0, 0)
        clear_row.setSpacing(8)
        clear_row.addStretch(1)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("TopTerminalClearButton")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_scrollback)
        clear_row.addWidget(clear_btn)
        panel_layout.addLayout(clear_row)

        # Basic inline styling (theme/QSS can override later).
        self.setStyleSheet(
            # Style the terminal container as the input "textbox".
            "QFrame#TopTerminalWidget { background: #2A2A2A; border: 1px solid #3A3A3A; border-radius: 6px; }"
            "QLabel#TopTerminalModeLabel { color: #9ca3af; font-size: 11px; font-family: 'Segoe UI', sans-serif; }"
            # Make the actual input transparent so it feels like you're typing
            # directly into the styled terminal container.
            "QLineEdit#TopTerminalInput { background: transparent; border: none; min-height: 24px;"
            " padding: 0px; margin: 0px;"
            " color: #ffffff; font-size: 12px; font-family: 'Segoe UI', sans-serif; }"
            "QWidget#TopTerminalMatchesBar { background: transparent; }"
            "QToolButton#TopTerminalMatchButton { background: #232323; color: #e5e7eb; border: 1px solid #3A3A3A; padding: 5px 8px; }"
            "QToolButton#TopTerminalMatchButton:hover { background: #2b2b2b; }"
            "QToolButton#TopTerminalMatchButton[selected='true'] { background: #0f172a; border: 1px solid #60a5fa; }"
            "QToolButton#TopTerminalExpandButton { background: transparent; color: #cbd5e1; border: none; }"
            "QFrame#TopTerminalPanel { background: #141414; border: 1px solid #3A3A3A; }"
            "QListWidget#TopTerminalOutputList { background: #141414; color: #d1d5db; border: none;"
            " font-family: 'Segoe UI', sans-serif; font-size: 11px; }"
            "QPushButton#TopTerminalClearButton { padding: 4px 10px; }"
        )
        self._reposition_panel()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_pending_input(self) -> bool:
        """Return True when the terminal input contains user-typed text."""
        return bool(self._input.text().strip())

    def clear_input(self) -> None:
        """Clear the current command/value input and associated suggestions."""
        self._input.clear()
        self._history_idx = -1
        self._history_draft = None
        self._clear_match_buttons()
        self._panel.hide()
        self._expand_btn.setChecked(False)

    def toggle_history_panel(self) -> None:
        """Toggle visibility of the expandable command/output history panel."""
        self._expand_btn.setChecked(not self._expand_btn.isChecked())

    def set_commands(self, commands: dict[str, Any]) -> None:
        entries: list[_CommandEntry] = []
        for k, v in commands.items():
            aliases = getattr(v, "aliases", ())
            if not isinstance(aliases, tuple):
                try:
                    aliases = tuple(aliases)
                except TypeError:
                    aliases = ()
            entries.append(
                _CommandEntry(
                    command_id=k,
                    label=_label_for_command_entry(k, v),
                    aliases=aliases,
                )
            )
        self._all_commands = sorted(entries, key=lambda e: e.label.lower())
        self._apply_filter()

    def _filtered_command_options(self, text: str) -> list[tuple[str, str]]:
        """Return [(key,label)] options filtered by *text* (lowercased)."""
        editor = self._editor
        if editor is None or not editor.is_running:
            return []
        typed = (text or "").strip().lower()
        options = getattr(editor, "command_option_entries", [])
        out: list[tuple[str, str]] = []
        for opt in options:
            key = (getattr(opt, "key", "") or "").strip()
            label = (getattr(opt, "label", "") or "").strip()
            if not label:
                continue
            if not typed:
                out.append((key, label))
                continue
            if (key and typed in key.lower()) or typed in label.lower():
                out.append((key, label))
        return out

    def focus_with_seed(self, seed: str = "") -> None:
        # Seed typed character(s) from the canvas while keeping default UX
        # as keyboard-first.
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if seed:
            self._input.setText(seed)
            self._input.setCursorPosition(len(seed))
        self._apply_filter()
        # Suggestions are rendered inline as match buttons; no panel expansion.

    def update_cursor_world(self, x: float, y: float) -> None:
        self._cursor_world = Vec2(x, y)

    def append_scrollback(self, line: str) -> None:
        line = (line or "").strip()
        if not line:
            return
        self._output.append(line)
        self._output_list.addItem(QListWidgetItem(line))
        self._output_list.scrollToBottom()
        if self._expand_btn.isChecked():
            self._panel.show()
            self._panel.raise_()

    def handle_key_event(self, event: QKeyEvent) -> bool:
        # Allow canvas to forward keys here without stealing focus.
        if event.key() == Qt.Key.Key_Escape:
            self._clear_terminal()
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_enter()
            return True
        if event.key() == Qt.Key.Key_Backspace:
            t = self._input.text()
            self._input.setText(t[:-1])
            self._apply_filter()
            return True
        if event.key() == Qt.Key.Key_Up:
            self._history_up()
            return True
        if event.key() == Qt.Key.Key_Down:
            self._history_down()
            return True
        if event.key() == Qt.Key.Key_Left:
            return self._select_match_delta(-1)
        if event.key() == Qt.Key.Key_Right:
            return self._select_match_delta(1)
        if event.text() and event.text().isprintable():
            self._input.setText(self._input.text() + event.text())
            self._apply_filter()
            return True
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clear_terminal(self) -> None:
        """Clear the terminal's current UI state (input + suggestions + panel)."""
        self.clear_input()

    def _set_expanded(self, on: bool) -> None:
        if on:
            self._reposition_panel()
            self._panel.show()
            self._panel.raise_()
        else:
            self._panel.hide()
        self._expand_btn.setText("▴" if on else "▾")

    def _clear_scrollback(self) -> None:
        self._output.clear()
        self._output_list.clear()

    def _on_text_edited(self, _text: str) -> None:
        # Any user edit exits history-navigation mode and drops draft state.
        if self._history_idx >= 0:
            self._history_idx = -1
            self._history_draft = None
        self._apply_filter()

    def _add_history_entry(self, text: str) -> None:
        token = (text or "").strip()
        if not token:
            return
        # Avoid stacking immediate duplicates while still preserving order.
        if self._history and self._history[-1] == token:
            self._history_idx = -1
            self._history_draft = None
            return
        self._history.append(token)
        self._history_idx = -1
        self._history_draft = None

    def _apply_filter(self) -> None:
        text = self._input.text().strip().lower()
        if not text:
            self._filtered_commands = list(self._all_commands)
        else:
            def _score(e: _CommandEntry) -> int | None:
                label = e.label.lower()
                cmd_id = e.command_id.lower()
                aliases = tuple(a.lower() for a in e.aliases)

                # Exact id recall from history should always win.
                if cmd_id == text:
                    return 0
                # Prefer exact alias hits first so shorthand like "l" or "mv"
                # reliably surfaces the intended command.
                if text in aliases:
                    return 1
                if label == text:
                    return 2
                # Then prefer prefix matches (most "command line" UX expects this).
                if label.startswith(text):
                    return 3
                if cmd_id.startswith(text):
                    return 4
                if any(a.startswith(text) for a in aliases):
                    return 5
                # Fall back to contains matches.
                if text in label:
                    return 6
                if text in cmd_id:
                    return 7
                if any(text in a for a in aliases):
                    return 8
                return None

            scored: list[tuple[int, _CommandEntry]] = []
            for e in self._all_commands:
                s = _score(e)
                if s is None:
                    continue
                scored.append((s, e))

            self._filtered_commands = [e for _s, e in sorted(scored, key=lambda t: (t[0], t[1].label.lower()))]
        if self._editor is not None and self._editor.is_running:
            self._refresh_match_buttons_for_command()
        else:
            self._refresh_match_buttons_for_idle()

    def _refresh_match_buttons_for_idle(self) -> None:
        # Only show match buttons while idle; when a command is running the input
        # is used for values/options, not command picking.
        if self._editor is None or self._editor.is_running:
            self._clear_match_buttons()
            return

        typed = self._input.text().strip()
        if not typed:
            self._clear_match_buttons()
            return

        prev_ids = list(self._visible_match_command_ids)
        prev_selected_cmd = (
            self._visible_match_command_ids[self._selected_match_idx]
            if (self._selected_match_idx >= 0 and self._selected_match_idx < len(self._visible_match_command_ids))
            else None
        )

        matches = self._filtered_commands[:4]
        self._visible_match_command_ids = [m.command_id for m in matches]
        self._sync_match_button_count(len(matches))
        for btn, entry in zip(self._match_buttons, matches, strict=False):
            btn.setText(entry.label)
            btn.setToolTip(entry.command_id)
            btn.setProperty("command_id", entry.command_id)
            btn.setProperty("option_value", None)

        # Keep the selected command if it still exists, otherwise default to first.
        if not matches:
            self._set_selected_match_idx(-1)
        else:
            typed_norm = typed.lower()
            exact_idx = -1
            for idx, entry in enumerate(matches):
                if typed_norm == entry.command_id.lower():
                    exact_idx = idx
                    break
                if typed_norm in tuple(a.lower() for a in entry.aliases):
                    exact_idx = idx
                    break
            if exact_idx >= 0:
                self._set_selected_match_idx(exact_idx)
            elif prev_selected_cmd in self._visible_match_command_ids:
                self._set_selected_match_idx(self._visible_match_command_ids.index(prev_selected_cmd))
            elif prev_ids != self._visible_match_command_ids:
                self._set_selected_match_idx(0)
            else:
                # List didn't change, keep current index (clamped).
                self._set_selected_match_idx(self._selected_match_idx)

    def _clear_match_buttons(self) -> None:
        self._visible_match_command_ids = []
        self._set_selected_match_idx(-1)
        self._sync_match_button_count(0)

    def _sync_match_button_count(self, n: int) -> None:
        # Grow
        while len(self._match_buttons) < n:
            btn = QToolButton(self._matches_bar)
            btn.setObjectName("TopTerminalMatchButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAutoRaise(False)
            btn.clicked.connect(self._on_match_button_clicked)
            self._matches_layout.addWidget(btn, 0)
            self._match_buttons.append(btn)
        # Shrink
        while len(self._match_buttons) > n:
            btn = self._match_buttons.pop()
            self._matches_layout.removeWidget(btn)
            btn.deleteLater()

    def _set_selected_match_idx(self, idx: int) -> None:
        if not self._visible_match_command_ids:
            idx = -1
        else:
            idx = max(-1, min(idx, len(self._visible_match_command_ids) - 1))
        self._selected_match_idx = idx
        for i, btn in enumerate(self._match_buttons):
            is_sel = i == idx
            btn.setProperty("selected", "true" if is_sel else "false")
            # Force Qt to re-evaluate the stylesheet for dynamic properties.
            try:
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            except Exception:
                pass
            btn.update()

    def _select_match_delta(self, delta: int) -> bool:
        if self._editor is None or self._editor.is_running:
            return False
        if not self._visible_match_command_ids:
            return False
        if self._selected_match_idx < 0:
            self._set_selected_match_idx(0)
            return True
        n = len(self._visible_match_command_ids)
        self._set_selected_match_idx((self._selected_match_idx + delta) % n)
        return True

    @Slot()
    def _on_match_button_clicked(self) -> None:
        if self._editor is None:
            return
        btn = self.sender()
        option_value = btn.property("option_value") if btn is not None else None
        if self._editor.is_running:
            if isinstance(option_value, str) and option_value.strip():
                self._editor.provide_command_option(option_value.strip())
                self._input.clear()
                self._clear_match_buttons()
            return

        cmd_id = btn.property("command_id") if btn is not None else None
        if isinstance(cmd_id, str) and cmd_id.strip():
            self._suppress_next_empty_enter_input = True
            self._run_command(cmd_id.strip())
            self._input.clear()
            self._clear_match_buttons()

    def _refresh_match_buttons_for_command(self) -> None:
        """Show active-command options as match buttons while a command runs."""
        if self._editor is None or not self._editor.is_running:
            self._clear_match_buttons()
            return

        typed = self._input.text().strip()
        options = self._filtered_command_options(typed)
        if not options:
            self._clear_match_buttons()
            return

        matches = options[:4]
        self._visible_match_command_ids = []
        self._sync_match_button_count(len(matches))
        for btn, (key, label) in zip(self._match_buttons, matches, strict=False):
            shown = f"[{key}] {label}" if key else label
            btn.setText(shown)
            btn.setToolTip(shown)
            btn.setProperty("command_id", None)
            # Prefer sending the key; if absent fall back to label.
            btn.setProperty("option_value", key or label)

        self._set_selected_match_idx(0)

    def _history_up(self) -> None:
        if not self._history:
            return
        if self._history_idx < 0:
            self._history_draft = self._input.text()
            self._history_idx = len(self._history) - 1
        else:
            self._history_idx = max(0, self._history_idx - 1)
        self._input.setText(self._history[self._history_idx])
        self._input.setCursorPosition(len(self._input.text()))
        self._apply_filter()

    def _history_down(self) -> None:
        if not self._history:
            return
        if self._history_idx < 0:
            return
        if self._history_idx >= len(self._history) - 1:
            self._history_idx = -1
            self._input.setText(self._history_draft or "")
            self._history_draft = None
            self._input.setCursorPosition(len(self._input.text()))
            self._apply_filter()
            return
        self._history_idx = min(len(self._history) - 1, self._history_idx + 1)
        self._input.setText(self._history[self._history_idx])
        self._input.setCursorPosition(len(self._input.text()))
        self._apply_filter()

    @Slot()
    def _on_enter(self) -> None:
        if self._editor is None:
            return
        raw = self._input.text()
        text = raw.strip()

        if text:
            self._add_history_entry(text)

        # If the previous Enter started a command, ignore the next "empty Enter"
        # that would otherwise be interpreted as an input submission.
        if (
            not text
            and self._suppress_next_empty_enter_input
            and self._editor.is_running
            and getattr(self._editor, "_input_mode", "none") != "none"
        ):
            self._suppress_next_empty_enter_input = False
            return

        # Command-running mode: provide input to the editor.
        if self._editor.is_running and getattr(self._editor, "_input_mode", "none") != "none":
            if text and getattr(self._editor, "command_option_labels", None):
                try:
                    accepted = self._editor.provide_command_option(text)
                except Exception:
                    accepted = False
                if accepted:
                    self._input.clear()
                    self._clear_match_buttons()
                    return
            self._submit_to_editor(text)
            self._input.clear()
            return

        # Idle mode: run best match from suggestions.
        if not text:
            if not self._editor.is_running:
                last_cmd = getattr(self._editor, "last_command_name", None)
                if isinstance(last_cmd, str) and last_cmd.strip():
                    self._suppress_next_empty_enter_input = True
                    self._add_history_entry(last_cmd)
                    self._run_command(last_cmd)
            self._clear_match_buttons()
            self._panel.hide()
            return
        if self._visible_match_command_ids and self._selected_match_idx >= 0:
            self._suppress_next_empty_enter_input = True
            self._run_command(self._visible_match_command_ids[self._selected_match_idx])
        elif self._filtered_commands:
            self._suppress_next_empty_enter_input = True
            self._run_command(self._filtered_commands[0].command_id)
        self._input.clear()
        self._clear_match_buttons()
        self._panel.hide()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        # When the input has focus, QLineEdit consumes arrow keys for cursor
        # movement. While idle + match buttons are visible, use Left/Right to
        # navigate matches instead (keyboard-only command picking).
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            try:
                key = event.key()
            except Exception:
                key = None
            if key == Qt.Key.Key_Escape:
                self._clear_terminal()
                return True
            if key == Qt.Key.Key_Up:
                self._history_up()
                return True
            if key == Qt.Key.Key_Down:
                self._history_down()
                return True
            if key == Qt.Key.Key_Left:
                return self._select_match_delta(-1)
            if key == Qt.Key.Key_Right:
                return self._select_match_delta(1)
        return super().eventFilter(obj, event)

    def _reposition_panel(self) -> None:
        p = self.parentWidget()
        if p is None:
            return
        # Ensure panel stays parented to the same overlay parent (canvas).
        if self._panel.parentWidget() is not p:
            self._panel.setParent(p)
        gap = 6
        x = self.x()
        y = self.y() + self.height() + gap
        self._panel.move(x, y)

    def moveEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().moveEvent(event)
        if self._expand_btn.isChecked():
            self._reposition_panel()

    def _run_command(self, cmd_id: str) -> None:
        self.append_scrollback(f"> {cmd_id}")
        self.command_requested.emit(cmd_id)

    def _submit_to_editor(self, text: str) -> None:
        editor = self._editor
        mode = getattr(editor, "_input_mode", "none")

        # Keep parity with the old dynamic input: some modes allow “empty” to
        # mean “use current cursor-derived value”.
        if mode == "point":
            base = getattr(editor, "snap_from_point", None)
            v = None
            if text:
                v = DynamicInputParser.parse_vector(
                    text,
                    current_pos=self._cursor_world,
                    base_point=base,
                )
            if v is None:
                v = self._cursor_world
            editor.provide_point(v)
            return

        if mode == "integer":
            if text:
                try:
                    editor.provide_integer(int(float(text)))
                except ValueError:
                    pass
            return

        if mode == "float":
            if text:
                try:
                    editor.provide_float(float(text))
                except ValueError:
                    pass
            return

        if mode == "angle":
            if text:
                try:
                    editor.provide_angle(float(text))
                except ValueError:
                    pass
            return

        if mode == "length":
            if text:
                try:
                    editor.provide_length(float(text))
                except ValueError:
                    pass
            return

        if mode == "string":
            editor.provide_string(text)
            return

        if mode == "choice":
            if text:
                editor.provide_choice(text)
            return

