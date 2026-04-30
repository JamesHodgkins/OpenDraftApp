"""Draw point command — stateful single-point placement."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import Vec2
from app.entities.point import PointEntity


@command("pointCommand")
class DrawPointCommand(StatefulCommandBase):
    """Place one point per command run; repeat mode enables continuous picks."""

    position = export(None, label="Position", input_kind="point")

    def start(self) -> None:
        self.begin(active_export="position", reset=("position",))

    def update(self) -> None:
        pt = self.point_value("position")
        self.editor.snap_from_point = pt
        self.editor.clear_dynamic()

    def commit(self) -> None:
        pt = self.point_value("position")
        if pt is None:
            self.editor.status_message.emit("Point: position is required")
            return
        self.editor.add_entity(PointEntity(position=pt))
        self.editor.snap_from_point = pt
