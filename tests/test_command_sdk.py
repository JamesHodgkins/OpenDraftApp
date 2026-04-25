"""Tests for the stable command SDK layer."""
from __future__ import annotations

from app.document import DocumentStore
from app.editor.command_registry import (
    get_command,
    get_command_spec,
    registered_command_specs,
)
from app.editor.editor import Editor
from app.editor.undo import UndoCommand
from app.entities import LineEntity, Vec2
from app.sdk.commands import CommandContext, CommandSpec, command, register


def test_sdk_function_command_registration_and_execution() -> None:
    command_id = "tests.sdk_function_command"
    alias = "tests.sdk_function_alias"

    @command(
        command_id,
        display_name="SDK Function Command",
        description="Function-style SDK command",
        aliases=(alias,),
        source="tests",
    )
    def _sdk_function(ctx: CommandContext) -> None:
        ctx.status("sdk function executed")

    cmd_cls = get_command(command_id)
    alias_cls = get_command(alias)
    assert cmd_cls is not None
    assert alias_cls is cmd_cls

    spec = get_command_spec(command_id)
    assert spec is not None
    assert spec.display_name == "SDK Function Command"
    assert spec.description == "Function-style SDK command"
    assert spec.source == "tests"
    assert alias in spec.aliases

    ed = Editor(document=DocumentStore())
    seen: list[str] = []
    ed.status_message.connect(lambda message: seen.append(message))

    cmd_cls(ed).execute()
    assert seen[-1] == "sdk function executed"


def test_sdk_class_command_registration_and_execution() -> None:
    command_id = "tests.sdk_class_command"

    @register(
        CommandSpec(
            id=command_id,
            display_name="SDK Class Command",
            description="Class-style SDK command",
            source="tests",
        )
    )
    class _SdkClassCommand:
        def execute(self, ctx: CommandContext) -> None:
            ctx.status("sdk class executed")

    cmd_cls = get_command(command_id)
    assert cmd_cls is not None

    specs = registered_command_specs()
    assert command_id in specs
    assert specs[command_id].display_name == "SDK Class Command"

    ed = Editor(document=DocumentStore())
    seen: list[str] = []
    ed.status_message.connect(lambda message: seen.append(message))

    cmd_cls(ed).execute()
    assert seen[-1] == "sdk class executed"


def test_command_context_exposes_helper_scopes_and_transactions() -> None:
    ed = Editor(document=DocumentStore())
    ctx = CommandContext(ed)

    preview_ent = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    with ctx.preview(lambda _mouse: [preview_ent]):
        assert ed.get_dynamic(Vec2(0, 0)) == [preview_ent]
    assert ed.get_dynamic(Vec2(0, 0)) == []

    with ctx.highlighted([preview_ent]):
        assert ed.get_highlight() == [preview_ent]
    assert ed.get_highlight() == []

    events: list[str] = []

    class _Marker(UndoCommand):
        def __init__(self, label: str) -> None:
            self.description = label

        def redo(self) -> None:
            events.append(f"redo:{self.description}")

        def undo(self) -> None:
            events.append(f"undo:{self.description}")

    with ctx.transaction("SDK helper batch") as tx:
        tx.add_undo(_Marker("a"))
        tx.add_undo(_Marker("b"))

    assert ed.undo_stack.undo_text == "SDK helper batch"
    assert ctx.undo() is True
    assert events == ["undo:b", "undo:a"]


def test_command_context_push_undo_and_notify_document_wrappers() -> None:
    ed = Editor(document=DocumentStore())
    ctx = CommandContext(ed)

    notifications: list[str] = []
    ed.document_changed.connect(lambda: notifications.append("changed"))

    events: list[str] = []

    class _Marker(UndoCommand):
        description = "SDK marker"

        def redo(self) -> None:
            events.append("redo")

        def undo(self) -> None:
            events.append("undo")

    ctx.push_undo(_Marker())
    ctx.notify_document()

    assert ed.undo_stack.undo_text == "SDK marker"
    assert notifications
    assert ctx.undo() is True
    assert events == ["undo"]
