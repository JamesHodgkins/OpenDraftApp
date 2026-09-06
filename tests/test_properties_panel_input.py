"""Regression tests for command-row text input focus behavior."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit

from app.editor.stateful_command import ExportInfo, StatefulCommandBase, export
from app.entities import Vec2
from app.ui.properties_panel import _CmdPointRow, _CmdScalarRow


def _row_text(row) -> str:
    edit = row.findChild(QLineEdit)
    assert edit is not None
    return edit.text()


def _space_key_event() -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ")


def _arrow_key_event(key) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


def test_cmd_point_row_append_text_keeps_first_character(qtbot) -> None:
    row = _CmdPointRow(
        ExportInfo(name="radius", label="Radius", input_kind="vector", default=None),
        point_parser=lambda _text: None,
    )
    qtbot.addWidget(row)
    row.show()

    row.append_text("2")
    qtbot.wait(0)
    row.append_text("0")
    row.append_text("0")

    assert _row_text(row) == "200"


def test_cmd_scalar_row_append_text_keeps_first_character(qtbot) -> None:
    row = _CmdScalarRow(
        ExportInfo(name="distance", label="Distance", input_kind="length", default=None)
    )
    qtbot.addWidget(row)
    row.show()

    row.append_text("2")
    qtbot.wait(0)
    row.append_text("0")
    row.append_text("0")

    assert _row_text(row) == "200"


def test_cmd_scalar_row_space_commits_like_enter(qtbot) -> None:
    """Regression test for KNOWN_BUGS #2 — Space commits typed values."""
    row = _CmdScalarRow(
        ExportInfo(name="distance", label="Distance", input_kind="length", default=None)
    )
    qtbot.addWidget(row)
    row.show()

    committed = []
    row.value_changed.connect(lambda v: committed.append(v))

    edit = row.findChild(QLineEdit)
    edit.setText("200")
    edit.keyPressEvent(_space_key_event())

    assert committed == [200.0]


def test_cmd_scalar_row_space_is_literal_for_string_input(qtbot) -> None:
    """String-kind exports (e.g. Text's Content) need literal spaces."""
    row = _CmdScalarRow(
        ExportInfo(name="content", label="Content", input_kind="string", default=None)
    )
    qtbot.addWidget(row)
    row.show()

    committed = []
    row.value_changed.connect(lambda v: committed.append(v))

    edit = row.findChild(QLineEdit)
    edit.setText("hello")
    edit.keyPressEvent(_space_key_event())

    assert committed == []
    assert edit.text() == "hello "


class _FakeLineCommand(StatefulCommandBase):
    start_point = export(None, label="Start point", input_kind="point")

    def execute(self) -> None:  # pragma: no cover - not exercised
        pass


def test_panel_space_commits_command_bar_value(qtbot) -> None:
    """Space in the top command bar commits a typed value like Enter does."""
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    editor = Editor(document=doc)
    panel = PropertiesPanel(doc, editor)
    qtbot.addWidget(panel)

    cmd = _FakeLineCommand(editor)
    editor._active_command = cmd
    panel.bind_stateful_command(cmd)

    submitted = []
    panel.header_value_submitted.connect(lambda text: submitted.append(text))

    panel._cmd_input.setText("0,0")
    panel._cmd_input.keyPressEvent(_space_key_event())

    assert submitted == ["0,0"]
    assert panel._cmd_input.text() == ""


def test_cmd_scalar_row_indicative_text_does_not_overwrite_typed_input(qtbot) -> None:
    """Regression test for KNOWN_BUGS #4 — indicative readout never clobbers real input."""
    row = _CmdScalarRow(
        ExportInfo(name="radius", label="Radius", input_kind="length", default=None)
    )
    qtbot.addWidget(row)
    row.show()

    row.set_indicative_text("12.5")
    edit = row.findChild(QLineEdit)
    assert edit.text() == ""
    assert edit.placeholderText() == "12.5"

    edit.setText("7")
    row.set_indicative_text("99")
    assert edit.text() == "7"  # typed value is never overwritten


def test_cmd_point_row_left_right_cycles_style_only_for_vector_kind(qtbot) -> None:
    """Left/Right on an empty vector row requests a style cycle; point rows don't."""
    vector_row = _CmdPointRow(
        ExportInfo(name="end_point", label="End vector", input_kind="vector", default=None),
        point_parser=lambda _text: None,
    )
    qtbot.addWidget(vector_row)
    vector_row.show()

    requests = []
    vector_row.cycle_style_requested.connect(requests.append)
    edit = vector_row.findChild(QLineEdit)
    edit.keyPressEvent(_arrow_key_event(Qt.Key.Key_Right))
    edit.keyPressEvent(_arrow_key_event(Qt.Key.Key_Left))

    assert requests == [1, -1]

    point_row = _CmdPointRow(
        ExportInfo(name="center", label="Center", input_kind="point", default=None),
        point_parser=lambda _text: None,
    )
    qtbot.addWidget(point_row)
    point_row.show()

    point_requests = []
    point_row.cycle_style_requested.connect(point_requests.append)
    point_edit = point_row.findChild(QLineEdit)
    point_edit.keyPressEvent(_arrow_key_event(Qt.Key.Key_Right))

    assert point_requests == []  # point rows have no ambiguous format to cycle


