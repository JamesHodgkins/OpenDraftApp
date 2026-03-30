"""
app.commands — concrete drawing and editing commands for OpenDraft.

Each module in this package defines one or more commands decorated with
``@command("actionName")``.  Importing this package is enough to register
all commands in the editor's command registry — just do::

    import app.commands  # registers everything
"""
# Import every command module so their @command decorators fire.
from app.commands import (  # noqa: F401
    draw_line,
    draw_circle,
    draw_arc,
    draw_rect,
    draw_polyline,
    draw_text,
    annotate_dimension,
    trim,
)
