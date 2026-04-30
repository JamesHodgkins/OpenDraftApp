"""Draw arc command (3 points: start, intermediate, end)."""
import math

from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import ArcEntity, LineEntity, Vec2


def _arc_from_3_points(p1: Vec2, p2: Vec2, p3: Vec2):
    """Return (center, radius, start_angle, end_angle, ccw) for the circle through p1, p2, p3.

    Returns None if the points are collinear.
    """
    ax, ay = p1.x, p1.y
    bx, by = p2.x, p2.y
    cx, cy = p3.x, p3.y

    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None

    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d

    center = Vec2(ux, uy)
    radius = math.hypot(p1.x - ux, p1.y - uy)
    start_angle = math.atan2(p1.y - uy, p1.x - ux)
    end_angle = math.atan2(p3.y - uy, p3.x - ux)

    # Determine winding: is p2 on the CCW arc from p1 to p3?
    mid_angle = math.atan2(p2.y - uy, p2.x - ux)
    # CCW span from start to mid
    ccw_to_mid = (mid_angle - start_angle) % (2 * math.pi)
    ccw_to_end = (end_angle - start_angle) % (2 * math.pi)
    ccw = ccw_to_mid <= ccw_to_end

    return center, radius, start_angle, end_angle, ccw


@command("arc3PointCommand")
class DrawArc3PointCommand(StatefulCommandBase):
    """Draw an arc by picking three points on its perimeter."""

    start_point = export(None, label="Start point", input_kind="point")
    intermediate_point = export(None, label="Intermediate point", input_kind="point")
    end_point = export(None, label="End point", input_kind="point")

    def start(self) -> None:
        self.begin(
            active_export="start_point",
            reset=("start_point", "intermediate_point", "end_point"),
        )

    def update(self) -> None:
        p1 = self.point_value("start_point")
        p2 = self.point_value("intermediate_point")
        p3 = self.point_value("end_point")

        self.set_snap_for_active(
            {
                "intermediate_point": p1,
                "end_point": (p2, p1),
                "start_point": (p3, p2),
            },
            default=(p3, p2, p1),
        )

        if p1 is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            if p2 is None:
                return [LineEntity(p1=p1, p2=mouse)]

            end = p3 if p3 is not None else mouse
            result = _arc_from_3_points(p1, p2, end)
            if result is None:
                return [LineEntity(p1=p1, p2=end)]
            center, radius, sa, ea, ccw = result
            return [ArcEntity(center=center, radius=radius, start_angle=sa, end_angle=ea, ccw=ccw)]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        p1 = self.point_value("start_point")
        p2 = self.point_value("intermediate_point")
        p3 = self.point_value("end_point")
        if p1 is None or p2 is None or p3 is None:
            self.editor.status_message.emit("Arc 3P: start, intermediate, and end points are required")
            return

        result = _arc_from_3_points(p1, p2, p3)
        if result is None:
            self.editor.status_message.emit("Arc 3P: points are collinear - no arc created")
            return

        center, radius, sa, ea, ccw = result
        self.editor.add_entity(ArcEntity(center=center, radius=radius, start_angle=sa, end_angle=ea, ccw=ccw))
        self.editor.snap_from_point = p3
