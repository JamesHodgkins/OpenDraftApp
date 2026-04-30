"""Draw polyline command — stateful vertex collection with Escape finish."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import PolylineEntity, Vec2


@command("polylineCommand")
class DrawPolylineCommand(StatefulCommandBase):
    """Collect polyline vertices one point at a time.

    Each committed point is appended to an internal vertex list while the
    command remains active. Press Escape to finish and create the polyline when
    at least two points were collected; Escape with fewer points cancels.
    """

    next_vertex = export(None, label="Next vertex", input_kind="point")

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._points: list[Vec2] = []

    def start(self) -> None:
        self._points = []
        self.begin(active_export="next_vertex", reset=("next_vertex",))

    def update(self) -> None:
        self.editor.snap_from_point = self._points[-1] if self._points else None

        if not self._points and getattr(self, "next_vertex", None) is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            pts = list(self._points)
            candidate = self.point_preview("next_vertex", mouse)
            if candidate is not None:
                pts.append(candidate)
            elif pts:
                pts.append(mouse)
            if len(pts) < 2:
                return []
            return [PolylineEntity(points=pts, closed=False)]

        self.editor.set_dynamic(_preview)

    def commit(self) -> bool:
        point = self.point_value("next_vertex")
        if point is None:
            if not self._points:
                self.editor.status_message.emit("Polyline: pick first vertex")
            else:
                self.editor.status_message.emit("Polyline: pick next vertex or press Escape to finish")
            return False

        self._points.append(point)
        self.editor.snap_from_point = point
        self.next_vertex = None
        self.active_export = "next_vertex"
        return False

    def cancel(self) -> None:
        self.editor.clear_dynamic()
        self.editor.snap_from_point = None
        if len(self._points) >= 2:
            self.editor.add_entity(PolylineEntity(points=list(self._points), closed=False))

