"""Draw circle command — stateful center + radius-vector workflow."""
import math

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import CircleEntity, LineEntity, Vec2


@command("circleCommand", aliases=("c",))
class DrawCircleCommand(StatefulCommandBase):
    """Draw a circle by setting center point and radius vector."""

    center = export(None, label="Center", input_kind="point")
    radius = export(None, label="Radius", input_kind="vector")

    def start(self) -> None:
        self.begin(active_export="center", reset=("center", "radius"))

    def update(self) -> None:
        center = self.point_value("center")
        radius_vec = self.vector_value("radius")
        edge = center + radius_vec if center is not None and radius_vec is not None else None

        self.set_snap_for_active(
            {
                "radius": center,
                "center": edge,
            },
            default=(center, edge),
        )

        if center is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            edge_pt = edge if edge is not None else mouse
            radius = max(1e-6, math.hypot(edge_pt.x - center.x, edge_pt.y - center.y))
            return [
                CircleEntity(center=center, radius=radius),
                LineEntity(p1=center, p2=edge_pt),
            ]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        center = self.point_value("center")
        radius_vec = self.vector_value("radius")
        if center is None or radius_vec is None:
            self.editor.status_message.emit("Circle: center and radius are required")
            return
        edge = center + radius_vec
        radius = math.hypot(radius_vec.x, radius_vec.y)
        self.editor.add_entity(CircleEntity(center=center, radius=max(1e-6, radius)))
        self.editor.snap_from_point = edge
