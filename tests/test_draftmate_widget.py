"""Tests for the custom DraftmateWidget input behaviour."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from app.ui.draftmate_widget import DraftmateWidget, InputFormat
from app.entities import Vec2


@pytest.fixture

def widget(qtbot):
    w = DraftmateWidget()
    w.set_input_mode("point", Vec2(0, 0))
    qtbot.addWidget(w)
    return w


def key(event, key_code, text=""):
    """Helper to create a key press event."""
    return QKeyEvent(QKeyEvent.KeyPress, key_code, Qt.NoModifier, text)


def test_tab_cycles_fields(widget):
    # field1 active initially
    assert widget._field_1.active
    assert not widget._field_2.active
    # press Tab
    widget.keyPressEvent(key(None, Qt.Key_Tab))
    assert not widget._field_1.active
    assert widget._field_2.active
    # press Shift+Tab
    widget.keyPressEvent(key(None, Qt.Key_Backtab))
    assert widget._field_1.active
    assert not widget._field_2.active


def test_d_key_resets_to_relative(widget):
    # start with relative format
    assert widget._input_format == InputFormat.RELATIVE
    # switch to absolute via '#'
    widget.keyPressEvent(key(None, Qt.Key_NumberSign, "#"))
    widget.keyPressEvent(key(None, Qt.Key_1, "1"))
    assert widget._input_format == InputFormat.ABSOLUTE
    # now press 'd' to go back
    widget.keyPressEvent(key(None, Qt.Key_D, "d"))
    assert widget._input_format == InputFormat.RELATIVE
    # fields should be cleared
    assert widget._field_1.text == ""
    assert widget._field_2.text == ""


def test_comma_advances_to_second_field(widget, qtbot):
    # type "0,0" as the user would expect using qtbot helper
    qtbot.keyClicks(widget, "0,0")
    assert widget._field_1.text == "0"
    assert widget._field_2.text == "0"
    # after the comma, the second field should have been activated
    assert widget._field_2.active
