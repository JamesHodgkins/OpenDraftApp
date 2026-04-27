"""
Main application window for OpenDraft.

Assembles the top-level layout and wires all major subsystems together.
Ribbon configuration data lives in :mod:`app.config.ribbon_config`.
"""
import logging
from typing import Optional

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFrame,
    QDockWidget,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QShortcut, QKeySequence, QIcon, QCloseEvent

from controls.ribbon import RibbonPanel
from app.canvas import CADCanvas
from app.document import DocumentStore
from app.editor import Editor
from app.entities import Vec2
from app.entities.snap_types import SnapType
from app.ui.layer_manager import LayerManagerDialog
from app.ui.draftmate_settings import DraftmateSettingsDialog
from app.ui.status_bar import StatusBarWidget
from app.ui.properties_panel import PropertiesPanel
from app.ui.top_terminal import TopTerminalWidget
from app.config.ribbon_config import (
    RIBBON_CONFIG,
    command_specs_from_ribbon,
    ribbon_action_names,
)
from app.editor.command_registry import (
    apply_command_specs,
    autodiscover,
    autodiscover_entry_points,
    command_catalog,
    refresh_command_catalog as refresh_registered_command_catalog,
    validate_action_sources,
)
from app.logger import configure_logging
from app.ribbon_bridge import RibbonDocumentBridge

_log = logging.getLogger(__name__)

configure_logging()

# Trigger @command decorator registration for all command modules.
# Using autodiscover() instead of a bare `import app.commands` side-effect
# import makes the intent explicit and prevents linters from stripping it.
autodiscover("app.commands")
autodiscover_entry_points("opendraft.commands")
apply_command_specs(command_specs_from_ribbon())

_LOCAL_ACTION_NAMES = {
    "newDocument",
    "openDocumentFromFile",
    "saveDocumentToFile",
    "saveDocumentAs",
    "toggleLayerModal",
    "togglePropertiesPanel",
    "toggleSettingsModal",
    "undo",
    "redo",
}

_STARTUP_ACTION_REPORTS = validate_action_sources(
    {"ribbon": ribbon_action_names()},
    local_actions=_LOCAL_ACTION_NAMES,
)
_UNRESOLVED_RIBBON_ACTIONS = _STARTUP_ACTION_REPORTS["ribbon"].unresolved_actions
if _UNRESOLVED_RIBBON_ACTIONS:
    _log.warning(
        "Unresolved ribbon actions at startup: %s",
        ", ".join(_UNRESOLVED_RIBBON_ACTIONS),
    )