def test_cmd_point_row_left_right_moves_cursor_once_field_has_text(qtbot) -> None:
    """Once the user has typed something, Left/Right must move the text cursor, not cycle."""
    row = _CmdPointRow(
        ExportInfo(name="end_point", label="End vector", input_kind="vector", default=None),
        point_parser=lambda _text: None,
    )
    qtbot.addWidget(row)
    row.show()

    requests = []
    row.cycle_style_requested.connect(requests.append)
    edit = row.findChild(QLineEdit)
    edit.setText("3,4")
    edit.setCursorPosition(3)
    edit.keyPressEvent(_arrow_key_event(Qt.Key.Key_Left))

    assert requests == []
    assert edit.cursorPosition() == 2  # moved left through the text as normal


class _FakeCircleCommand(StatefulCommandBase):
    center = export(None, label="Center", input_kind="point")
    radius = export(None, label="Radius", input_kind="length")

    def execute(self) -> None:  # pragma: no cover - not exercised
        pass

    def live_preview_value(self, name, cursor):
        if name == "radius":
            center = self.point_value("center")
            if center is None:
                return None
            return ((cursor.x - center.x) ** 2 + (cursor.y - center.y) ** 2) ** 0.5
        return super().live_preview_value(name, cursor)


def test_panel_shows_indicative_radius_while_drawing_circle(qtbot) -> None:
    """Regression test for KNOWN_BUGS #4.

    With a center picked but no radius typed, the Radius row should show a
    live readout of the current cursor-derived radius as placeholder text.
    """
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    editor = Editor(document=doc)
    panel = PropertiesPanel(doc, editor)
    qtbot.addWidget(panel)

    cmd = _FakeCircleCommand(editor)
    editor._active_command = cmd
    cmd.center = Vec2(0, 0)
    cmd.active_export = "radius"
    panel.bind_stateful_command(cmd)

    panel.update_cursor_world(3.0, 4.0)  # distance from (0,0) is 5

    radius_row = panel._cmd_rows["radius"]
    edit = radius_row.findChild(QLineEdit)
    assert edit.text() == ""
    assert edit.placeholderText() == "5"


def test_panel_indicative_radius_clears_when_no_center_yet(qtbot) -> None:
    """Before a center is picked, Radius has no live value to show."""
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    editor = Editor(document=doc)
    panel = PropertiesPanel(doc, editor)
    qtbot.addWidget(panel)

    cmd = _FakeCircleCommand(editor)
    editor._active_command = cmd
    panel.bind_stateful_command(cmd)

    panel.update_cursor_world(3.0, 4.0)

    radius_row = panel._cmd_rows["radius"]
    edit = radius_row.findChild(QLineEdit)
    assert edit.placeholderText() == "Type a value…"


def test_panel_space_commits_idle_command(qtbot) -> None:
    """Space in the idle command bar starts the best-matching command."""
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    editor = Editor(document=doc)
    panel = PropertiesPanel(doc, editor)
    qtbot.addWidget(panel)
    from app.sdk.commands.spec import CommandSpec

    panel.set_commands({"core.line": CommandSpec(id="core.line", display_name="Line", aliases=("l",))})

    requested = []
    panel.command_requested.connect(lambda cmd_id: requested.append(cmd_id))

    panel._cmd_input.setText("l")
    panel._cmd_input.keyPressEvent(_space_key_event())

    assert requested == ["core.line"]
    assert panel._cmd_input.text() == ""


def _mirror_panel(qtbot):
    """Build a PropertiesPanel bound to a MirrorCommand parked at keep_originals."""
    from app.commands.modify_mirror import MirrorCommand
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.entities import LineEntity
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    editor = Editor(document=doc)
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0))
    doc.add_entity(line)
    editor.selection.add(line.id)

    panel = PropertiesPanel(doc, editor)
    qtbot.addWidget(panel)
    main_win_glue(panel, editor)

    cmd = MirrorCommand(editor)
    editor._active_command = cmd
    cmd.start()
    panel.bind_stateful_command(cmd)
    editor.set_stateful_property("axis_start", Vec2(0, 0))
    editor.set_stateful_property("axis_end", Vec2(0, 10))
    assert cmd.active_export == "keep_originals"
    return panel, editor, cmd


