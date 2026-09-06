"""Regression coverage for the "unconfirmed input" status-bar finding.

Found via the ai_user AI-driven-testing harness: an agent (and, just as
easily, a human) typing a complete point value into a running command's
active field (e.g. "0,0" for Line's Start point) got no indication the
value was ready to confirm. The status bar stayed frozen on the export's
bare label ("Start point") the whole time — even after typing a *second*
value straight after with no intervening Enter/Space, which silently
appended onto the same unconfirmed field instead of starting fresh (see
KNOWN_BUGS-style bug: "0,0" + "100,100" typed back-to-back became the
single malformed string "0,0100,100", and the command silently never
advances past Start point).

Fixed in ``MainWindow._on_popup_property_preview_changed``: once a row's
live preview is a *complete* value (a full ``Vec2``, not a ``PartialPoint``
with a component still missing), the status bar now says so explicitly and
tells the user to confirm before typing the next value.

A second, related gap surfaced by re-running the same AI-driven task after
the above fix: the model sometimes typed a command name (e.g. "line") into
the *idle* command bar but never pressed Enter to actually run it — the
suggestion list was already showing and its top match already pre-selected
(a single Enter runs it), but nothing said so in text, so the next typed
value landed on top of the un-run command name instead of into a running
command's field (e.g. "line" + "0,0" -> the literal string "line0,0",
`editor.is_running` stays False the whole time). Fixed in
``PropertiesPanel._refresh_suggestion_buttons``: the moment a typed prefix
matches a real command, the status bar now says "Press Enter to run
'<Command>'" (or "No command matches '<text>'" for no match at all).

A third finding, surfaced once the above two fixes let the agent reliably
reach the point of *choosing* a command name: typing the natural English
word for a tool (e.g. "rectangle") matched nothing at all, because the
Rectangle tool's display name is the abbreviation "Rect" and
``PropertiesPanel._command_score`` only ever tested whether the *typed*
text was a substring/prefix of the label — never the reverse (the label
being a prefix of a longer word the user typed). Fixed by adding one more
scoring tier: a short, alphabetic label that the typed text starts with now
matches too (e.g. "rectangle".startswith("rect")).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ai_user.actions import Action
from ai_user.app_harness import AppHarness


@pytest.fixture
def harness():
    h = AppHarness()
    yield h
    h.close()


def _status_text(harness: AppHarness) -> str:
    return harness.window._status_widget.cmd_label.text()


def test_status_bar_is_silent_before_any_input(harness) -> None:
    harness.perform(Action(name="type", text="line"))
    harness.perform(Action(name="key", text="Return"))

    assert _status_text(harness) == "Start point"


def test_typing_a_complete_point_shows_a_confirm_hint(harness) -> None:
    harness.perform(Action(name="type", text="line"))
    harness.perform(Action(name="key", text="Return"))

    harness.perform(Action(name="type", text="0,0"))

    text = _status_text(harness)
    assert "0,0" in text
    assert "confirm" in text.lower()


def test_typing_a_partial_point_does_not_show_a_confirm_hint(harness) -> None:
    harness.perform(Action(name="type", text="line"))
    harness.perform(Action(name="key", text="Return"))

    harness.perform(Action(name="type", text="5"))  # x only — y still pending

    assert _status_text(harness) == "Start point"


def test_confirming_advances_past_the_hint_to_the_next_export(harness) -> None:
    harness.perform(Action(name="type", text="line"))
    harness.perform(Action(name="key", text="Return"))
    harness.perform(Action(name="type", text="0,0"))
    assert "confirm" in _status_text(harness).lower()

    harness.perform(Action(name="key", text="Return"))

    # Line's second export is the (vector-kind) End vector.
    assert "confirm" not in _status_text(harness).lower()
    assert "End" in _status_text(harness)


def test_typing_a_matching_command_name_shows_a_run_hint(harness) -> None:
    harness.perform(Action(name="type", text="line"))

    text = _status_text(harness)
    assert "Enter" in text
    assert "Line" in text
    # The command must not have started yet — this is the idle bar, before
    # any confirming Enter/Space was sent.
    assert harness.window.editor.is_running is False


def test_typing_an_unmatched_prefix_shows_no_match_message(harness) -> None:
    harness.perform(Action(name="type", text="zzzznotacommand"))

    text = _status_text(harness)
    assert "No command matches" in text
    assert "zzzznotacommand" in text


def test_command_bar_status_hint_clears_when_input_is_emptied(harness) -> None:
    harness.perform(Action(name="type", text="line"))
    assert _status_text(harness) != ""

    harness.perform(Action(name="key", text="Backspace"))
    harness.perform(Action(name="key", text="Backspace"))
    harness.perform(Action(name="key", text="Backspace"))
    harness.perform(Action(name="key", text="Backspace"))

    assert _status_text(harness) == ""


def test_typing_the_full_word_for_an_abbreviated_command_matches_it(harness) -> None:
    # Regression test: the Rectangle tool's display name is "Rect" — typing
    # the natural full word "rectangle" previously matched nothing at all.
    harness.perform(Action(name="type", text="rectangle"))

    text = _status_text(harness)
    assert "Rect" in text
    assert "No command matches" not in text


def test_command_score_matches_full_word_against_abbreviated_label() -> None:
    from ai_user.app_harness import AppHarness

    h = AppHarness()
    try:
        panel = h.window._props_panel
        spec = panel._all_commands["core.rect"]

        assert panel._command_score("core.rect", spec, "rect") is not None
        assert panel._command_score("core.rect", spec, "rectangle") is not None
    finally:
        h.close()
