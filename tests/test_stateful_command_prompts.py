"""Tests for stateful-command prompts surfacing in the status bar.

Every ``StatefulCommandBase`` export already carries a human-readable
``label`` (e.g. Circle's "Center" / "Radius").  ``Editor._emit_stateful_prompt``
mirrors whichever export is currently active into ``status_message`` — the
same signal the bottom-left status label is wired to — so a running command
always shows the user what it wants next, matching what the older blocking
``get_point``/``get_length``/etc. API already did for worker-thread commands.
"""
from __future__ import annotations

import app.commands  # noqa: F401 — registers commands
from app.document import DocumentStore
from app.editor.editor import Editor
from app.entities import LineEntity, Vec2


def test_starting_a_command_prompts_for_its_first_export(qtbot) -> None:
    ed = Editor(document=DocumentStore())
    messages: list[str] = []
    ed.status_message.connect(messages.append)

    ed.run_command("circleCommand")
    qtbot.waitUntil(lambda: ed.is_running)

    assert messages[-1] == "Center"


def test_advancing_to_the_next_export_updates_the_prompt(qtbot) -> None:
    ed = Editor(document=DocumentStore())
    messages: list[str] = []
    ed.status_message.connect(messages.append)

    ed.run_command("circleCommand")
    qtbot.waitUntil(lambda: ed.is_running)

    ed.provide_point(Vec2(0, 0))
    qtbot.waitUntil(lambda: ed.active_command.active_export == "radius")

    assert messages[-1] == "Radius"


def test_choice_export_prompt_lists_its_options(qtbot) -> None:
    doc = DocumentStore()
    ed = Editor(document=doc)
    line = LineEntity(p1=Vec2(0, 0), p2=Vec2(1, 0))
    doc.add_entity(line)
    ed.selection.add(line.id)
    messages: list[str] = []
    ed.status_message.connect(messages.append)

    ed.run_command("mirrorCommand")
    qtbot.waitUntil(lambda: ed.is_running)

    ed.provide_point(Vec2(0, 0))
    ed.provide_point(Vec2(0, 1))
    qtbot.waitUntil(lambda: ed.active_command.active_export == "keep_originals")

    assert messages[-1] == "Keep originals (Y/N)"


def test_panel_appends_live_readout_to_the_active_prompt(qtbot) -> None:
    """The rubber-band line length was invisible while freestyle-drawing.

    ``PropertiesPanel._refresh_active_prompt`` appends the active export's
    live-preview readout to the status-bar prompt on every cursor move, so
    drawing a line now shows "End vector — 3,4" (default relative style)
    rather than just "End vector" with no length/position visible anywhere.
    """
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    ed = Editor(document=doc)
    panel = PropertiesPanel(doc, ed)
    qtbot.addWidget(panel)
    messages: list[str] = []
    ed.status_message.connect(messages.append)

    ed.run_command("lineCommand")
    qtbot.waitUntil(lambda: ed.is_running)
    panel.bind_stateful_command(ed.active_command)

    ed.provide_point(Vec2(0, 0))
    qtbot.waitUntil(lambda: ed.active_command.active_export == "end_point")

    panel.update_cursor_world(3.0, 4.0)

    assert messages[-1] == "End vector — 3,4"


def test_panel_readout_switches_format_when_vector_style_cycles(qtbot) -> None:
    """Left/Right cycling the vector-input style changes how the readout renders."""
    from app.ui.properties_panel import PropertiesPanel

    doc = DocumentStore()
    ed = Editor(document=doc)
    panel = PropertiesPanel(doc, ed)
    qtbot.addWidget(panel)
    messages: list[str] = []
    ed.status_message.connect(messages.append)

    ed.run_command("lineCommand")
    qtbot.waitUntil(lambda: ed.is_running)
    panel.bind_stateful_command(ed.active_command)
    ed.provide_point(Vec2(0, 0))
    qtbot.waitUntil(lambda: ed.active_command.active_export == "end_point")

    assert ed.vector_input_style == "relative"

    panel._cycle_vector_input_style(1)
    assert ed.vector_input_style == "absolute"
    panel.update_cursor_world(3.0, 4.0)
    assert messages[-1] == "End vector — #3,4"

    panel._cycle_vector_input_style(1)
    assert ed.vector_input_style == "polar"
    panel.update_cursor_world(3.0, 4.0)
    assert messages[-1] == "End vector — 5<53.13°"

    # Wraps back around to relative.
    panel._cycle_vector_input_style(1)
    assert ed.vector_input_style == "relative"

    # Left steps backward.
    panel._cycle_vector_input_style(-1)
    assert ed.vector_input_style == "polar"


def test_finishing_a_command_clears_the_prompt(qtbot) -> None:
    ed = Editor(document=DocumentStore())
    messages: list[str] = []
    ed.status_message.connect(messages.append)

    ed.run_command("circleCommand")
    qtbot.waitUntil(lambda: ed.is_running)
    ed.cancel()
    qtbot.waitUntil(lambda: not ed.is_running)

    assert messages[-1] == ""
