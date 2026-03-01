"""Tests for the undo / redo system."""
from __future__ import annotations

import pytest

from app.document import DocumentStore, Layer
from app.editor.editor import Editor
from app.editor.undo import (
    AddEntityUndoCommand,
    AddLayerUndoCommand,
    RemoveEntitiesUndoCommand,
    RemoveLayerUndoCommand,
    RenameLayerUndoCommand,
    SetActiveLayerUndoCommand,
    SetEntityPropertiesUndoCommand,
    SetLayerPropertyUndoCommand,
    UndoCommand,
    UndoStack,
)
from app.entities import LineEntity, Vec2


# ---------------------------------------------------------------------------
# UndoStack unit tests
# ---------------------------------------------------------------------------


class _DummyCmd(UndoCommand):
    """Trivial undoable command that appends to a shared log."""

    def __init__(self, log: list, tag: str) -> None:
        self._log = log
        self._tag = tag
        self.description = tag

    def redo(self) -> None:
        self._log.append(f"redo-{self._tag}")

    def undo(self) -> None:
        self._log.append(f"undo-{self._tag}")


def test_push_and_undo():
    stack = UndoStack()
    log: list[str] = []
    stack.push(_DummyCmd(log, "A"))
    assert stack.can_undo
    assert not stack.can_redo

    stack.undo()
    assert log == ["undo-A"]
    assert not stack.can_undo
    assert stack.can_redo


def test_undo_then_redo():
    stack = UndoStack()
    log: list[str] = []
    stack.push(_DummyCmd(log, "A"))
    stack.undo()
    stack.redo()
    assert log == ["undo-A", "redo-A"]
    assert stack.can_undo
    assert not stack.can_redo


def test_push_clears_redo_tail():
    stack = UndoStack()
    log: list[str] = []
    stack.push(_DummyCmd(log, "A"))
    stack.push(_DummyCmd(log, "B"))
    stack.undo()  # undo B
    # Now push C — B should be gone from the redo tail.
    stack.push(_DummyCmd(log, "C"))
    assert not stack.can_redo
    stack.undo()  # undo C
    stack.undo()  # undo A
    assert not stack.can_undo
    assert log == ["undo-B", "undo-C", "undo-A"]


def test_execute_on_push():
    stack = UndoStack()
    log: list[str] = []
    stack.push(_DummyCmd(log, "X"), execute_on_push=True)
    assert log == ["redo-X"]


def test_clear():
    stack = UndoStack()
    stack.push(_DummyCmd([], "A"))
    stack.clear()
    assert not stack.can_undo
    assert not stack.can_redo
    assert stack.count == 0


def test_undo_text_and_redo_text():
    stack = UndoStack()
    assert stack.undo_text == ""
    assert stack.redo_text == ""
    stack.push(_DummyCmd([], "Draw Line"))
    assert stack.undo_text == "Draw Line"
    stack.undo()
    assert stack.redo_text == "Draw Line"


def test_state_changed_signal():
    stack = UndoStack()
    fired: list[bool] = []
    stack.state_changed.connect(lambda: fired.append(True))
    stack.push(_DummyCmd([], "A"))
    stack.undo()
    stack.redo()
    stack.clear()
    assert len(fired) == 4  # push, undo, redo, clear


def test_limit_enforced():
    stack = UndoStack(limit=3)
    for i in range(5):
        stack.push(_DummyCmd([], str(i)))
    assert stack.count == 3
    # Oldest should be gone; undo 3 times should exhaust.
    assert stack.undo()
    assert stack.undo()
    assert stack.undo()
    assert not stack.can_undo


# ---------------------------------------------------------------------------
# AddEntityUndoCommand
# ---------------------------------------------------------------------------


def test_add_entity_undo_command():
    doc = DocumentStore()
    e = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    cmd = AddEntityUndoCommand(doc, e)

    cmd.redo()
    assert doc.get_entity(e.id) is e

    cmd.undo()
    assert doc.get_entity(e.id) is None

    # redo again
    cmd.redo()
    assert doc.get_entity(e.id) is e


# ---------------------------------------------------------------------------
# RemoveEntitiesUndoCommand
# ---------------------------------------------------------------------------


def test_remove_entities_undo_command():
    doc = DocumentStore()
    e1 = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    e2 = LineEntity(p1=Vec2(2, 0), p2=Vec2(3, 0))
    e3 = LineEntity(p1=Vec2(4, 0), p2=Vec2(5, 0))
    doc.add_entity(e1)
    doc.add_entity(e2)
    doc.add_entity(e3)

    # Remove the middle entity.
    cmd = RemoveEntitiesUndoCommand(doc, [e2], [1])
    cmd.redo()
    assert doc.get_entity(e2.id) is None
    assert len(doc.entities) == 2

    cmd.undo()
    assert doc.get_entity(e2.id) is e2
    # Should be back at index 1.
    assert doc.entities[1] is e2


