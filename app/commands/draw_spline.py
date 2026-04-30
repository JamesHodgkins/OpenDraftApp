"""Draw spline command — pick 3+ control points, Escape to finish."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import LineEntity, Vec2
from app.entities.spline import SplineEntity


@command("splineCommand")
class DrawSplineCommand(StatefulCommandBase):
    """Collect spline control points one point at a time."""

    next_control_point = export(None, label="Next control point", input_kind="point")

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._points: list[Vec2] = []

    def start(self) -> None:
        self._points = []
        self.begin(active_export="next_control_point", reset=("next_control_point",))

    def update(self) -> None:
        self.editor.snap_from_point = self._points[-1] if self._points else None

        if not self._points and getattr(self, "next_control_point", None) is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2) -> list:
            pts = list(self._points)
            candidate = self.point_preview("next_control_point", mouse)
            if candidate is not None:
                pts.append(candidate)
            elif pts:
                pts.append(mouse)
            if len(pts) < 2:
                return []
            if len(pts) == 2:
                return [LineEntity(p1=pts[0], p2=pts[1])]
            return [SplineEntity(points=pts)]

        self.editor.set_dynamic(_preview)

    def commit(self) -> bool:
        point = self.point_value("next_control_point")
        if point is None:
            if not self._points:
                self.editor.status_message.emit("Spline: pick first control point")
            else:
                self.editor.status_message.emit("Spline: pick next control point or press Escape to finish")
            return False

        self._points.append(point)
        self.editor.snap_from_point = point
        self.next_control_point = None
        self.active_export = "next_control_point"
        return False

    def cancel(self) -> None:
        self.editor.clear_dynamic()
        self.editor.snap_from_point = None
        if len(self._points) < 2:
            self.editor.status_message.emit("Spline: need at least 2 points - cancelled")
            return
        self.editor.add_entity(SplineEntity(points=list(self._points)))
