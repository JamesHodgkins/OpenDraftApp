"""Regression tests for command-row text input focus behavior."""
from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from app.editor.stateful_command import ExportInfo
from app.ui.properties_panel import _CmdPointRow, _CmdScalarRow


def _row_text(row) -> str:
    edit = row.findChild(QLineEdit)
    assert edit is not None
    return edit.text()


def test_cmd_point_row_append_text_keeps_first_character(qtbot) -> None:
    row = _CmdPointRow(
        ExportInfo(name="radius", label="Radius", input_kind="vector", default=None),
        point_parser=lambda _text: None,
    )
    qtbot.addWidget(row)
    row.show()

    row.append_text("2")
    qtbot.wait(0)
    row.append_text("0")
    row.append_text("0")

    assert _row_text(row) == "200"


def test_cmd_scalar_row_append_text_keeps_first_character(qtbot) -> None:
    row = _CmdScalarRow(
        ExportInfo(name="distance", label="Distance", input_kind="length", default=None)
    )
    qtbot.addWidget(row)
    row.show()

    row.append_text("2")
    qtbot.wait(0)
    row.append_text("0")
    row.append_text("0")

    assert _row_text(row) == "200"