# ---------------------------------------------------------------------------
# Editor integration
# ---------------------------------------------------------------------------


def test_editor_add_entity_is_undoable():
    doc = DocumentStore()
    ed = Editor(document=doc)

    e = ed.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    assert len(doc.entities) == 1

    ed.undo()
    assert len(doc.entities) == 0

    ed.redo()
    assert len(doc.entities) == 1
    assert doc.entities[0].id == e.id


def test_editor_delete_selection_is_undoable():
    doc = DocumentStore()
    ed = Editor(document=doc)

    e1 = ed.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    e2 = ed.add_entity(LineEntity(p1=Vec2(2, 0), p2=Vec2(3, 0)))
    ed.selection.add(e1.id)
    ed.selection.add(e2.id)

    ed.delete_selection()
    assert len(doc.entities) == 0

    ed.undo()  # undo the delete
    assert len(doc.entities) == 2
    assert doc.get_entity(e1.id) is not None
    assert doc.get_entity(e2.id) is not None


def test_editor_multiple_undo_redo():
    doc = DocumentStore()
    ed = Editor(document=doc)

    e1 = ed.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))
    e2 = ed.add_entity(LineEntity(p1=Vec2(2, 0), p2=Vec2(3, 0)))
    assert len(doc.entities) == 2

    ed.undo()   # undo e2
    assert len(doc.entities) == 1
    ed.undo()   # undo e1
    assert len(doc.entities) == 0

    ed.redo()   # redo e1
    assert len(doc.entities) == 1
    ed.redo()   # redo e2
    assert len(doc.entities) == 2


def test_editor_undo_stack_property():
    ed = Editor()
    assert ed.undo_stack is ed._undo_stack


# ---------------------------------------------------------------------------
# SetEntityPropertiesUndoCommand
# ---------------------------------------------------------------------------


def test_set_entity_properties_undo_command():
    doc = DocumentStore()
    e = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    doc.add_entity(e)
    cmd = SetEntityPropertiesUndoCommand(
        doc, [(e.id, "color", None, "#ff0000")], "Change colour"
    )
    cmd.redo()
    assert e.color == "#ff0000"

    cmd.undo()
    assert e.color is None


def test_set_entity_properties_multiple_attrs():
    doc = DocumentStore()
    e1 = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    e2 = LineEntity(p1=Vec2(2, 0), p2=Vec2(3, 0))
    doc.add_entity(e1)
    doc.add_entity(e2)

    cmd = SetEntityPropertiesUndoCommand(
        doc,
        [
            (e1.id, "line_style", None, "dashed"),
            (e2.id, "line_style", None, "dashed"),
        ],
        "Change line style",
    )
    cmd.redo()
    assert e1.line_style == "dashed"
    assert e2.line_style == "dashed"

    cmd.undo()
    assert e1.line_style is None
    assert e2.line_style is None


# ---------------------------------------------------------------------------
# SetLayerPropertyUndoCommand
# ---------------------------------------------------------------------------


def test_set_layer_property_undo_command():
    doc = DocumentStore()
    layer = doc.get_layer("default")
    assert layer is not None
    old_color = layer.color

    cmd = SetLayerPropertyUndoCommand(
        doc, "default", "color", old_color, "#00ff00",
        description="Layer colour",
    )
    cmd.redo()
    assert layer.color == "#00ff00"

    cmd.undo()
    assert layer.color == old_color


def test_set_layer_visibility_undo():
    doc = DocumentStore()
    layer = doc.get_layer("default")

    cmd = SetLayerPropertyUndoCommand(
        doc, "default", "visible", True, False,
        description="Layer visibility",
    )
    cmd.redo()
    assert layer.visible is False

    cmd.undo()
    assert layer.visible is True


# ---------------------------------------------------------------------------
# RenameLayerUndoCommand
# ---------------------------------------------------------------------------


def test_rename_layer_undo_command():
    doc = DocumentStore()
    doc.add_layer(Layer(name="walls"))
    doc.active_layer = "walls"

    cmd = RenameLayerUndoCommand(doc, "walls", "exterior")
    cmd.redo()
    assert doc.get_layer("walls") is None
    assert doc.get_layer("exterior") is not None
    assert doc.active_layer == "exterior"

    cmd.undo()
    assert doc.get_layer("exterior") is None
    assert doc.get_layer("walls") is not None
    assert doc.active_layer == "walls"


