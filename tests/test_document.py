"""Tests for DocumentStore — CRUD, layers, serialisation and change notification."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from app.entities.base import Vec2
from app.entities.line import LineEntity
from app.entities.circle import CircleEntity
from app.entities.rectangle import RectangleEntity
from app.document import DocumentStore, Layer


# ===================================================================
# Entity CRUD
# ===================================================================

class TestEntityCRUD:
    def test_add_entity(self):
        doc = DocumentStore()
        line = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1))
        returned = doc.add_entity(line)
        assert returned is line
        assert len(doc) == 1

    def test_remove_entity(self):
        doc = DocumentStore()
        line = doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        removed = doc.remove_entity(line.id)
        assert removed is line
        assert len(doc) == 0

    def test_remove_nonexistent(self):
        doc = DocumentStore()
        assert doc.remove_entity("no-such-id") is None

    def test_get_entity(self):
        doc = DocumentStore()
        line = doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(5, 5)))
        assert doc.get_entity(line.id) is line
        assert doc.get_entity("bogus") is None

    def test_clear(self):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        doc.add_entity(CircleEntity(center=Vec2(0, 0), radius=5))
        doc.clear()
        assert len(doc) == 0

    def test_entities_on_layer(self):
        doc = DocumentStore()
        l1 = doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1), layer="A"))
        l2 = doc.add_entity(LineEntity(p1=Vec2(2, 2), p2=Vec2(3, 3), layer="B"))
        found = list(doc.entities_on_layer("A"))
        assert l1 in found
        assert l2 not in found

    def test_iteration(self):
        doc = DocumentStore()
        e1 = doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        e2 = doc.add_entity(CircleEntity(center=Vec2(5, 5), radius=1))
        assert list(doc) == [e1, e2]


# ===================================================================
# Layers
# ===================================================================

class TestLayers:
    def test_default_layer_exists(self):
        doc = DocumentStore()
        assert doc.get_layer("default") is not None

    def test_add_layer(self):
        doc = DocumentStore()
        lyr = doc.add_layer(Layer(name="electrical", color="#ff0000"))
        assert doc.get_layer("electrical") is lyr

    def test_add_duplicate_noop(self):
        doc = DocumentStore()
        doc.add_layer(Layer(name="mechanical"))
        doc.add_layer(Layer(name="mechanical"))
        assert sum(1 for l in doc.layers if l.name == "mechanical") == 1

    def test_remove_layer(self):
        doc = DocumentStore()
        doc.add_layer(Layer(name="temp"))
        removed = doc.remove_layer("temp")
        assert removed is not None
        assert doc.get_layer("temp") is None

    def test_remove_default_blocked(self):
        doc = DocumentStore()
        assert doc.remove_layer("default") is None
        assert doc.get_layer("default") is not None

    def test_layer_roundtrip(self):
        lyr = Layer(name="dims", color="#00ff00", visible=False,
                    line_style="dashed", thickness=2.5)
        d = lyr.to_dict()
        restored = Layer.from_dict(d)
        assert restored.name == lyr.name
        assert restored.color == lyr.color
        assert restored.visible == lyr.visible
        assert restored.line_style == lyr.line_style
        assert restored.thickness == lyr.thickness


# ===================================================================
# Change notification (Qt signal)
# ===================================================================

class TestChangeNotification:
    def test_signal_emitted_on_add(self):
        doc = DocumentStore()
        calls = []
        doc.add_change_listener(lambda: calls.append("changed"))
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        assert len(calls) == 1

    def test_signal_emitted_on_remove(self):
        doc = DocumentStore()
        line = doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        calls = []
        doc.add_change_listener(lambda: calls.append("changed"))
        doc.remove_entity(line.id)
        assert len(calls) == 1

    def test_signal_emitted_on_clear(self):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        calls = []
        doc.add_change_listener(lambda: calls.append("changed"))
        doc.clear()
        assert len(calls) == 1

    def test_remove_listener(self):
        doc = DocumentStore()
        calls = []
        fn = lambda: calls.append("changed")
        doc.add_change_listener(fn)
        doc.remove_change_listener(fn)
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        assert len(calls) == 0

    def test_remove_unregistered_listener_noop(self):
        doc = DocumentStore()
        doc.remove_change_listener(lambda: None)  # should not raise


# ===================================================================
# Serialisation
# ===================================================================

class TestSerialisation:
    def test_dict_roundtrip(self):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(10, 0)))
        doc.add_entity(CircleEntity(center=Vec2(5, 5), radius=3))
        doc.add_layer(Layer(name="extra", color="#abcdef"))
        doc.active_layer = "extra"

        d = doc.to_dict()
        restored = DocumentStore.from_dict(d)
        assert len(restored) == 2
        assert restored.active_layer == "extra"
        assert restored.get_layer("extra") is not None

    def test_json_file_roundtrip(self, tmp_path):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(1, 2), p2=Vec2(3, 4)))
        doc.add_entity(RectangleEntity(p1=Vec2(0, 0), p2=Vec2(5, 5)))

        filepath = tmp_path / "test_drawing.json"
        doc.save_json(filepath)

        loaded = DocumentStore.load_json(filepath)
        assert len(loaded) == 2
        # Verify entity types survived the round-trip
        types = {e.type for e in loaded}
        assert "line" in types
        assert "rect" in types

    def test_json_file_content(self, tmp_path):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(1, 2), p2=Vec2(3, 4)))
        filepath = tmp_path / "content_check.json"
        doc.save_json(filepath)

        raw = json.loads(filepath.read_text())
        assert raw["version"] == "1.0"
        assert len(raw["entities"]) == 1
        assert raw["entities"][0]["type"] == "line"

    def test_entity_from_dict_fallback(self):
        """Unknown entity type falls back to BaseEntity."""
        from app.entities import entity_from_dict
        e = entity_from_dict({"type": "unknown_future_thing", "id": "x"})
        assert e.type == ""  # BaseEntity default
