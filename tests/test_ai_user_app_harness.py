"""Tests for ai_user.app_harness against a real, offscreen MainWindow.

These exercise the actual widget tree — region classification against the
real Controller dock / canvas geometry, and real QTest-injected key/mouse
events — rather than mocks, since the entire point of this harness is to
reproduce real Qt behaviour (focus, event delivery) faithfully.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from ai_user.actions import Action
from ai_user.app_harness import AppHarness, ScreenRegion


@pytest.fixture
def harness():
    h = AppHarness()
    yield h
    # Defensively close any modal dialog a test left open (e.g. Ctrl+S opens
    # a real Save-As dialog — see test_key_action_ctrl_s_opens_a_real_modal_dialog)
    # before tearing the window down, so one test's dialog can't leak into
    # the next test's fixture setup.
    modal = QApplication.instance().activeModalWidget() if QApplication.instance() else None
    if modal is not None:
        modal.reject() if hasattr(modal, "reject") else modal.close()
    h.close()


def test_screenshot_returns_a_nonempty_image_matching_window_size(harness) -> None:
    image = harness.screenshot()

    width, height = harness.window_size()
    assert image.width() == width
    assert image.height() == height
    assert not image.isNull()


def test_screenshot_png_bytes_are_a_valid_png(harness) -> None:
    data = harness.screenshot_png_bytes()

    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_properties_dock_point_classifies_as_properties_panel(harness) -> None:
    dock = harness.window._props_dock
    local_center = dock.rect().center()
    global_pt = dock.mapToGlobal(local_center)
    window_pt = harness.window.mapFromGlobal(global_pt)

    region = harness.classify_point(window_pt.x(), window_pt.y())

    assert region == ScreenRegion.PROPERTIES_PANEL


def test_canvas_point_classifies_as_viewport(harness) -> None:
    canvas = harness.window._canvas
    local_center = canvas.rect().center()
    global_pt = canvas.mapToGlobal(local_center)
    window_pt = harness.window.mapFromGlobal(global_pt)

    region = harness.classify_point(window_pt.x(), window_pt.y())

    assert region == ScreenRegion.VIEWPORT


def test_click_action_reports_the_region_it_landed_in(harness) -> None:
    dock = harness.window._props_dock
    local_center = dock.rect().center()
    global_pt = dock.mapToGlobal(local_center)
    window_pt = harness.window.mapFromGlobal(global_pt)

    outcome = harness.perform(Action(name="left_click", coordinate=(window_pt.x(), window_pt.y())))

    assert outcome.region == ScreenRegion.PROPERTIES_PANEL


def test_type_action_reports_keyboard_area_used(harness) -> None:
    outcome = harness.perform(Action(name="type", text="hello123"))

    assert outcome.used_keyboard_area is True


def test_key_action_ctrl_s_opens_a_real_modal_dialog_and_becomes_the_active_window(harness) -> None:
    # Save-As on an untitled document is genuine OpenDraft behaviour, not
    # something the harness works around: a screenshot-driven agent must be
    # able to see and eventually deal with it, same as a human would.
    #
    # perform() blocks for as long as the dialog's own nested exec() runs
    # (exactly as a human "waits" for a dialog), so this test observes the
    # dialog *while it is open* from inside a QTimer fired during that
    # nested loop, rather than racing perform()'s return.
    from PySide6.QtCore import QTimer

    seen = {}

    def observe_and_close():
        modal = QApplication.instance().activeModalWidget()
        seen["modal"] = modal
        seen["was_active_window"] = harness.active_window() is modal
        if modal is not None:
            modal.reject()

    QTimer.singleShot(200, observe_and_close)

    outcome = harness.perform(Action(name="key", text="ctrl+s"))

    assert outcome.used_keyboard_area is True
    assert seen.get("modal") is not None
    assert seen.get("was_active_window") is True


def test_key_action_escape_alone_does_not_count_as_keyboard_area(harness) -> None:
    outcome = harness.perform(Action(name="key", text="Escape"))

    assert outcome.used_keyboard_area is False


def test_screenshot_and_wait_actions_do_not_raise_or_affect_keyboard_scoring(harness) -> None:
    screenshot_outcome = harness.perform(Action(name="screenshot"))
    wait_outcome = harness.perform(Action(name="wait", duration=0.1))

    assert screenshot_outcome.used_keyboard_area is False
    assert wait_outcome.used_keyboard_area is False


def test_type_with_submit_true_types_and_confirms_in_one_action(harness) -> None:
    # Regression test for the compound type+submit action — added after
    # live agent testing showed the model reliably says "I will type X and
    # press Enter" but then only calls the tool once, leaving the value
    # typed-but-unconfirmed. submit=True makes this one atomic action
    # instead of relying on a second turn that doesn't always come.
    harness.perform(Action(name="type", text="line", submit=True))
    harness.perform(Action(name="type", text="0,0", submit=True))
    harness.perform(Action(name="type", text="100,100", submit=True))

    from app.entities import LineEntity

    doc = harness.window.editor.document
    lines = [e for e in doc.entities if isinstance(e, LineEntity)]
    assert len(lines) == 1
    assert lines[0].p1.x == 0.0 and lines[0].p1.y == 0.0
    assert lines[0].p2.x == 100.0 and lines[0].p2.y == 100.0
    assert harness.window.editor.is_running is False


def test_type_without_submit_leaves_value_unconfirmed(harness) -> None:
    harness.perform(Action(name="type", text="line"))
    harness.perform(Action(name="type", text="0,0"))  # no submit — same field

    # Without submit=True the two typed strings concatenate into the same
    # unconfirmed field, exactly the failure this feature exists to prevent.
    assert harness.window.editor.is_running is False
