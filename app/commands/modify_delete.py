"""Modify — Delete command."""
from app.editor import command
from app.editor.stateful_command import StatefulCommandBase


@command("deleteCommand")
class DeleteCommand(StatefulCommandBase):
    """Delete all selected entities from the document."""

    def start(self) -> bool:
        if not self.editor.selection:
            self.editor.status_message.emit("Delete: nothing selected")
            return False
        self.editor.delete_selection()
        self.editor.document_changed.emit()
        return False
