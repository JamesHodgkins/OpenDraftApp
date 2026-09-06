"""Draw circle command — stateful center + radius workflow."""
import math

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import CircleEntity, LineEntity, Vec2


@command("circleCommand", aliases=("c",))
class DrawCircleCommand(StatefulCommandBase):
    """Draw a circle by setting center point and radius length."""

    center = export(None, label="Center", input_kind="point")
    radius = export(None, label="Radius", input_kind="length")

    def start(self) -> None:
        self.begin(active_export="center", reset=("center", "radius"))

    def live_preview_value(self, name, cursor):
        if name == "radius":
            center = self.point_value("center")
            if center is None:
                return None
            return math.hypot(cursor.x - center.x, cursor.y - center.y)
        return super().live_preview_value(name, cursor)

    def update(self) -> None:
        center = self.point_value("center")
        radius_len = self.number_value("radius")

        self.set_snap_for_active(
            {"radius": center},
            default=center,
        )

        if center is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            if radius_len is not None:
                r = max(1e-6, radius_len)
                edge_pt = Vec2(center.x + r, center.y)
            else:
                r = max(1e-6, math.hypot(mouse.x - center.x, mouse.y - center.y))
                edge_pt = mouse
            return [
                CircleEntity(center=center, radius=r),
                LineEntity(p1=center, p2=edge_pt),
            ]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        center = self.point_value("center")
        radius_len = self.number_value("radius")
        if center is None or radius_len is None:
            self.editor.status_message.emit("Circle: center and radius are required")
            return
        self.editor.add_entity(CircleEntity(center=center, radius=max(1e-6, radius_len)))
        self.editor.snap_from_point = center
