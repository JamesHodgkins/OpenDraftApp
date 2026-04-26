"""Tests for editor selection deletion helpers."""
from __future__ import annotations

import threading
import time

import pytest

from app.editor.editor import CommandOption, CommandOptionSelection, Editor
from app.editor.undo import UndoCommand
from app.document import DocumentStore
from app.entities import Vec2, LineEntity


def _wait_until(predicate, timeout: float = 1.0) -> bool:
    """Poll *predicate* until true or timeout."""
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_delete_selection_removes_all_and_clears():
    doc = DocumentStore()
    ed = Editor(document=doc)

    # add two entities, select both
    e1 = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    e2 = LineEntity(p1=Vec2(1, 1), p2=Vec2(2, 2))
    doc.add_entity(e1)
    doc.add_entity(e2)
    ed.selection.add(e1.id)
    ed.selection.add(e2.id)

    removed = ed.delete_selection()
    # order should match the selection iteration order
    assert e1 in removed and e2 in removed
    # both gone from document
    assert doc.get_entity(e1.id) is None
    assert doc.get_entity(e2.id) is None
    # selection cleared
    assert not ed.selection


def test_delete_selection_emits_signals():
    doc = DocumentStore()
    ed = Editor(document=doc)

    e = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    doc.add_entity(e)
    ed.selection.add(e.id)

    seen: list[str] = []
    ed.entity_removed.connect(lambda eid: seen.append(eid))

    ed.delete_selection()
    assert seen == [e.id]


def test_get_command_option_returns_selected_label() -> None:
    doc = DocumentStore()
    ed = Editor(document=doc)

    result: list[str] = []

    def _worker() -> None:
        result.append(ed.get_command_option("Rotate: choose option", ["Set base vector", "Set destination vector"]))

    t = threading.Thread(target=_worker, daemon=True)
    ed._thread = t
    t.start()

    assert _wait_until(lambda: bool(ed.command_option_labels))
    ed.provide_command_option("set destination vector")
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert result == ["Set destination vector"]


def test_provide_command_option_accepts_keyed_shortcuts() -> None:
    doc = DocumentStore()
    ed = Editor(document=doc)

    result: list[Vec2 | CommandOptionSelection] = []

    def _worker() -> None:
        # Mimic real command flow: point input mode but command options allowed.
        result.append(
            ed.get_point(
                "Rotate: specify rotation vector or choose option",
                allow_command_options=True,
            )
        )

    # Commands may register keyed options for terminal usage.
    ed.set_command_options_keyed(
        [
            CommandOption(key="b", label="Set base vector"),
            CommandOption(key="d", label="Set destination vector"),
        ]
    )

    t = threading.Thread(target=_worker, daemon=True)
    ed._thread = t
    t.start()

    assert _wait_until(lambda: ed.is_running and ed.input_mode == "point")
    assert ed.provide_command_option("b")
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert len(result) == 1
    assert isinstance(result[0], CommandOptionSelection)
    assert result[0].label == "Set base vector"


def test_get_angle_can_return_command_option_selection() -> None:
    doc = DocumentStore()
    ed = Editor(document=doc)
    ed.set_command_options(["Set base vector"])

    result: list[float | CommandOptionSelection] = []

    def _worker() -> None:
        result.append(
            ed.get_angle(
                "Rotate: pick a point or enter angle (degrees)",
                center=Vec2(0, 0),
                allow_command_options=True,
            )
        )

    t = threading.Thread(target=_worker, daemon=True)
    ed._thread = t
    t.start()

    assert _wait_until(lambda: ed.input_mode == "angle")
    ed.provide_command_option("set base vector")
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert len(result) == 1
    assert isinstance(result[0], CommandOptionSelection)
    assert result[0].label == "Set base vector"


def test_get_point_can_return_command_option_selection() -> None:
    doc = DocumentStore()
    ed = Editor(document=doc)
    ed.set_command_options(["Enter factor"])

    result: list[Vec2 | CommandOptionSelection] = []

    def _worker() -> None:
        result.append(
            ed.get_point(
                "Scale: specify reference vector or choose option",
                allow_command_options=True,
            )
        )

    t = threading.Thread(target=_worker, daemon=True)
    ed._thread = t
    t.start()

    assert _wait_until(lambda: ed.input_mode == "point")
    ed.provide_command_option("enter factor")
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert len(result) == 1
    assert isinstance(result[0], CommandOptionSelection)
    assert result[0].label == "Enter factor"


def test_editor_preview_scope_clears_callback_on_exit() -> None:
    ed = Editor(document=DocumentStore())
    preview_ent = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))

    with ed.preview(lambda _mouse: [preview_ent]):
        assert ed.get_dynamic(Vec2(0, 0)) == [preview_ent]

    assert ed.get_dynamic(Vec2(0, 0)) == []


def test_editor_highlight_scope_clears_on_exit() -> None:
    ed = Editor(document=DocumentStore())
    highlighted = LineEntity(p1=Vec2(0, 0), p2=Vec2(2, 0))

    with ed.highlighted([highlighted]):
        assert ed.get_highlight() == [highlighted]

    assert ed.get_highlight() == []