class MainWindow(QMainWindow):
    """Top-level application window."""

    _OPEN_FILE_FILTER = (
        "OpenDraft Files (*.odx *.json);;"
        "OpenDraft Native (*.odx);;"
        "JSON Files (*.json);;"
        "All Files (*)"
    )
    _SAVE_FILE_FILTER = (
        "OpenDraft Native (*.odx);;"
        "JSON Files (*.json);;"
        "All Files (*)"
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenDraft 2D CAD App")
        _icon = Path(__file__).parent.parent / "assets" / "svg" / "badge_logo_dark.svg"
        self.setWindowIcon(QIcon(str(_icon)))

        # ---- Core subsystems (created before widgets so canvas can receive
        #      proper constructor arguments instead of post-hoc attr injection) ---
        doc = DocumentStore()
        self._doc = doc
        self.editor = Editor(document=doc, parent=self)
        self._document_path: Optional[Path] = None
        self._last_saved_generation: int = doc.generation

        # ---- Ribbon toolbar (fixed at top, not affected by dock widgets) ----
        ribbon = RibbonPanel(
            RIBBON_CONFIG,
            dark=False,  # set True for dark mode
        )
        self._ribbon = ribbon

        self.setMenuWidget(ribbon)

        # ---- Canvas is the central drawing widget — docks snap beside it -----
        canvas = CADCanvas(document=doc, editor=self.editor)
        self._canvas = canvas

        # ---- Top terminal (single consolidated input + output) -------------
        # Implemented as an overlay anchored to the canvas so it does not
        # consume layout height (i.e. it sits on top of the viewport).
        terminal = TopTerminalWidget(editor=self.editor, parent=canvas)
        terminal.setFixedWidth(800)
        terminal.raise_()
        terminal.show()
        self._terminal = terminal

        class _TerminalOverlayAnchor(QObject):
            def __init__(self, *, canvas: QWidget, terminal: QWidget) -> None:
                super().__init__(canvas)
                self._canvas = canvas
                self._terminal = terminal

            def _reposition(self) -> None:
                x = max(0, (self._canvas.width() - self._terminal.width()) // 2)
                y = 8
                self._terminal.move(x, y)
                self._terminal.raise_()
                # Keep dropdown panel aligned under the input row.
                if hasattr(self._terminal, "_reposition_panel"):
                    try:
                        self._terminal._reposition_panel()  # type: ignore[attr-defined]
                    except Exception:
                        pass

            def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
                if obj is self._canvas and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                    self._reposition()
                return super().eventFilter(obj, event)

        self._terminal_anchor = _TerminalOverlayAnchor(canvas=canvas, terminal=terminal)
        canvas.installEventFilter(self._terminal_anchor)
        self._terminal_anchor._reposition()

        # Global Escape shortcut: always handle Escape even when focus is
        # inside ribbon controls so users can press Esc to clear selection
        # or cancel commands without clicking the viewport first.
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)

        # Undo / Redo global shortcuts (Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z).
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.editor.undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self.editor.redo)

        # Document workflow shortcuts.
        new_shortcut = QShortcut(QKeySequence.StandardKey.New, self)
        new_shortcut.activated.connect(self._new_document)
        open_shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        open_shortcut.activated.connect(self._open_document_from_file)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._save_document_to_file)
        save_as_shortcut = QShortcut(QKeySequence.StandardKey.SaveAs, self)
        save_as_shortcut.activated.connect(self._save_document_as)

        # Priority-7 UX shortcuts.
        help_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        help_shortcut.activated.connect(self._show_shortcuts_help)
        history_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F2), self)
        history_shortcut.activated.connect(self._toggle_command_history_panel)
        osnap_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F3), self)
        osnap_shortcut.activated.connect(self._toggle_master_osnap)

        # Delete key — delete selected entities when no command is running.
        # Call delete_selection() directly (not via run_command) because
        # delete is an immediate UI action, not a threaded command workflow.
        del_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        def _handle_delete():
            if not self.editor.is_running and self.editor.selection:
                self.editor.delete_selection()
                self.editor.document_changed.emit()
        del_shortcut.activated.connect(_handle_delete)

        def _handle_escape():
            # If the user is currently typing into the terminal, Esc should
            # clear that input first (CAD-style command line UX).
            if hasattr(terminal, "has_pending_input") and terminal.has_pending_input():
                terminal.clear_input()
                return
            canvas.handle_escape()
        esc_shortcut.activated.connect(_handle_escape)
        canvas.escapePressed.connect(_handle_escape)

        # Terminal command catalog — populate once all commands are registered.
        self._refresh_command_pickers()
        terminal.command_requested.connect(self.editor.run_command)
        # Canvas keypress (idle) → seed terminal input without extra clicks.
        canvas.terminalRequested.connect(terminal.focus_with_seed)
        # Canvas keypress forwarding → terminal input buffer (no focus required).
        canvas.terminalKeyEvent.connect(terminal.handle_key_event)

        # Canvas left-click → provide world point to the active command
        canvas.pointSelected.connect(
            lambda x, y: self.editor.provide_point(Vec2(x, y))
        )
        # Escape key on canvas → cancel the active command
        canvas.cancelRequested.connect(self.editor.cancel)

        # Wire ribbon property controls via the decoupled bridge
        self._bridge = RibbonDocumentBridge(ribbon, doc, self.editor)

        # Ribbon button → route to the correct handler
        ribbon.actionTriggered.connect(self._on_action)

        # Redraw the canvas whenever the document changes.
        # Use QueuedConnection to ensure canvas.refresh() is called on the GUI
        # thread even though document_changed is emitted from the worker thread.
        self.editor.document_changed.connect(
            canvas.refresh, Qt.ConnectionType.QueuedConnection
        )
        self.editor.document_changed.connect(
            self._update_window_title, Qt.ConnectionType.QueuedConnection
        )
        # Redraw when selection changes (already on GUI thread).
        self.editor.selection.changed.connect(canvas.refresh)
        # NOTE: Do not auto-clear selection on command start.
        #
        # Modify commands (Rotate/Move/Mirror/etc.) rely on the current
        # selection. Clearing here would make those commands no-op.
        # -------------------------------------------------------------------

        # Wrap canvas in a container so we can paint a stable 1px separator
        # line at the bottom without fighting QStatusBar's repaint ordering.
        _central = QWidget()
        _central_layout = QVBoxLayout(_central)
        _central_layout.setContentsMargins(0, 0, 0, 0)
        _central_layout.setSpacing(0)
        _central_layout.addWidget(canvas)
        _sep = QFrame()
        _sep.setFixedHeight(1)
        _sep.setStyleSheet("QFrame { background: #555555; border: none; }")
        _central_layout.addWidget(_sep)
        self.setCentralWidget(_central)

        # ---- Status bar (full custom widget) -------------------------------
        self._status_widget = StatusBarWidget()
        sb = self.statusBar()
        sb.setObjectName("MainStatusBar")
        sb.setContentsMargins(0, 0, 0, 0)
        # The StatusBarWidget is the sole occupant — add it as a permanent
        # widget that spans the full width.
        sb.addPermanentWidget(self._status_widget, 1)

        # Wire toggle buttons → canvas / engine state.
        self._wire_status_bar()

        # -------------------------------------------------------------------
        # Window sizing/positioning
        # -------------------------------------------------------------------
        self.setMinimumSize(800, 400)
        self.showMaximized()

        # Editor status message → left side of status bar
        self.editor.status_message.connect(self._status_widget.cmd_label.setText)
        # Mirror prompts/errors into the terminal scrollback too.
        self.editor.status_message.connect(terminal.append_scrollback)
        self.editor.command_started.connect(lambda name: terminal.append_scrollback(f"[start] {name}"))
        self.editor.command_finished.connect(lambda: terminal.append_scrollback("[done]"))

        # update status with canvas mouse movement
        try:
            canvas.mouseMoved.connect(self._on_canvas_mouse_moved)
            canvas.mouseMoved.connect(lambda x, y: terminal.update_cursor_world(x, y))
        except Exception:
            pass

        # Properties panel — dockable, right side.
        self._props_panel = PropertiesPanel(doc, self.editor, parent=self)
        self._props_dock = QDockWidget("Properties", self)
        self._props_dock.setObjectName("PropertiesDock")
        self._props_dock.setWidget(self._props_panel)
        self._props_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self._props_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._props_dock)
        self._props_dock.hide()  # hidden until the user opens it or selects entities
        self.editor.selection.changed.connect(self._props_panel.refresh)

        # Reusable Layer Manager dialog — created once, re-shown on demand.
        self._layer_dlg: Optional[LayerManagerDialog] = None

        # Sync status-bar buttons when the canvas toggles via F-keys.
        canvas.orthoChanged.connect(self._status_widget.set_ortho)
        canvas.draftmateChanged.connect(self._status_widget.set_draftmate)

        self._update_window_title()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._canvas.setFocus()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.editor.is_running:
            self.editor.cancel()
        if self._confirm_unsaved_changes("closing OpenDraft"):
            event.accept()
            return
        event.ignore()

    # -----------------------------------------------------------------------
    # Status-bar wiring
    # -----------------------------------------------------------------------

    def _wire_status_bar(self) -> None:
        """Connect every StatusBarWidget toggle to the matching engine state."""
        sw = self._status_widget
        canvas = self._canvas

        # -- Master OSNAP toggle --------------------------------------------
        def _on_master_snap(on: bool) -> None:
            canvas._osnap_master = on
            canvas.update()
        sw.btn_mas.toggled.connect(_on_master_snap)

        # -- Individual snap-type toggles -----------------------------------
        _snap_map = {
            SnapType.ENDPOINT:      sw.snap_button(SnapType.ENDPOINT),
            SnapType.MIDPOINT:      sw.snap_button(SnapType.MIDPOINT),
            SnapType.CENTER:        sw.snap_button(SnapType.CENTER),
            SnapType.PERPENDICULAR: sw.snap_button(SnapType.PERPENDICULAR),
            SnapType.NEAREST:       sw.snap_button(SnapType.NEAREST),
        }
        for st, btn in _snap_map.items():
            if btn is None:
                continue
            # Closure trick: bind *st* in default arg so each lambda captures
            # its own copy.
            def _make_handler(snap_type: SnapType):
                def _handler(on: bool) -> None:
                    if on:
                        canvas._osnap.enabled.add(snap_type)
                    else:
                        canvas._osnap.enabled.discard(snap_type)
                return _handler
            btn.toggled.connect(_make_handler(st))

        # -- Ortho toggle ---------------------------------------------------
        sw.btn_ortho.toggled.connect(canvas._set_ortho)

        # -- Draftmate toggle -----------------------------------------------
        sw.btn_dm.toggled.connect(canvas._set_draftmate)

        # Right-click DM → open settings dialog.
        sw.draftmate_settings_requested.connect(self._open_draftmate_settings)

    def _on_canvas_mouse_moved(self, x: float, y: float) -> None:
        self._status_widget.update_coords(x, y)

    # -----------------------------------------------------------------------
    # Action routing
    # -----------------------------------------------------------------------

    def _refresh_command_pickers(self) -> None:
        """Repopulate command pickers from the latest catalog snapshot."""
        self._terminal.set_commands(command_catalog())

    def refresh_command_catalog(self, *, reload_plugins: bool = True) -> None:
        """Refresh plugin commands and repopulate picker UIs.

        Intended for future plugin manager flows that install/unload plugins
        at runtime and need picker UIs to reflect the latest command set.
        """
        report = refresh_registered_command_catalog(reload_plugins=reload_plugins)
        self._refresh_command_pickers()
        _log.info(
            "Command catalog refreshed: %d commands, %d removed, %d entry points loaded",
            report.command_count,
            len(report.removed_command_ids),
            len(report.loaded_entry_points),
        )

    # Actions handled directly by MainWindow (not forwarded to the editor)
    _LOCAL_ACTIONS = set(_LOCAL_ACTION_NAMES)

    def _on_action(self, name: str) -> None:
        """Route ribbon actions to the correct handler.

        Actions in :attr:`_LOCAL_ACTIONS` are handled here; everything else
        is forwarded to the editor's command runner.
        """
        if name == "newDocument":
            self._new_document()
        elif name == "openDocumentFromFile":
            self._open_document_from_file()
        elif name == "saveDocumentToFile":
            self._save_document_to_file()
        elif name == "saveDocumentAs":
            self._save_document_as()
        elif name == "toggleLayerModal":
            self._toggle_layer_modal()
        elif name == "togglePropertiesPanel":
            self._toggle_properties_panel()
        elif name == "toggleSettingsModal":
            self._open_draftmate_settings()
        elif name == "undo":
            self.editor.undo()
        elif name == "redo":
            self.editor.redo()
        else:
            self.editor.run_command(name)

    def _is_document_dirty(self) -> bool:
        return self._doc.generation != self._last_saved_generation

    def _mark_document_saved(self) -> None:
        self._last_saved_generation = self._doc.generation

    def _current_file_display_name(self) -> str:
        if self._document_path is not None:
            return self._document_path.name
        return "Untitled.odx"

    def _default_file_dialog_dir(self) -> str:
        if self._document_path is not None:
            return str(self._document_path.parent)
        return str(Path.home())

    def _update_window_title(self) -> None:
        dirty = "*" if self._is_document_dirty() else ""
        self.setWindowTitle(
            f"OpenDraft 2D CAD App - {self._current_file_display_name()}{dirty}"
        )

    def _normalize_save_path(self, raw_path: str, selected_filter: str) -> Path:
        path = Path(raw_path)
        if path.suffix:
            return path
        if "JSON" in selected_filter.upper():
            return path.with_suffix(".json")
        return path.with_suffix(".odx")

    def _ensure_no_active_command(self) -> bool:
        if not self.editor.is_running:
            return True
        QMessageBox.warning(
            self,
            "Command Running",
            "Finish or cancel the active command before starting a file operation.",
        )
        self.editor.status_message.emit(
            "Finish or cancel the active command before file operations."
        )
        return False

    def _confirm_unsaved_changes(self, action_label: str) -> bool:
        if not self._is_document_dirty():
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved Changes")
        box.setText("The current drawing has unsaved changes.")
        box.setInformativeText(f"Save changes before {action_label}?")
        save_button = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is save_button:
            return self._save_document_to_file()
        if clicked is discard_button:
            return True
        if clicked is cancel_button:
            return False
        return False

    def _new_document(self) -> bool:
        if not self._ensure_no_active_command():
            return False
        if not self._confirm_unsaved_changes("creating a new drawing"):
            return False

        self._doc.reset_to_default()
        self.editor.selection.clear()
        self.editor.undo_stack.clear()
        self.editor.clear_dynamic()
        self.editor.clear_highlight()

        self._document_path = None
        self._mark_document_saved()
        self._bridge.refresh_layers()
        self._props_panel.refresh()
        self.editor.status_message.emit("Created new drawing.")
        self.editor.document_changed.emit()
        self._update_window_title()
        return True

    def _save_document_to_file(self) -> bool:
        if not self._ensure_no_active_command():
            return False
        if self._document_path is None:
            return self._save_document_as()
        return self._save_document_to_path(self._document_path)

    def _save_document_as(self) -> bool:
        if not self._ensure_no_active_command():
            return False

        initial_path = Path(self._default_file_dialog_dir()) / self._current_file_display_name()
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Drawing As",
            str(initial_path),
            self._SAVE_FILE_FILTER,
        )
        if not selected_path:
            return False

        return self._save_document_to_path(
            self._normalize_save_path(selected_path, selected_filter)
        )

    def _save_document_to_path(self, path: Path) -> bool:
        try:
            thumbnail_png = self._canvas.export_thumbnail_png()
            self._doc.save(path, thumbnail_png=thumbnail_png)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save drawing to:\n{path}\n\n{exc}",
            )
            self.editor.status_message.emit(f"Save failed: {exc}")
            return False

        self._document_path = path
        self._mark_document_saved()
        self._update_window_title()
        self.editor.status_message.emit(f"Saved: {path.name}")
        return True

    def _open_document_from_file(self) -> bool:
        if not self._ensure_no_active_command():
            return False
        if not self._confirm_unsaved_changes("opening another drawing"):
            return False

        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Drawing",
            self._default_file_dialog_dir(),
            self._OPEN_FILE_FILTER,
        )
        if not selected_path:
            return False

        return self._load_document_from_path(Path(selected_path))

    def _load_document_from_path(self, path: Path) -> bool:
        try:
            loaded = DocumentStore.load(path)
        except Exception as exc:
            message = self._format_load_error(exc)
            QMessageBox.critical(
                self,
                "Open Failed",
                f"Could not open drawing:\n{path}\n\n{message}",
            )
            self.editor.status_message.emit(f"Open failed: {message}")
            return False

        self._doc.replace_with(loaded)
        self.editor.selection.clear()
        self.editor.undo_stack.clear()
        self.editor.clear_dynamic()
        self.editor.clear_highlight()

        self._document_path = path
        self._mark_document_saved()
        self._bridge.refresh_layers()
        self._props_panel.refresh()
        self.editor.status_message.emit(f"Opened: {path.name}")
        self.editor.document_changed.emit()
        self._update_window_title()
        return True

    def _format_load_error(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            code = str(exc)
            if code == "invalid_zip":
                return "The file is not a valid ZIP-based OpenDraft .odx container."
            if code == "missing_document_json":
                return "The .odx file is missing required document.json payload."
            if code == "invalid_document_json":
                return "The document.json payload is invalid UTF-8 JSON."
        return str(exc) or exc.__class__.__name__

    def _toggle_properties_panel(self) -> None:
        """Show or hide the Properties dock panel."""
        if self._props_dock.isVisible():
            self._props_dock.hide()
        else:
            self.open_properties_panel()

    def open_properties_panel(self) -> None:
        """Show and refresh the Properties dock panel."""
        self._props_dock.show()
        self._props_panel.refresh()
        self._props_dock.raise_()

    def _toggle_layer_modal(self) -> None:
        """Open (or bring to front) the Layer Manager dialog.

        The dialog is created once and reused on subsequent opens,
        preserving scroll position and column widths between sessions.
        """
        if self._layer_dlg is None:
            self._layer_dlg = LayerManagerDialog(self._doc, parent=self, editor=self.editor)
            # Live-refresh the canvas whenever a layer property changes
            self._layer_dlg.layers_changed.connect(self._canvas.refresh)
            # Repopulate the layer combo if layers are added/removed/renamed
            self._layer_dlg.layers_changed.connect(self._bridge.refresh_layers)
        self._layer_dlg.exec()  # modal — canvas refresh signal still fires during exec()

    # -----------------------------------------------------------------------
    # Draftmate helpers
    # -----------------------------------------------------------------------

    def _open_draftmate_settings(self) -> None:
        """Open the Draftmate settings dialog."""
        dlg = DraftmateSettingsDialog(
            self._canvas._draftmate.settings, parent=self,
        )
        dlg.exec()
        # Sync the status label after the dialog closes.
        self._status_widget.set_draftmate(
            self._canvas._draftmate.settings.enabled
        )

    def _toggle_command_history_panel(self) -> None:
        """Toggle the top-terminal scrollback/history panel (F2)."""
        if hasattr(self._terminal, "toggle_history_panel"):
            self._terminal.toggle_history_panel()

    def _toggle_master_osnap(self) -> None:
        """Toggle master OSNAP state (F3)."""
        new_state = not self._canvas._osnap_master
        self._canvas._osnap_master = new_state
        self._status_widget.set_master_snap(new_state)
        self._canvas.update()

    def _show_shortcuts_help(self) -> None:
        """Show a compact keyboard shortcuts help dialog (F1)."""
        QMessageBox.information(
            self,
            "OpenDraft Help",
            "Keyboard shortcuts:\n"
            "F1  Help\n"
            "F2  Toggle command history panel\n"
            "F3  Toggle OSNAP\n"
            "F8  Toggle Ortho\n"
            "F10 Toggle Draftmate\n"
            "Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S  File operations\n"
            "Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z  Undo/Redo\n"
            "Delete  Delete selected entities\n"
            "Escape  Cancel command / clear selection",
        )

    # -----------------------------------------------------------------------
    # helpers
    # -----------------------------------------------------------------------
    def _center_on_screen(self) -> None:
        """Move the window to the centre of the primary available screen."""
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        avail = screen.availableGeometry()
        # move the top‑left point so that the window is centred
        new_left = avail.x() + (avail.width() - self.width()) // 2
        new_top = avail.y() + (avail.height() - self.height()) // 2
        self.move(new_left, new_top)
