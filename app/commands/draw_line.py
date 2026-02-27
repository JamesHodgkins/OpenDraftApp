"""Draw line command — collects two points and adds a LineEntity."""
from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import LineEntity


@command("lineCommand")
class DrawLineCommand(CommandBase):
    """Draw a line by picking a start point and an end point."""

    def execute(self) -> None:
        start = self.editor.get_point("Line: pick start point")
        self.editor.set_dynamic(lambda m: [LineEntity(p1=start, p2=m)])
        end = self.editor.get_point("Line: pick end point")
        self.editor.clear_dynamic()
        self.editor.add_entity(LineEntity(p1=start, p2=end))
