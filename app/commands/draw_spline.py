"""Draw spline command — pick 3+ control points, Escape to finish."""
from app.editor import command
from app.editor.base_command import CommandBase, CommandCancelled
from app.entities import LineEntity, Vec2
from app.entities.spline import SplineEntity


@command("splineCommand")
class DrawSplineCommand(CommandBase):
    """Draw a Catmull-Rom spline by picking control points; Escape to finish."""

    def execute(self) -> None:
        points: list[Vec2] = []

        p1 = self.editor.get_point("Spline: pick first control point")
        points.append(p1)
        self.editor.snap_from_point = p1

        def _preview(m: Vec2) -> list:
            pts = points + [m]
            if len(pts) < 2:
                return []
            if len(pts) == 2:
                return [LineEntity(p1=pts[0], p2=pts[1])]
            return [SplineEntity(points=pts)]

        self.editor.set_dynamic(_preview)

        try:
            while True:
                pt = self.editor.get_point(
                    f"Spline: pick control point {len(points) + 1} (Escape to finish)"
                )
                points.append(pt)
                self.editor.snap_from_point = pt
        except CommandCancelled:
            pass

        self.editor.clear_dynamic()
        self.editor.snap_from_point = None

        if len(points) < 2:
            self.editor.status_message.emit("Spline: need at least 2 points — cancelled")
            return

        self.editor.add_entity(SplineEntity(points=points))
