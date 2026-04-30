"""Draw line command — stateful, with point + vector exports."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import LineEntity, Vec2


@command("lineCommand", aliases=("l",))
class DrawLineCommand(StatefulCommandBase):
    """Draw a line by picking a start point and an end vector."""

    start_point = export(None, label="Start point", input_kind="point")
    end_point = export(None, label="End vector", input_kind="vector")

    def start(self) -> None:
        self.begin(active_export="start_point", reset=("start_point", "end_point"))

    def seed_from_previous(self, prev: StatefulCommandBase) -> None:
        """Chain consecutive lines: previous end becomes our start.

        When Repeat-command auto-launches another DrawLine after a commit,
        the next line picks up where the last one ended (AutoCAD-style
        polyline drawing).  Active export is moved to ``end_point`` so the
        very next click extends the chain rather than re-defining Start.
        """
        start = self._resolve_complete_vec2(getattr(prev, "start_point", None))
        vector = self._resolve_complete_vec2(getattr(prev, "end_point", None))
        end = start + vector if start is not None and vector is not None else None
        if end is not None:
            self.start_point = end
            self.active_export = "end_point"
            self.editor.snap_from_point = end

    def update(self) -> None:
        start_anchor = self.point_value("start_point")
        vector_anchor = self.vector_value("end_point")
        end_anchor = start_anchor + vector_anchor if start_anchor and vector_anchor else None

        self.set_snap_for_active(
            {
                "end_point": start_anchor,
                "start_point": end_anchor,
            },
            default=(start_anchor, end_anchor),
        )

        if getattr(self, "start_point", None) is None:
            self.editor.clear_dynamic()
            return

        def _preview(mouse: Vec2):
            start = self.point_preview("start_point", mouse)
            if start is None:
                return []
            if getattr(self, "end_point", None) is None:
                end = mouse
            else:
                vector = self.vector_preview("end_point", mouse, base=start)
                if vector is None:
                    return []
                end = start + vector
            return [LineEntity(p1=start, p2=end)]

        self.editor.set_dynamic(_preview)

    def commit(self) -> None:
        start = self.point_value("start_point")
        vector = self.vector_value("end_point")
        if start is None or vector is None:
            self.editor.status_message.emit("Start point and end vector are required.")
            return
        end = start + vector
        self.editor.add_entity(LineEntity(p1=start, p2=end))
        # Make the just-committed end-point available as snap_from_point so
        # downstream commands (or a Repeat-command run that does NOT chain)
        # can still snap from it.
        self.editor.snap_from_point = end
