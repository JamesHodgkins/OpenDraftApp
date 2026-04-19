"""Draw point command — place a single point entity on each click."""
from app.editor import command
from app.editor.base_command import CommandBase, CommandCancelled
from app.entities import Vec2
from app.entities.point import PointEntity


@command("pointCommand")
class DrawPointCommand(CommandBase):
    """Place point entities repeatedly until Escape."""

    def execute(self) -> None:
        try:
            while True:
                pt = self.editor.get_point("Point: pick location (Escape to stop)")
                self.editor.add_entity(PointEntity(position=pt))
        except CommandCancelled:
            pass
