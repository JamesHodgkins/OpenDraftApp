"""Draw arc commands using stateful exported properties."""
import math

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import ArcEntity, CircleEntity, LineEntity, Vec2


def _arc_center_from_start_end_radius(
    start: Vec2,
    end: Vec2,
    radius: float,
) -> tuple[Vec2, float, float] | None:
    """Return center, start_angle, end_angle for start/end/radius arc.

    Uses the left-hand center relative to the chord so the arc defaults to CCW.
    Returns ``None`` when the radius is not geometrically valid.
    """
    dx, dy = end.x - start.x, end.y - start.y
    chord = math.hypot(dx, dy)
    if chord == 0 or radius < chord / 2:
        return None

    mid_x, mid_y = (start.x + end.x) / 2, (start.y + end.y) / 2
    h = math.sqrt(radius ** 2 - (chord / 2) ** 2)
    perp_x, perp_y = -dy / chord, dx / chord
    cx = mid_x + h * perp_x
    cy = mid_y + h * perp_y

    center = Vec2(cx, cy)
    start_angle = math.atan2(start.y - cy, start.x - cx)
    end_angle = math.atan2(end.y - cy, end.x - cx)
    return center, start_angle, end_angle


@command("arcCenterStartEndCommand")
class DrawArcCenterStartEndCommand(StatefulCommandBase):
    """Draw an arc by setting center, start point, and end point."""

    center = export(None, label="Center", input_kind="point")
    start_point = export(None, label="Start point", input_kind="point")
    end_point = export(None, label="End point", input_kind="point")

    def start(self) -> None:
        self.begin(
            active_export="center",
            reset=("center", "start_point", "end_point"),
        )

    def update(self) -> None:
        center = self.point_value("center")
        start = self.point_value("start_point")
        end = self.point_value("end_point")

        self.set_snap_for_active(
            {
                "start_point": center,
                "end_point": center,
                "center": (start, end),
            },
            default=(center, start, end),
        )

        if center is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            if start is None:
                radius = max(1e-6, math.hypot(mouse.x - center.x, mouse.y - center.y))
                return [
                    CircleEntity(center=center, radius=radius),
                    LineEntity(p1=center, p2=mouse),
                ]

            radius = math.hypot(start.x - center.x, start.y - center.y)
            if radius < 1e-6:
                return [LineEntity(p1=center, p2=mouse)]

            end_pt = end if end is not None else mouse
            start_angle = math.atan2(start.y - center.y, start.x - center.x)
            end_angle = math.atan2(end_pt.y - center.y, end_pt.x - center.x)
            return [
                ArcEntity(
                    center=center,
                    radius=radius,
                    start_angle=start_angle,
                    end_angle=end_angle,
                    ccw=True,
                )
            ]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        center = self.point_value("center")
        start = self.point_value("start_point")
        end = self.point_value("end_point")
        if center is None or start is None or end is None:
            self.editor.status_message.emit("Arc: center, start, and end points are required")
            return

        radius = math.hypot(start.x - center.x, start.y - center.y)
        if radius < 1e-6:
            self.editor.status_message.emit("Arc: start point must differ from center")
            return

        start_angle = math.atan2(start.y - center.y, start.x - center.x)
        end_angle = math.atan2(end.y - center.y, end.x - center.x)
        self.editor.add_entity(
            ArcEntity(
                center=center,
                radius=radius,
                start_angle=start_angle,
                end_angle=end_angle,
                ccw=True,
            )
        )
        self.editor.snap_from_point = end


@command("arcStartEndRadiusCommand")
class DrawArcStartEndRadiusCommand(StatefulCommandBase):
    """Draw an arc by setting start point, end point, and radius."""

    start_point = export(None, label="Start point", input_kind="point")
    end_point = export(None, label="End point", input_kind="point")
    radius = export(None, label="Radius", input_kind="length")

    def start(self) -> None:
        self.begin(
            active_export="start_point",
            reset=("start_point", "end_point", "radius"),
        )

    def update(self) -> None:
        start = self.point_value("start_point")
        end = self.point_value("end_point")
        radius = self.number_value("radius")

        self.set_snap_for_active(
            {
                "end_point": start,
                "radius": end,
                "start_point": end,
            },
            default=(end, start),
        )

        if start is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            if end is None:
                return [LineEntity(p1=start, p2=mouse)]
            if radius is None or radius <= 0:
                return [LineEntity(p1=start, p2=end)]

            result = _arc_center_from_start_end_radius(start, end, float(radius))
            if result is None:
                return [LineEntity(p1=start, p2=end)]
            center, start_angle, end_angle = result
            return [
                ArcEntity(
                    center=center,
                    radius=float(radius),
                    start_angle=start_angle,
                    end_angle=end_angle,
                    ccw=True,
                )
            ]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        start = self.point_value("start_point")
        end = self.point_value("end_point")
        radius = self.number_value("radius")
        if start is None or end is None or radius is None:
            self.editor.status_message.emit("Arc: start, end, and radius are required")
            return

        result = _arc_center_from_start_end_radius(start, end, radius)
        if result is None:
            self.editor.status_message.emit("Arc: radius too small for the given points")
            return

        center, start_angle, end_angle = result
        self.editor.add_entity(
            ArcEntity(
                center=center,
                radius=radius,
                start_angle=start_angle,
                end_angle=end_angle,
                ccw=True,
            )
        )
        self.editor.snap_from_point = end
