"""Regression coverage for MainWindow stateful-command glue."""
from __future__ import annotations

import os
import sys

from app.editor.stateful_command import StatefulCommandBase, export
from app.main_window import MainWindow


class _FakeStatefulCommand(StatefulCommandBase):
    choice = export(None, label="Choice", input_kind="choice")

    def advance_active_export(self) -> None:
        if self.choice is not None:
            self.active_export = ""

    def commit(self) -> None:
        return None


class _FakeEditor:
    def __init__(self, command=None) -> None:
        self.active_command = command
        self._choice_options = ["Y", "N"]


class _FakePanel:
    def __init__(self) -> None:
        self.bound = None
        self.focused = False
        self.cleared = False
        self.refreshed = False

    def is_bound_to_stateful_command(self, command) -> bool:
        return self.bound is command

    def bind_stateful_command(self, command) -> None:
        self.bound = command

    def focus_command_input(self) -> None:
        self.focused = True

    def clear_stateful_command(self) -> None:
        self.cleared = True

    def refresh(self) -> None:
        self.refreshed = True


class _FakeDock:
    def __init__(self) -> None:
        self.shown = False
        self.raised = False

    def show(self) -> None:
        self.shown = True

    def raise_(self) -> None:
        self.raised = True


def test_input_mode_change_binds_active_stateful_command() -> None:
    window = MainWindow.__new__(MainWindow)
    cmd = _FakeStatefulCommand(_FakeEditor())
    window.editor = _FakeEditor(cmd)
    window._props_panel = _FakePanel()
    window._props_dock = _FakeDock()

    window._on_input_mode_changed("choice")

    assert window._props_panel.bound is cmd
    assert window._props_panel.focused
    assert window._props_dock.shown
    assert window._props_dock.raised


def test_header_value_parser_accepts_choice_hotkey() -> None:
    window = MainWindow.__new__(MainWindow)
    window.editor = _FakeEditor()

    assert window._parse_header_value("y", "choice") == "Y"
    assert window._parse_header_value("n", "choice") == "N"
    assert window._parse_header_value("maybe", "choice") is None


def test_empty_enter_on_active_choice_commits_default() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.commands.modify_mirror import MirrorCommand
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.entities import LineEntity, Vec2
    from app.ui.properties_panel import PropertiesPanel

    app = QApplication.instance() or QApplication(sys.argv)
    editor = Editor(document=DocumentStore())
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    editor.document.add_entity(line)
    editor.selection.add(line.id)

    command = MirrorCommand(editor)
    editor._active_command = command
    command.start()

    panel = PropertiesPanel(editor.document, editor)
    try:
        panel.bind_stateful_command(command)
        editor.stateful_value_changed.connect(panel.set_command_property_value)
        editor.stateful_active_export_changed.connect(panel.set_active_command_property)
        panel.property_changed.connect(
            lambda name, value: editor.set_stateful_property(name, value)
        )
        editor.set_stateful_property("axis_start", Vec2(0, 0))
        editor.set_stateful_property("axis_end", Vec2(0, 10))

        assert command.active_export == "keep_originals"

        panel._on_cmd_input_return()
        app.processEvents()

        assert command.keep_originals == "Y"
        assert command.active_export == ""
    finally:
        panel.close()
