"""
Command base classes and exception types.

Every concrete command inherits :class:`CommandBase` and implements
:meth:`execute`.  :class:`CommandCancelled` is raised automatically by
the :class:`~app.editor.Editor` input methods when the user presses Escape,
and it propagates cleanly up through :meth:`execute` without any extra
handling required in the command itself.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.editor.editor import Editor


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class CommandCancelled(Exception):
    """Raised inside a command thread to signal a clean cancellation.

    Caught by the editor's thread-runner; should not be caught inside
    ``execute()`` unless the command needs to do cleanup before exiting.
    """


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class CommandBase:
    """Abstract base class for all editor commands.

    Subclasses must implement :meth:`execute`.  The editor instance is
    injected at construction time so commands can call::

        pt    = self.editor.get_point("Pick start point")
        value = self.editor.get_integer("Enter repetitions")
        self.editor.add_entity(some_entity)

    Each ``get_*`` call blocks the command thread until the user provides
    input or presses Escape (in which case :class:`CommandCancelled` is
    raised and ``execute`` returns immediately).
    """

    #: Set automatically by the ``@command`` decorator.
    command_name: str = ""

    def __init__(self, editor: "Editor") -> None:
        self.editor = editor

    def execute(self) -> None:
        """Run the command logic.  Override in every concrete subclass."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute()"
        )

    def __repr__(self) -> str:          # noqa: D105
        return f"<{self.__class__.__name__}>"
