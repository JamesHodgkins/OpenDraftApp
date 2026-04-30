"""Draw text command — pick an insertion point and enter the text string."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase, export
from app.entities import Vec2
from app.entities import TextEntity


@command("textCommand")
class DrawTextCommand(StatefulCommandBase):
    """Place a text annotation by picking an insertion point."""

    position = export(None, label="Position", input_kind="point")
    content = export(None, label="Content", input_kind="string")

    def start(self) -> None:
        self.begin(active_export="position", reset=("position", "content"))

    def update(self) -> None:
        position = self.point_value("position")
        self.editor.snap_from_point = position
        self.editor.clear_dynamic()

    def commit(self) -> None:
        position = self.point_value("position")
        content = self.string_value("content")
        if position is None or content is None:
            self.editor.status_message.emit("Text: position and content are required")
            return
        content = content.strip()
        if not content:
            self.editor.status_message.emit("Text: content cannot be empty")
            return

        self.editor.add_entity(
            TextEntity(
                text=content,
                position=position,
                height=2.5,
            )
        )
        self.editor.snap_from_point = position
