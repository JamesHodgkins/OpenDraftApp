"""Draw arc command (centre → start → end)."""
import math

from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import ArcEntity, CircleEntity, LineEntity, Vec2


@command("arcCenterStartEndCommand")
class DrawArcCenterStartEndCommand(CommandBase):
    """Draw an arc by picking centre, then start point, then end point (CCW)."""

    def execute(self) -> None:
        center = self.editor.get_point("Arc: pick centre point")

        # Phase 1: circle tracks cursor to show the radius.
        self.editor.set_dynamic(
            lambda m: [
                CircleEntity(center=center, radius=max(1e-6, math.hypot(m.x - center.x, m.y - center.y))),
                LineEntity(p1=center, p2=m),
            ]
        )
        self.editor.snap_from_point = center
        start = self.editor.get_point("Arc: pick start point")

        radius      = math.hypot(start.x - center.x, start.y - center.y)
        start_angle = math.atan2(start.y - center.y, start.x - center.x)

        # Phase 2: arc sweeps from start_angle to cursor angle.
        def _arc_preview(m: Vec2):
            end_angle = math.atan2(m.y - center.y, m.x - center.x)
            return [ArcEntity(
                center=center,
                radius=radius,
                start_angle=start_angle,
                end_angle=end_angle,
                ccw=True,
            )]

        self.editor.set_dynamic(_arc_preview)
        end = self.editor.get_point("Arc: pick end point")
        self.editor.clear_dynamic()

        end_angle = math.atan2(end.y - center.y, end.x - center.x)
        self.editor.add_entity(ArcEntity(
            center=center,
            radius=radius,
            start_angle=start_angle,
            end_angle=end_angle,
            ccw=True,
        ))


@command("arcStartEndRadiusCommand")
class DrawArcStartEndRadiusCommand(CommandBase):
    """Draw an arc by picking start, end, then entering a radius."""

    def execute(self) -> None:
        start = self.editor.get_point("Arc: pick start point")

        # Show a line from start to cursor while picking the end point.
        self.editor.set_dynamic(lambda m: [LineEntity(p1=start, p2=m)])
        end = self.editor.get_point("Arc: pick end point")

        # Show the chord while the user types the radius.
        self.editor.set_dynamic(lambda m: [LineEntity(p1=start, p2=end)])
        radius = self.editor.get_float("Arc: enter radius")
        self.editor.clear_dynamic()

        # Compute the centre from the chord and radius (choose the left-hand
        # centre so the arc sweeps CCW by default).
        dx, dy = end.x - start.x, end.y - start.y
        chord  = math.hypot(dx, dy)
        if chord == 0 or radius < chord / 2:
            self.editor.status_message.emit("Arc: radius too small for the given points")
            return

        mid_x, mid_y = (start.x + end.x) / 2, (start.y + end.y) / 2
        h = math.sqrt(radius ** 2 - (chord / 2) ** 2)
        # Perpendicular direction (rotated 90° CCW from chord direction)
        perp_x, perp_y = -dy / chord, dx / chord
        cx = mid_x + h * perp_x
        cy = mid_y + h * perp_y

        center      = Vec2(cx, cy)
        start_angle = math.atan2(start.y - cy, start.x - cx)
        end_angle   = math.atan2(end.y   - cy, end.x   - cx)

        self.editor.add_entity(ArcEntity(
            center=center,
            radius=radius,
            start_angle=start_angle,
            end_angle=end_angle,
            ccw=True,
        ))
