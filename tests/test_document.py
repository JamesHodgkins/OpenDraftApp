"""Tests for DocumentStore — CRUD, layers, serialisation and change notification."""
from __future__ import annotations

import json
import pytest
import zipfile
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

    def test_generation_increments_on_mutation(self):
        doc = DocumentStore()
        start = doc.generation
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        assert doc.generation > start

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

    def test_replace_with_replaces_entities_and_index(self):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))

        loaded = DocumentStore()
        loaded.add_entity(CircleEntity(center=Vec2(10, 10), radius=3))
        loaded.add_layer(Layer(name="dims"))
        loaded.active_layer = "dims"
        loaded.active_color = "#ff00ff"

        doc.replace_with(loaded)

        assert len(doc) == 1
        assert doc.entities[0].type == "circle"
        assert doc.active_layer == "dims"
        assert doc.active_color == "#ff00ff"
        assert doc.get_entity(doc.entities[0].id) is doc.entities[0]

    def test_reset_to_default_clears_document_state(self):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 1)))
        doc.add_layer(Layer(name="tmp"))
        doc.active_layer = "tmp"
        doc.active_color = "#ff0000"
        doc.active_line_style = "dashed"
        doc.active_thickness = 2.0

        doc.reset_to_default()

        assert len(doc) == 0
        assert len(doc.layers) == 1
        assert doc.layers[0].name == "default"
        assert doc.active_layer == "default"
        assert doc.active_color is None
        assert doc.active_line_style is None
        assert doc.active_thickness is None


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
        doc.add_entity(RectangleEntity.from_corners(Vec2(0, 0), Vec2(5, 5)))

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

    def test_odx_file_roundtrip(self, tmp_path):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(1, 2), p2=Vec2(3, 4)))
        doc.add_entity(RectangleEntity.from_corners(Vec2(0, 0), Vec2(5, 5)))

        filepath = tmp_path / "test_drawing.odx"
        doc.save_odx(filepath)

        loaded = DocumentStore.load_odx(filepath)
        assert len(loaded) == 2
        types = {e.type for e in loaded}
        assert "line" in types
        assert "rect" in types

    def test_odx_container_contains_document_json(self, tmp_path):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(1, 2), p2=Vec2(3, 4)))
        filepath = tmp_path / "container_check.odx"
        doc.save_odx(filepath)

        with zipfile.ZipFile(filepath, "r") as zf:
            assert "document.json" in zf.namelist()
            raw = json.loads(zf.read("document.json").decode("utf-8"))
        assert raw["version"] == "1.0"
        assert raw["entities"][0]["type"] == "line"

    def test_odx_container_can_include_thumbnail_png(self, tmp_path):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(1, 2), p2=Vec2(3, 4)))
        filepath = tmp_path / "container_thumb.odx"
        thumb = b"fake-png-data"
        doc.save_odx(filepath, thumbnail_png=thumb)

        with zipfile.ZipFile(filepath, "r") as zf:
            assert "assets/thumbnail.png" in zf.namelist()
            assert zf.read("assets/thumbnail.png") == thumb

        assert DocumentStore.load_thumbnail_png(filepath) == thumb

    def test_load_odx_missing_document_json(self, tmp_path):
        filepath = tmp_path / "missing_payload.odx"
        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", "{}")

        with pytest.raises(ValueError, match="missing_document_json"):
            DocumentStore.load_odx(filepath)

    def test_load_odx_invalid_zip(self, tmp_path):
        filepath = tmp_path / "invalid_zip.odx"
        filepath.write_text("not a zip archive", encoding="utf-8")

        with pytest.raises(ValueError, match="invalid_zip"):
            DocumentStore.load_odx(filepath)

    def test_load_odx_invalid_document_json(self, tmp_path):
        filepath = tmp_path / "invalid_document_json.odx"
        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("document.json", "{not-valid-json")

        with pytest.raises(ValueError, match="invalid_document_json"):
            DocumentStore.load_odx(filepath)

    def test_save_and_load_extension_dispatch(self, tmp_path):
        doc = DocumentStore()
        doc.add_entity(LineEntity(p1=Vec2(1, 1), p2=Vec2(2, 2)))

        odx_path = tmp_path / "auto_native.odx"
        json_path = tmp_path / "auto_debug.json"

        doc.save(odx_path)
        doc.save(json_path)

        loaded_odx = DocumentStore.load(odx_path)
        loaded_json = DocumentStore.load(json_path)
        assert len(loaded_odx) == 1
        assert len(loaded_json) == 1

    def test_odx_is_smaller_than_pretty_json_for_same_doc(self, tmp_path):
        doc = DocumentStore()
        for i in range(60):
            doc.add_entity(LineEntity(p1=Vec2(float(i), 0.0), p2=Vec2(float(i), 100.0)))

        odx_path = tmp_path / "size_compare.odx"
        json_path = tmp_path / "size_compare.json"
        doc.save_odx(odx_path)
        doc.save_json(json_path, indent=2)

        assert odx_path.stat().st_size < json_path.stat().st_size

    def test_entity_from_dict_fallback(self):
        """Unknown entity type falls back to BaseEntity."""
        from app.entities import entity_from_dict
        e = entity_from_dict({"type": "unknown_future_thing", "id": "x"})
        assert e.type == ""  # BaseEntity default
