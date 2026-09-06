"""Drives a real OpenDraft ``MainWindow`` the way a human would.

The harness owns the one legitimate "cheat" in this whole system: it can
look at the widget tree to answer *geometric* questions (where is the
viewport, where is the properties dock, what widget currently has focus)
purely so it can classify a coordinate/detect a focus change for scoring
purposes. It never uses that access to read or drive application *state*
(entities, commands, etc.) — every actual input is delivered through Qt's
real event pipeline (``QTest``), exactly as it would arrive from a physical
mouse/keyboard, so focus-stealing bugs and dropped keystrokes are reproduced
for real rather than assumed away.

**Modal dialogs are in scope.** OpenDraft opens real (non-native, since
``QT_QPA_PLATFORM=offscreen`` has no OS dialog backend to call into) Qt
dialogs for things like Save As — a genuine, correct part of the app, not
something the harness works around. ``active_window()`` always resolves to
whichever top-level window currently has the active/modal focus, and
screenshots + click/key targeting follow it — exactly what a human sees and
operates, dialog or not. An agent that never learns to handle a dialog it
opened will simply run out of steps against it, same as a confused human
user would.

Runs with ``QT_QPA_PLATFORM=offscreen`` by default — Qt still fully lays out
and paints widgets in that mode, so ``grab()`` returns a real rendered
pixmap and geometry/focus queries behave exactly as on-screen.

**Fonts do not load under Qt's offscreen platform on Windows** — unlike the
real ``windows`` platform (242 families available here), the offscreen QPA
backend's font database returns zero families with no error, so every
screenshot renders all text as blank tofu boxes with no warning that
anything is wrong. This was found via a real agent episode that appeared to
"ignore" on-screen status text — it never could have read it. See
``_ensure_fonts_loaded()``, which explicitly registers a system font (Segoe
UI, falling back to Arial) via ``QFontDatabase.addApplicationFont`` before
any widget is constructed, so offscreen screenshots carry real, legible
glyphs. This is a known upstream Qt limitation (the offscreen platform has
no OS font-enumeration backend on Windows the way it does via fontconfig on
Linux), not something specific to OpenDraft.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from app.main_window import MainWindow

from ai_user.actions import Action, KEYBOARD_AREA_TOKENS


class ScreenRegion(Enum):
    """Which named region of the app a screen coordinate falls in."""
    VIEWPORT = "viewport"
    PROPERTIES_PANEL = "properties_panel"
    OTHER = "other"


# Candidate system font files to register explicitly for the offscreen
# platform, in preference order. Only used when QFontDatabase reports zero
# families already loaded (i.e. never on the real ``windows`` platform,
# where Windows' own font enumeration already works) — see module docstring.
_FALLBACK_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\segoeui.ttf",  # Segoe UI — matches the app's own QSS
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
)


def _ensure_fonts_loaded() -> None:
    """Register a real font for the offscreen platform if none loaded.

    Qt's offscreen QPA platform has no OS font-enumeration backend on
    Windows (unlike the real ``windows`` platform, or Linux's fontconfig
    fallback) — ``QFontDatabase.families()`` silently returns empty and
    every screenshot renders all text as blank glyph boxes, with no error
    or warning. Explicitly loading one system font file via
    ``addApplicationFont`` is enough to give the whole app legible text.
    A no-op (and harmless) when fonts are already available, or when none
    of the candidate files exist on this machine — screenshots would just
    keep rendering tofu as before, same as prior to this fix.
    """
    if QFontDatabase.families():
        return
    for path in _FALLBACK_FONT_CANDIDATES:
        if os.path.exists(path) and QFontDatabase.addApplicationFont(path) != -1:
            return


# Modifier-key name -> Qt enum, for both `key` combos and click modifiers.
_MODIFIER_MAP = {
    "ctrl": Qt.KeyboardModifier.ControlModifier,
    "control": Qt.KeyboardModifier.ControlModifier,
    "shift": Qt.KeyboardModifier.ShiftModifier,
    "alt": Qt.KeyboardModifier.AltModifier,
    "super": Qt.KeyboardModifier.MetaModifier,
    "meta": Qt.KeyboardModifier.MetaModifier,
}

# Single "key" action text -> Qt.Key, for the non-printable/named keys the
# computer-use tool sends (e.g. "Return", "Escape", "Tab", "space", "F2").
_NAMED_KEY_MAP = {
    "return": Qt.Key.Key_Return,
    "enter": Qt.Key.Key_Enter,
    "escape": Qt.Key.Key_Escape,
    "esc": Qt.Key.Key_Escape,
    "tab": Qt.Key.Key_Tab,
    "space": Qt.Key.Key_Space,
    "backspace": Qt.Key.Key_Backspace,
    "delete": Qt.Key.Key_Delete,
    "up": Qt.Key.Key_Up,
    "down": Qt.Key.Key_Down,
    "left": Qt.Key.Key_Left,
    "right": Qt.Key.Key_Right,
    "home": Qt.Key.Key_Home,
    "end": Qt.Key.Key_End,
    **{f"f{i}": getattr(Qt.Key, f"Key_F{i}") for i in range(1, 13)},
}


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def _split_key_combo(text: str) -> Tuple[Tuple[Qt.KeyboardModifier, ...], Optional[Qt.Key], Optional[str]]:
    """Parse a computer-use ``key`` action's text, e.g. "ctrl+s" or "a".

    Returns (modifiers, qt_key_for_named_key_or_None, literal_char_or_None).
    Exactly one of the last two is set: named keys (Return, F2, ...) resolve
    to a Qt.Key; a single printable character is sent as literal text instead
    so QTest picks the correct key + shift state for symbols.
    """
    parts = [p.strip() for p in text.split("+") if p.strip()]
    mods = []
    key_part = None
    for p in parts:
        low = p.lower()
        if low in _MODIFIER_MAP:
            mods.append(_MODIFIER_MAP[low])
        else:
            key_part = p
    if key_part is None:
        return tuple(mods), None, None
    named = _NAMED_KEY_MAP.get(key_part.lower())
    if named is not None:
        return tuple(mods), named, None
    return tuple(mods), None, key_part


def _combine_modifiers(mods: Tuple[Qt.KeyboardModifier, ...]) -> Qt.KeyboardModifier:
    combined = Qt.KeyboardModifier.NoModifier
    for m in mods:
        combined |= m
    return combined


@dataclass
class ActionOutcome:
    """What happened while executing one action — feeds the scorer."""
    region: ScreenRegion
    focus_before: Optional[QWidget]
    focus_after: Optional[QWidget]
    used_keyboard_area: bool


class AppHarness:
    """Boots OpenDraft and exposes screenshot / region / input primitives."""

    def __init__(self) -> None:
        self.app = _app()
        _ensure_fonts_loaded()
        self.window = MainWindow()
        # size the window explicitly — offscreen platform has no window
        # manager to give it a sane default size.
        self.window.resize(1600, 1000)
        self.window.show()
        self.app.processEvents()

    # -- lifecycle ---------------------------------------------------
    def close(self) -> None:
        """Tear down the window without going through its interactive
        ``closeEvent`` — that path pops a real "save unsaved changes?"
        QMessageBox when the episode's document is dirty (correct behaviour
        for a human quitting the app, but not something the harness should
        ever have to answer at teardown, and another reentrant-modal path to
        avoid — see the `key`/`left_click` branches of ``perform()``).
        ``hide()`` + ``deleteLater()`` skips ``closeEvent`` entirely.
        """
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    # -- window resolution -----------------------------------------------
    def active_window(self) -> QWidget:
        """Whichever top-level window a human would currently be looking at
        and typing/clicking into: an open modal dialog if one is active,
        else the main window. This is what screenshots and coordinates are
        always relative to — matching what's actually on screen.
        """
        modal = self.app.activeModalWidget()
        if modal is not None and modal.isVisible():
            return modal
        active = self.app.activeWindow()
        if active is not None and active.isVisible():
            return active
        return self.window

    # -- perception ----------------------------------------------------
    def screenshot(self) -> QImage:
        """Render the active top-level window, exactly as a human would see it."""
        self.app.processEvents()
        pixmap = self.active_window().grab()
        return pixmap.toImage()

    def screenshot_png_bytes(self) -> bytes:
        from PySide6.QtCore import QBuffer, QIODevice

        image = self.screenshot()
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buf, "PNG")
        return bytes(buf.data())

    def window_size(self) -> Tuple[int, int]:
        size = self.active_window().size()
        return size.width(), size.height()

    # -- region classification -----------------------------------------
    def classify_point(self, x: int, y: int) -> ScreenRegion:
        """Classify a pixel coordinate — local to whichever window is
        currently active (matching the coordinate space of the most recent
        ``screenshot()``) — into a named region. A dialog (or any window
        other than the main window) always classifies as OTHER: the
        properties-panel/viewport rules only apply to OpenDraft's own main
        window regions.
        """
        active = self.active_window()
        if active is not self.window:
            return ScreenRegion.OTHER

        global_pt = active.mapToGlobal(QPoint(int(x), int(y)))

        dock = getattr(self.window, "_props_dock", None)
        if dock is not None and dock.isVisible():
            top_left = dock.mapToGlobal(QPoint(0, 0))
            rect = dock.rect()
            rect.moveTopLeft(top_left)
            if rect.contains(global_pt):
                return ScreenRegion.PROPERTIES_PANEL

        canvas = getattr(self.window, "_canvas", None)
        if canvas is not None and canvas.isVisible():
            top_left = canvas.mapToGlobal(QPoint(0, 0))
            rect = canvas.rect()
            rect.moveTopLeft(top_left)
            if rect.contains(global_pt):
                return ScreenRegion.VIEWPORT

        return ScreenRegion.OTHER

    def focused_widget(self) -> Optional[QWidget]:
        return self.app.focusWidget()

    # -- action execution ------------------------------------------------
    def perform(self, action: Action) -> ActionOutcome:
        """Execute one action against the real widget tree and report what
        happened (region touched, focus before/after) for scoring.
        """
        focus_before = self.focused_widget()
        region = ScreenRegion.OTHER
        used_keyboard_area = False
        active = self.active_window()

        if action.name in ("left_click", "double_click"):
            x, y = action.coordinate or (0, 0)
            region = self.classify_point(x, y)
            global_pt = active.mapToGlobal(QPoint(int(x), int(y)))
            target = self.app.widgetAt(global_pt)
            if target is None:
                target = active
            local_pt = target.mapFromGlobal(global_pt)
            mods = _combine_modifiers(tuple(_MODIFIER_MAP[m.lower()] for m in action.modifiers if m.lower() in _MODIFIER_MAP))
            clicks = 2 if action.name == "double_click" else 1

            # Same nested-exec() reentrancy hazard as the `key` branch below
            # (e.g. clicking a ribbon "Save" button can open a modal dialog
            # synchronously) — post the click(s) rather than deliver them
            # directly inside this call stack.
            def _deliver(target=target, mods=mods, local_pt=local_pt, clicks=clicks):
                for _ in range(clicks):
                    QTest.mouseClick(target, Qt.MouseButton.LeftButton, mods, local_pt)

            QTimer.singleShot(0, _deliver)
            self.app.processEvents()

        elif action.name == "type":
            text = action.text or ""
            target = self.app.focusWidget() or active

            def _deliver(target=target, text=text, submit=action.submit):
                QTest.keyClicks(target, text)
                if submit:
                    # Pressing Enter right after typing can synchronously
                    # start/advance a command (or open a modal dialog) —
                    # same reentrancy hazard as the `key` branch below, so
                    # this whole delivery (type + submit) already runs
                    # inside one deferred callback rather than directly in
                    # this call stack.
                    QTest.keyClick(target, Qt.Key.Key_Return)

            QTimer.singleShot(0, _deliver)
            self.app.processEvents()
            used_keyboard_area = any(ch.lower() in KEYBOARD_AREA_TOKENS for ch in text)

        elif action.name == "key":
            text = action.text or ""
            target = self.app.focusWidget() or active
            mods, named_key, literal = _split_key_combo(text)
            qt_mods = _combine_modifiers(mods)
            # A key combo (e.g. Ctrl+S) can synchronously open a modal
            # dialog (a real, correct app behaviour — see module docstring).
            # Qt's QTest helpers pump their own internal event loop while
            # delivering a key event; letting a *nested* dialog exec() start
            # underneath that pump is fragile (observed native-crash-level
            # instability under the offscreen platform). Posting the key
            # event for the next event-loop iteration instead means any
            # dialog it opens starts its own exec() at the top level, which
            # is the well-trodden, stable path.
            def _deliver():
                if named_key is not None:
                    QTest.keyClick(target, named_key, qt_mods)
                elif literal is not None and len(literal) == 1:
                    QTest.keyClick(target, ord(literal.lower()), qt_mods)

            QTimer.singleShot(0, _deliver)
            self.app.processEvents()
            used_keyboard_area = _key_combo_uses_keyboard_area(text)

        elif action.name == "scroll":
            # Not needed by current OpenDraft tasks; accepted as a no-op so
            # an agent that tries it doesn't crash the episode.
            pass

        elif action.name in ("screenshot", "wait", "done"):
            pass

        self.app.processEvents()
        focus_after = self.focused_widget()
        return ActionOutcome(
            region=region,
            focus_before=focus_before,
            focus_after=focus_after,
            used_keyboard_area=used_keyboard_area,
        )


def _key_combo_uses_keyboard_area(text: str) -> bool:
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    return any(p in KEYBOARD_AREA_TOKENS for p in parts)
