"""Draw circle command — collects centre point and a point on the radius."""
import math

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import CircleEntity, LineEntity, Vec2


@command("circleCommand")
class DrawCircleCommand(CommandBase):
    """Draw a circle by picking a centre and a circumference point."""

    def execute(self) -> None:
        center = self.editor.get_point("Circle: pick centre point")

        def _preview(m: Vec2):
            r = math.hypot(m.x - center.x, m.y - center.y) or 1e-6
            return [
                CircleEntity(center=center, radius=r),
                LineEntity(p1=center, p2=m),
            ]

        self.editor.set_dynamic(_preview)
        edge = self.editor.get_point("Circle: pick point on circumference")
        self.editor.clear_dynamic()
        radius = math.hypot(edge.x - center.x, edge.y - center.y)
        self.editor.add_entity(CircleEntity(center=center, radius=radius))
