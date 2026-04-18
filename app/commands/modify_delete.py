"""Modify — Delete command."""
from app.editor import command
from app.editor.base_command import CommandBase


@command("deleteCommand")
class DeleteCommand(CommandBase):
    """Delete all selected entities from the document."""

    def execute(self) -> None:
        if not self.editor.selection:
            self.editor.status_message.emit("Delete: nothing selected")
            return
        self.editor.delete_selection()
        self.editor.document_changed.emit()
