"""Tests for top terminal command/history UX behavior."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt

from app.document import DocumentStore
from app.editor.editor import Editor
from app.ui.top_terminal import TopTerminalWidget


class _AliveThread:
    def is_alive(self) -> bool:
        return True


def _terminal_with_editor(qtbot):
    editor = Editor(document=DocumentStore())
    terminal = TopTerminalWidget(editor=editor)
    terminal.resize(800, 44)
    terminal.show()
    qtbot.addWidget(terminal)
    return terminal, editor


def test_empty_enter_repeats_last_command_when_idle(qtbot):
    terminal, editor = _terminal_with_editor(qtbot)
    editor._last_command_name = "lineCommand"

    seen: list[str] = []
    terminal.command_requested.connect(seen.append)

    terminal._input.clear()
    terminal._on_enter()

    assert seen == ["lineCommand"]


def test_empty_enter_does_not_repeat_while_command_running(qtbot):
    terminal, editor = _terminal_with_editor(qtbot)
    editor._last_command_name = "lineCommand"
    editor._thread = _AliveThread()  # type: ignore[assignment]

    seen: list[str] = []
    terminal.command_requested.connect(seen.append)

    terminal._input.clear()
    terminal._on_enter()

    assert seen == []


def test_up_down_history_restores_current_draft(qtbot):
    terminal, _editor = _terminal_with_editor(qtbot)
    terminal._history = ["lineCommand", "circleCommand"]

    terminal._input.setFocus()
    terminal._input.setText("co")

    qtbot.keyClick(terminal._input, Qt.Key.Key_Up)
    assert terminal._input.text() == "circleCommand"

    qtbot.keyClick(terminal._input, Qt.Key.Key_Up)
    assert terminal._input.text() == "lineCommand"

    qtbot.keyClick(terminal._input, Qt.Key.Key_Down)
    assert terminal._input.text() == "circleCommand"

    qtbot.keyClick(terminal._input, Qt.Key.Key_Down)
    assert terminal._input.text() == "co"


def test_history_recall_prefers_exact_command_id_match(qtbot):
    terminal, _editor = _terminal_with_editor(qtbot)
    terminal.set_commands(
        {
            "core.line": SimpleNamespace(
                display_name="Line",
                aliases=("lineCommand", "l"),
            ),
            "core.linear_dimension": SimpleNamespace(
                display_name="Dimension",
                aliases=("linearDimensionCommand",),
            ),
        }
    )
    terminal._history = ["core.line"]

    terminal._history_up()

    assert terminal._input.text() == "core.line"
    assert terminal._visible_match_command_ids
    selected_id = terminal._visible_match_command_ids[terminal._selected_match_idx]
    assert selected_id == "core.line"
