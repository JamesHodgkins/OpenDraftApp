"""Draw rectangle command — stateful two-corner workflow."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import RectangleEntity, Vec2


@command("rectCommand")
class DrawRectCommand(StatefulCommandBase):
    """Draw a rectangle from two opposite corner points."""

    first_corner = export(None, label="First corner", input_kind="point")
    opposite_corner = export(None, label="Opposite corner", input_kind="point")

    def start(self) -> None:
        self.begin(
            active_export="first_corner",
            reset=("first_corner", "opposite_corner"),
        )

    def update(self) -> None:
        p1 = self.point_value("first_corner")
        p2 = self.point_value("opposite_corner")

        self.set_snap_for_active(
            {
                "opposite_corner": p1,
                "first_corner": p2,
            },
            default=(p1, p2),
        )

        if p1 is None:
            self.editor.clear_dynamic()
            return

        self.editor.set_dynamic(lambda m: [RectangleEntity.from_corners(p1, p2 or m)])

    def commit(self) -> None:
        p1 = self.point_value("first_corner")
        p2 = self.point_value("opposite_corner")
        if p1 is None or p2 is None:
            self.editor.status_message.emit("Rectangle: both corner points are required")
            return
        self.editor.add_entity(RectangleEntity.from_corners(p1, p2))
        self.editor.snap_from_point = p2
