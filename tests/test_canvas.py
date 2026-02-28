"""Tests for CADCanvas coordinate transforms and origin anchoring.

These tests use pytest-qt to create a real QApplication, which is required
by PySide6 widget constructors.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from app.canvas import CADCanvas
from app.document import DocumentStore


@pytest.fixture
def canvas(qtbot):
    """Create a canvas widget backed by an empty document."""
    doc = DocumentStore()
    c = CADCanvas(document=doc)
    c.resize(800, 600)
    qtbot.addWidget(c)
    return c


class TestCoordinateTransforms:
    """Verify screen↔world round-trip at default settings."""

    def test_world_to_screen_roundtrip(self, canvas):
        world = QPointF(50, 30)
        screen = canvas.world_to_screen(world)
        back = canvas.screen_to_world(screen)
        assert back.x() == pytest.approx(world.x(), abs=1e-6)
        assert back.y() == pytest.approx(world.y(), abs=1e-6)

    def test_screen_to_world_roundtrip(self, canvas):
        screen = QPointF(200, 150)
        world = canvas.screen_to_world(screen)
        back = canvas.world_to_screen(world)
        assert back.x() == pytest.approx(screen.x(), abs=1e-6)
        assert back.y() == pytest.approx(screen.y(), abs=1e-6)

    def test_origin_maps_to_offset(self, canvas):
        """World origin should map to the inset position, not (0,0)."""
        sp = canvas.world_to_screen(QPointF(0, 0))
        # With bottom-left anchor and 10px inset, origin screen pos should be
        # near (10, height - 10)
        assert sp.x() == pytest.approx(10.0, abs=1.0)
        assert sp.y() == pytest.approx(canvas.height() - 10.0, abs=1.0)


class TestOriginAnchoring:
    def test_set_origin_bottom_left(self, canvas):
        canvas.set_origin_anchor("bottom-left", inset_x_px=20, inset_y_px=30)
        sp = canvas.world_to_screen(QPointF(0, 0))
        assert sp.x() == pytest.approx(20.0, abs=1.0)
        assert sp.y() == pytest.approx(canvas.height() - 30.0, abs=1.0)

    def test_set_origin_top_left(self, canvas):
        canvas.set_origin_anchor("top-left", inset_x_px=15, inset_y_px=15)
        sp = canvas.world_to_screen(QPointF(0, 0))
        assert sp.x() == pytest.approx(15.0, abs=1.0)
        assert sp.y() == pytest.approx(15.0, abs=1.0)

    def test_invalid_anchor_raises(self, canvas):
        with pytest.raises(ValueError):
            canvas.set_origin_anchor("center")

    def test_resize_preserves_anchor(self, canvas):
        canvas.set_origin_anchor("bottom-left", inset_x_px=10, inset_y_px=10)
        canvas.setFixedSize(1024, 768)
        # _update_offset_for_origin is called by resizeEvent, but
        # setFixedSize may not fire events in test; call manually.
        canvas._update_offset_for_origin()
        sp = canvas.world_to_screen(QPointF(0, 0))
        assert sp.x() == pytest.approx(10.0, abs=1.0)
        assert sp.y() == pytest.approx(canvas.height() - 10.0, abs=1.0)

    def test_positive_y_goes_up(self, canvas):
        """World +Y should map to a lower screen Y (upward on screen)."""
        canvas.set_origin_anchor("bottom-left", inset_x_px=0, inset_y_px=0)
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s1 = canvas.world_to_screen(QPointF(0, 10))
        assert s1.y() < s0.y()

    def test_positive_x_goes_right(self, canvas):
        """World +X should map to higher screen X."""
        canvas.set_origin_anchor("bottom-left", inset_x_px=0, inset_y_px=0)
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s1 = canvas.world_to_screen(QPointF(10, 0))
        assert s1.x() > s0.x()


class TestScaling:
    def test_zoom_in(self, canvas):
        """Doubling scale should double screen distances."""
        canvas.scale = 1.0
        canvas._update_offset_for_origin()
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s10 = canvas.world_to_screen(QPointF(10, 0))
        delta1 = s10.x() - s0.x()

        canvas.scale = 2.0
        canvas._update_offset_for_origin()
        s0 = canvas.world_to_screen(QPointF(0, 0))
        s10 = canvas.world_to_screen(QPointF(10, 0))
        delta2 = s10.x() - s0.x()

        assert delta2 == pytest.approx(delta1 * 2, abs=1.0)
