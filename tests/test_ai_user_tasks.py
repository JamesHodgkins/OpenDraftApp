"""Tests for ai_user.tasks.basic_shapes verifiers — pure DocumentStore
inspection, no GUI/Qt involved."""
from __future__ import annotations

from app.document import DocumentStore
from app.entities import CircleEntity, LineEntity, RectangleEntity, Vec2

from ai_user.tasks.basic_shapes import ALL_TASKS, TASKS_BY_ID


def test_all_tasks_have_unique_ids() -> None:
    ids = [t.task_id for t in ALL_TASKS]
    assert len(ids) == len(set(ids))


def test_draw_a_line_verify_false_on_empty_document() -> None:
    task = TASKS_BY_ID["draw_a_line"]
    assert task.verify(DocumentStore()) is False


def test_draw_a_line_verify_true_once_any_line_exists() -> None:
    task = TASKS_BY_ID["draw_a_line"]
    doc = DocumentStore()
    doc.add_entity(LineEntity(p1=Vec2(0, 0), p2=Vec2(5, 5)))
    assert task.verify(doc) is True


def test_draw_circle_radius_5_requires_matching_radius() -> None:
    task = TASKS_BY_ID["draw_circle_radius_5"]
    doc = DocumentStore()
    doc.add_entity(CircleEntity(center=Vec2(0, 0), radius=1.0))
    assert task.verify(doc) is False

    doc.add_entity(CircleEntity(center=Vec2(10, 10), radius=5.0))
    assert task.verify(doc) is True


def test_draw_circle_radius_5_within_tolerance() -> None:
    task = TASKS_BY_ID["draw_circle_radius_5"]
    doc = DocumentStore()
    doc.add_entity(CircleEntity(center=Vec2(0, 0), radius=5.3))
    assert task.verify(doc) is True


def test_draw_rectangle_matches_either_orientation() -> None:
    task = TASKS_BY_ID["draw_rectangle_100x50"]

    doc_wh = DocumentStore()
    doc_wh.add_entity(RectangleEntity(center=Vec2(0, 0), width=100.0, height=50.0))
    assert task.verify(doc_wh) is True

    doc_hw = DocumentStore()
    doc_hw.add_entity(RectangleEntity(center=Vec2(0, 0), width=50.0, height=100.0))
    assert task.verify(doc_hw) is True


def test_draw_rectangle_wrong_dimensions_fails() -> None:
    task = TASKS_BY_ID["draw_rectangle_100x50"]
    doc = DocumentStore()
    doc.add_entity(RectangleEntity(center=Vec2(0, 0), width=10.0, height=10.0))
    assert task.verify(doc) is False
