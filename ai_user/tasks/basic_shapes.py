"""A small starter set of drawing tasks, ordered roughly by difficulty."""
from __future__ import annotations

import math

from app.document import DocumentStore
from app.entities import CircleEntity, LineEntity, RectangleEntity

from ai_user.tasks import Task


def _draw_line_task() -> Task:
    def verify(doc: DocumentStore) -> bool:
        return any(isinstance(e, LineEntity) for e in doc.entities)

    return Task(
        task_id="draw_a_line",
        prompt="Draw a single straight line anywhere on the canvas.",
        verify=verify,
        max_steps=15,
    )


def _draw_circle_with_radius_task(radius: float = 5.0, tol: float = 0.5) -> Task:
    def verify(doc: DocumentStore) -> bool:
        return any(
            isinstance(e, CircleEntity) and math.isclose(e.radius, radius, abs_tol=tol)
            for e in doc.entities
        )

    return Task(
        task_id="draw_circle_radius_5",
        prompt=(
            f"Draw a circle with a radius of exactly {radius} drawing units. "
            "Use the command bar and type the radius value precisely rather "
            "than eyeballing it with the mouse."
        ),
        verify=verify,
        max_steps=20,
    )


def _draw_rectangle_task(width: float = 100.0, height: float = 50.0, tol: float = 1.0) -> Task:
    def verify(doc: DocumentStore) -> bool:
        for e in doc.entities:
            if not isinstance(e, RectangleEntity):
                continue
            w, h = e.width, e.height
            if (math.isclose(w, width, abs_tol=tol) and math.isclose(h, height, abs_tol=tol)) or (
                math.isclose(w, height, abs_tol=tol) and math.isclose(h, width, abs_tol=tol)
            ):
                return True
        return False

    return Task(
        task_id="draw_rectangle_100x50",
        prompt=(
            f"Draw a rectangle exactly {int(width)} units wide by {int(height)} "
            "units tall. Type the exact dimensions rather than dragging freehand."
        ),
        verify=verify,
        max_steps=20,
    )


ALL_TASKS = [
    _draw_line_task(),
    _draw_circle_with_radius_task(),
    _draw_rectangle_task(),
]

TASKS_BY_ID = {t.task_id: t for t in ALL_TASKS}
