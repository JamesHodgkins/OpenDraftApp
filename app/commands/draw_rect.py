"""Draw rectangle command — two opposite corner points."""
from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import RectangleEntity


@command("rectCommand")
class DrawRectCommand(CommandBase):
    """Draw a rectangle from two opposite corner points."""

    def execute(self) -> None:
        p1 = self.editor.get_point("Rectangle: pick first corner")
        self.editor.snap_from_point = p1
        self.editor.set_dynamic(lambda m: [RectangleEntity(p1=p1, p2=m)])
        p2 = self.editor.get_point("Rectangle: pick opposite corner")
        self.editor.snap_from_point = None
        self.editor.clear_dynamic()
        self.editor.add_entity(RectangleEntity(p1=p1, p2=p2))
