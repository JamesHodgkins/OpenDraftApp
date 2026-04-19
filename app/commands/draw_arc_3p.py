"""Draw arc command (3 points: start, intermediate, end)."""
import math

from app.editor import command
from app.editor.base_command import CommandBase
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
class DrawArc3PointCommand(CommandBase):
    """Draw an arc by picking three points on its perimeter."""

    def execute(self) -> None:
        p1 = self.editor.get_point("Arc 3P: pick start point")
        self.editor.snap_from_point = p1
        self.editor.set_dynamic(lambda m: [LineEntity(p1=p1, p2=m)])

        p2 = self.editor.get_point("Arc 3P: pick intermediate point")
        self.editor.snap_from_point = p2

        def _preview(m: Vec2):
            result = _arc_from_3_points(p1, p2, m)
            if result is None:
                return [LineEntity(p1=p1, p2=m)]
            center, radius, sa, ea, ccw = result
            return [ArcEntity(center=center, radius=radius, start_angle=sa, end_angle=ea, ccw=ccw)]

        self.editor.set_dynamic(_preview)

        p3 = self.editor.get_point("Arc 3P: pick end point")
        self.editor.clear_dynamic()
        self.editor.snap_from_point = None

        result = _arc_from_3_points(p1, p2, p3)
        if result is None:
            self.editor.status_message.emit("Arc 3P: points are collinear — no arc created")
            return
        center, radius, sa, ea, ccw = result
        self.editor.add_entity(ArcEntity(center=center, radius=radius, start_angle=sa, end_angle=ea, ccw=ccw))
