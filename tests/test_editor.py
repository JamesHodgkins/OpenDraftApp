"""Tests for editor selection deletion helpers."""
from __future__ import annotations

import pytest

from app.editor.editor import Editor
from app.document import DocumentStore
from app.entities import Vec2, LineEntity


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