def main_win_glue(panel, editor) -> None:
    """Wire the same property_changed/commit_requested paths MainWindow uses."""
    panel.property_changed.connect(
        lambda name, value: editor.set_stateful_property(name, value)
    )
    panel.commit_requested.connect(editor.commit_command)


def test_single_keystroke_commits_choice_without_space_or_enter(qtbot) -> None:
    """Regression test for KNOWN_BUGS #6 — typing 'y' alone commits Mirror's choice."""
    panel, editor, cmd = _mirror_panel(qtbot)

    panel.inject_text("y")

    assert cmd.keep_originals == "Y"
    assert cmd.active_export == ""  # advanced past the last export


def test_bare_space_on_empty_choice_row_commits_default(qtbot) -> None:
    """Regression test for KNOWN_BUGS #6 — Space with nothing typed keeps originals."""
    panel, editor, cmd = _mirror_panel(qtbot)

    row = panel._cmd_rows["keep_originals"]
    edit = row.findChild(QLineEdit)
    assert edit.text() == ""
    edit.keyPressEvent(_space_key_event())

    assert cmd.keep_originals == "Y"  # first option ("Y") is the default


def test_commit_button_activates_on_enter_when_focused(qtbot) -> None:
    """Regression test: Mirror looked stuck at 'keep originals' in real use.

    A plain QPushButton only reacts to Enter/Return when ``autoDefault`` (or
    ``isDefault``) is set — that wiring normally only happens automatically
    inside a QDialog. This panel is a dock widget, not a dialog, so the
    Commit button silently ignored Enter even while focused: the user
    answered Y/N, focus moved to Commit exactly as intended, they pressed
    Enter expecting it to finish — and nothing happened. Answering the
    choice with a real keystroke sequence (not a direct editor call) and
    then pressing physical Enter on whatever now has focus must actually
    commit the command.
    """
    from PySide6.QtTest import QTest

    panel, editor, cmd = _mirror_panel(qtbot)
    panel.show()

    row = panel._cmd_rows["keep_originals"]
    row.focus_input()
    QTest.keyClick(row._edit, Qt.Key.Key_Y)
    QTest.keyClick(row._edit, Qt.Key.Key_Space)

    assert cmd.all_exports_set()
    assert panel._cmd_commit_btn.hasFocus()
    assert panel._cmd_commit_btn.autoDefault()

    QTest.keyClick(panel._cmd_commit_btn, Qt.Key.Key_Return)

    from app.entities import LineEntity as _LineEntity

    lines = [e for e in editor.document.entities if isinstance(e, _LineEntity)]
    assert len(lines) == 2  # original + mirrored copy — command actually finished
    assert editor.active_command is None


def _idle_panel_with_last_command(qtbot, command_id: str = "core.line"):
    """Build an idle PropertiesPanel that has already run *command_id* once."""
    import app.commands  # noqa: F401 — registers built-in commands
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    editor = Editor(document=doc)
    panel = PropertiesPanel(doc, editor)
    qtbot.addWidget(panel)
    panel.command_requested.connect(editor.run_command)

    editor.run_command(command_id)
    editor.cancel_command()  # back to idle; last_command_name stays set
    assert editor.last_command_name == command_id
    assert not editor.is_running
    return panel, editor


def test_empty_enter_repeats_last_command(qtbot) -> None:
    """Regression test for KNOWN_BUGS #7 — bare Enter in idle mode reruns the last command."""
    panel, editor = _idle_panel_with_last_command(qtbot)

    assert panel._cmd_input.text() == ""
    panel._cmd_input.returnPressed.emit()

    assert editor.is_running
    assert editor.last_command_name == "core.line"


def test_empty_space_repeats_last_command(qtbot) -> None:
    """Regression test for KNOWN_BUGS #7 — bare Space in idle mode reruns the last command."""
    panel, editor = _idle_panel_with_last_command(qtbot)

    assert panel._cmd_input.text() == ""
    panel._cmd_input.keyPressEvent(_space_key_event())

    assert editor.is_running
    assert editor.last_command_name == "core.line"


def test_empty_enter_does_nothing_with_no_last_command(qtbot) -> None:
    """No prior command run — empty Enter must not error or start anything."""
    from app.document import DocumentStore
    from app.editor.editor import Editor
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    editor = Editor(document=doc)
    panel = PropertiesPanel(doc, editor)
    qtbot.addWidget(panel)

    requested = []
    panel.command_requested.connect(requested.append)

    panel._cmd_input.returnPressed.emit()

    assert requested == []
