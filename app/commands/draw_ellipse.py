"""Draw ellipse command — pick centre, then major-axis endpoint, then minor radius."""
import math

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import LineEntity, Vec2
from app.entities.ellipse import EllipseEntity


@command("ellipseCommand")
class DrawEllipseCommand(CommandBase):
    """Draw an ellipse: pick centre, major-axis point, then minor-axis distance."""

    def execute(self) -> None:
        center = self.editor.get_point("Ellipse: pick centre")
        self.editor.snap_from_point = center

        def _preview_major(m: Vec2) -> list:
            return [LineEntity(p1=center, p2=m)]

        self.editor.set_dynamic(_preview_major)
        major_pt = self.editor.get_point("Ellipse: pick major-axis endpoint")
        self.editor.snap_from_point = major_pt

        radius_x = math.hypot(major_pt.x - center.x, major_pt.y - center.y)
        rotation = math.atan2(major_pt.y - center.y, major_pt.x - center.x)

        if radius_x < 1e-6:
            self.editor.clear_dynamic()
            self.editor.snap_from_point = None
            self.editor.status_message.emit("Ellipse: zero-length major axis — cancelled")
            return

        def _preview_minor(m: Vec2) -> list:
            # Project mouse onto the minor-axis direction (perpendicular to major axis)
            perp_angle = rotation + math.pi / 2
            px = math.cos(perp_angle)
            py = math.sin(perp_angle)
            dx = m.x - center.x
            dy = m.y - center.y
            radius_y = abs(dx * px + dy * py)
            radius_y = max(radius_y, 1e-6)
            return [EllipseEntity(center=center, radius_x=radius_x, radius_y=radius_y, rotation=rotation)]

        self.editor.set_dynamic(_preview_minor)
        minor_pt = self.editor.get_point("Ellipse: pick minor-axis distance point")

        self.editor.clear_dynamic()
        self.editor.snap_from_point = None

        perp_angle = rotation + math.pi / 2
        px, py = math.cos(perp_angle), math.sin(perp_angle)
        dx = minor_pt.x - center.x
        dy = minor_pt.y - center.y
        radius_y = max(abs(dx * px + dy * py), 1e-6)

        self.editor.add_entity(EllipseEntity(
            center=center,
            radius_x=radius_x,
            radius_y=radius_y,
            rotation=rotation,
        ))