# ---------------------------------------------------------------------------
# AddLayerUndoCommand
# ---------------------------------------------------------------------------


def test_add_layer_undo_command():
    doc = DocumentStore()
    layer = Layer(name="annotations")
    cmd = AddLayerUndoCommand(doc, layer)

    cmd.redo()
    assert doc.get_layer("annotations") is not None

    cmd.undo()
    assert doc.get_layer("annotations") is None


# ---------------------------------------------------------------------------
# RemoveLayerUndoCommand
# ---------------------------------------------------------------------------


def test_remove_layer_undo_command():
    doc = DocumentStore()
    layer = Layer(name="temp")
    doc.add_layer(layer)
    e = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0), layer="temp")
    doc.add_entity(e)
    doc.active_layer = "temp"

    cmd = RemoveLayerUndoCommand(
        doc, layer, index=1,
        reassigned_entities=[(e.id, "temp")],
        was_active=True,
    )
    cmd.redo()
    assert doc.get_layer("temp") is None
    assert e.layer == "default"
    assert doc.active_layer == "default"

    cmd.undo()
    assert doc.get_layer("temp") is not None
    assert e.layer == "temp"
    assert doc.active_layer == "temp"


# ---------------------------------------------------------------------------
# SetActiveLayerUndoCommand
# ---------------------------------------------------------------------------


def test_set_active_layer_undo_command():
    doc = DocumentStore()
    doc.add_layer(Layer(name="L2"))

    cmd = SetActiveLayerUndoCommand(doc, "default", "L2")
    cmd.redo()
    assert doc.active_layer == "L2"

    cmd.undo()
    assert doc.active_layer == "default"


# ---------------------------------------------------------------------------
# Editor helper methods
# ---------------------------------------------------------------------------


def test_editor_set_entity_properties():
    doc = DocumentStore()
    ed = Editor(document=doc)
    e = ed.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0)))

    ed.set_entity_properties([e.id], "color", "#ff0000", description="Set red")
    assert e.color == "#ff0000"

    ed.undo()
    assert e.color is None

    ed.redo()
    assert e.color == "#ff0000"


def test_editor_set_layer_property():
    doc = DocumentStore()
    ed = Editor(document=doc)

    ed.set_layer_property("default", "visible", False, description="Hide default")
    layer = doc.get_layer("default")
    assert layer.visible is False

    ed.undo()
    assert layer.visible is True


def test_editor_rename_layer():
    doc = DocumentStore()
    ed = Editor(document=doc)
    doc.add_layer(Layer(name="walls"))
    doc.active_layer = "walls"

    ed.rename_layer("walls", "ext_walls")
    assert doc.get_layer("ext_walls") is not None
    assert doc.active_layer == "ext_walls"

    ed.undo()
    assert doc.get_layer("walls") is not None
    assert doc.active_layer == "walls"


def test_editor_add_layer():
    doc = DocumentStore()
    ed = Editor(document=doc)

    lyr = Layer(name="new_layer")
    ed.add_layer(lyr)
    assert doc.get_layer("new_layer") is not None

    ed.undo()
    assert doc.get_layer("new_layer") is None

    ed.redo()
    assert doc.get_layer("new_layer") is not None


def test_editor_remove_layer_undoable():
    doc = DocumentStore()
    ed = Editor(document=doc)

    lyr = Layer(name="temp")
    doc.add_layer(lyr)
    e = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0), layer="temp")
    doc.add_entity(e)
    doc.active_layer = "temp"

    ok = ed.remove_layer_undoable("temp")
    assert ok
    assert doc.get_layer("temp") is None
    assert e.layer == "default"
    assert doc.active_layer == "default"

    ed.undo()
    assert doc.get_layer("temp") is not None
    assert e.layer == "temp"
    assert doc.active_layer == "temp"


def test_editor_set_active_layer():
    doc = DocumentStore()
    ed = Editor(document=doc)
    doc.add_layer(Layer(name="L2"))

    ed.set_active_layer("L2")
    assert doc.active_layer == "L2"

    ed.undo()
    assert doc.active_layer == "default"

    ed.redo()
    assert doc.active_layer == "L2"


def test_editor_remove_layer_default_blocked():
    doc = DocumentStore()
    ed = Editor(document=doc)

    ok = ed.remove_layer_undoable("default")
    assert not ok
    assert doc.get_layer("default") is not None
