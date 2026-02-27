"""Draw text command — pick an insertion point and enter the text string."""
from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import TextEntity


@command("textCommand")
class DrawTextCommand(CommandBase):
    """Place a text annotation by picking an insertion point."""

    def execute(self) -> None:
        position = self.editor.get_point("Text: pick insertion point")
        content  = self.editor.get_string("Text: enter text content")
        if content:
            self.editor.add_entity(TextEntity(
                text=content,
                position=position,
                height=2.5,
            ))