def test_editor_transaction_groups_undo_commands() -> None:
    ed = Editor(document=DocumentStore())
    events: list[str] = []

    class _Marker(UndoCommand):
        def __init__(self, label: str) -> None:
            self.description = label

        def redo(self) -> None:
            events.append(f"redo:{self.description}")

        def undo(self) -> None:
            events.append(f"undo:{self.description}")

    with ed.transaction("Batch edit") as tx:
        tx.add_undo(_Marker("first"))
        tx.add_undo(_Marker("second"))

    # Push-only semantics should not replay redo.
    assert events == []
    assert ed.undo_stack.undo_text == "Batch edit"

    assert ed.undo()
    assert events == ["undo:second", "undo:first"]

    assert ed.redo()
    assert events == ["undo:second", "undo:first", "redo:first", "redo:second"]


def test_move_command_second_pick_uses_base_point_as_vector_origin() -> None:
    import app.commands  # noqa: F401

    doc = DocumentStore()
    ed = Editor(document=doc)
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(2, 0))
    doc.add_entity(line)
    ed.selection.add(line.id)

    ed.run_command("moveCommand")
    assert _wait_until(lambda: ed.is_running and ed.input_mode == "point")

    base = Vec2(1, 1)
    ed.provide_point(base)
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and ed.snap_from_point == base
    )

    ed.provide_point(Vec2(4, 2))
    assert _wait_until(lambda: not ed.is_running)

    assert line.p1 == Vec2(3, 1)
    assert line.p2 == Vec2(5, 1)


def test_copy_command_keeps_base_point_as_vector_origin_between_placements() -> None:
    import app.commands  # noqa: F401

    doc = DocumentStore()
    ed = Editor(document=doc)
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    doc.add_entity(line)
    ed.selection.add(line.id)

    ed.run_command("copyCommand")
    assert _wait_until(lambda: ed.is_running and ed.input_mode == "point")

    base = Vec2(2, 2)
    ed.provide_point(base)
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and ed.snap_from_point == base
    )

    ed.provide_point(Vec2(5, 2))
    assert _wait_until(lambda: len(doc.entities) == 2)
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and ed.snap_from_point == base
    )

    copies = [ent for ent in doc.entities if ent.id != line.id]
    assert len(copies) == 1
    copy_line = copies[0]
    assert isinstance(copy_line, LineEntity)
    assert copy_line.p1 == Vec2(3, 0)
    assert copy_line.p2 == Vec2(4, 0)

    ed.cancel()
    assert _wait_until(lambda: not ed.is_running)
    assert ed.snap_from_point is None


def test_rotate_command_uses_vector_point_input_for_angle() -> None:
    import app.commands  # noqa: F401

    doc = DocumentStore()
    ed = Editor(document=doc)
    line = LineEntity(p1=Vec2(1, 0), p2=Vec2(2, 0))
    doc.add_entity(line)
    ed.selection.add(line.id)

    ed.run_command("rotateCommand")
    assert _wait_until(lambda: ed.is_running and ed.input_mode == "point")

    center = Vec2(0, 0)
    ed.provide_point(center)
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and ed.snap_from_point == center
    )

    ed.provide_point(Vec2(0, 10))
    assert _wait_until(lambda: not ed.is_running)

    assert line.p1.x == pytest.approx(0.0, abs=1e-6)
    assert line.p1.y == pytest.approx(1.0, abs=1e-6)
    assert line.p2.x == pytest.approx(0.0, abs=1e-6)
    assert line.p2.y == pytest.approx(2.0, abs=1e-6)


def test_rotate_base_vector_redefines_zero_axis_for_vector_pick() -> None:
    import app.commands  # noqa: F401

    doc = DocumentStore()
    ed = Editor(document=doc)
    line = LineEntity(p1=Vec2(1, 0), p2=Vec2(2, 0))
    doc.add_entity(line)
    ed.selection.add(line.id)

    ed.run_command("rotateCommand")
    assert _wait_until(lambda: ed.is_running and ed.input_mode == "point")

    center = Vec2(0, 0)
    ed.provide_point(center)
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and ed.snap_from_point == center
    )
    assert _wait_until(lambda: "Set base vector" in ed.command_option_labels)

    # Set base vector to straight up; this should become the effective 0 axis.
    ed.provide_command_option("Set base vector")
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and not ed.command_option_labels
    )
    base_start = Vec2(10, 10)
    base_end = Vec2(10, 20)
    ed.provide_point(base_start)
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and ed.snap_from_point == base_start
    )
    ed.provide_point(base_end)

    # Pick the same (straight up) vector as rotation vector => zero rotation.
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point"
        and ed.snap_from_point == center
        and "Set base vector" in ed.command_option_labels
    )
    ed.provide_point(Vec2(0, 10))
    assert _wait_until(lambda: not ed.is_running)

    assert line.p1.x == pytest.approx(1.0, abs=1e-6)
    assert line.p1.y == pytest.approx(0.0, abs=1e-6)
    assert line.p2.x == pytest.approx(2.0, abs=1e-6)
    assert line.p2.y == pytest.approx(0.0, abs=1e-6)


def test_scale_command_uses_vector_point_input_for_factor() -> None:
    import app.commands  # noqa: F401

    doc = DocumentStore()
    ed = Editor(document=doc)
    line = LineEntity(p1=Vec2(10, 0), p2=Vec2(20, 0))
    doc.add_entity(line)
    ed.selection.add(line.id)

    ed.run_command("scaleCommand")
    assert _wait_until(lambda: ed.is_running and ed.input_mode == "point")

    base = Vec2(0, 0)
    ed.provide_point(base)
    assert _wait_until(
        lambda: ed.is_running and ed.input_mode == "point" and ed.snap_from_point == base
    )

    ed.provide_point(Vec2(200, 0))
    assert _wait_until(lambda: not ed.is_running)

    assert line.p1 == Vec2(20, 0)
    assert line.p2 == Vec2(40, 0)
