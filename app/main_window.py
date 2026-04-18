"""
Main application window for OpenDraft.

Assembles the top-level layout and wires all major subsystems together.
Ribbon configuration data lives in :mod:`app.config.ribbon_config`.
"""
from typing import Optional

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence, QIcon

from controls.ribbon import RibbonPanel
from app.canvas import CADCanvas
from app.document import DocumentStore
from app.editor import Editor
from app.entities import Vec2
from app.entities.snap_types import SnapType
from app.ui.layer_manager import LayerManagerDialog
from app.ui.draftmate_settings import DraftmateSettingsDialog
from app.ui.status_bar import StatusBarWidget
from app.config.ribbon_config import RIBBON_CONFIG
from app.editor.command_registry import autodiscover
from app.logger import configure_logging

configure_logging()

# Trigger @command decorator registration for all command modules.
# Using autodiscover() instead of a bare `import app.commands` side-effect
# import makes the intent explicit and prevents linters from stripping it.
autodiscover("app.commands")

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenDraft 2D CAD App")
        _icon = Path(__file__).parent.parent / "assets" / "svg" / "badge_logo.svg"
        self.setWindowIcon(QIcon(str(_icon)))

        # ---- Core subsystems (created before widgets so canvas can receive
        #      proper constructor arguments instead of post-hoc attr injection) ---
        doc = DocumentStore()
        self._doc = doc
        self.editor = Editor(document=doc, parent=self)

        # ---- Layout -------------------------------------------------------
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        ribbon = RibbonPanel(
            RIBBON_CONFIG,
            dark=False,  # set True for dark mode
        )
        self._ribbon = ribbon
        layout.addWidget(ribbon)

        # Canvas receives document and editor via constructor — no post-hoc
        # private attribute injection needed.
        canvas = CADCanvas(document=doc, editor=self.editor)
        self._canvas = canvas
        layout.addWidget(canvas)

        # Global Escape shortcut: always handle Escape even when focus is
        # inside ribbon controls so users can press Esc to clear selection
        # or cancel commands without clicking the viewport first.
        esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)

        # Undo / Redo global shortcuts (Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z).
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.editor.undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self.editor.redo)

        # Delete key — delete selected entities when no command is running.
        del_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self)
        def _handle_delete():
            if not self.editor.is_running and self.editor.selection:
                self.editor.run_command("deleteCommand")
        del_shortcut.activated.connect(_handle_delete)

        esc_shortcut.activated.connect(canvas.handle_escape)

        # Canvas left-click → provide world point to the active command
        canvas.pointSelected.connect(
            lambda x, y: self.editor.provide_point(Vec2(x, y))
        )
        # Escape key on canvas → cancel the active command
        canvas.cancelRequested.connect(self.editor.cancel)

        # Wire PropertyPanel controls to the live document
        ribbon.setup_document(doc, editor=self.editor)

        # Ribbon button → route to the correct handler
        ribbon.actionTriggered.connect(self._on_action)

        # Redraw the canvas whenever the document changes.
        # Use QueuedConnection to ensure canvas.refresh() is called on the GUI
        # thread even though document_changed is emitted from the worker thread.
        self.editor.document_changed.connect(
            canvas.refresh, Qt.ConnectionType.QueuedConnection
        )
        # Redraw when selection changes (already on GUI thread).
        self.editor.selection.changed.connect(canvas.refresh)
        # Clear selection when a new command starts so drawing commands work
        # on a clean slate.
        self.editor.command_started.connect(lambda _: self.editor.selection.clear())
        # -------------------------------------------------------------------

        # thin separator that visually separates the central content from the status bar
        sep = QFrame()
        sep.setObjectName("StatusSeparator")
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setLineWidth(0)
        sep.setMidLineWidth(0)
        sep.setFixedHeight(1)
        sep.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(sep)

        central = QWidget()
        central.setLayout(layout)
        central.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central)

        # ---- Status bar (full custom widget) -------------------------------
        self._status_widget = StatusBarWidget()
        sb = self.statusBar()
        sb.setObjectName("MainStatusBar")
        # The StatusBarWidget is the sole occupant — add it as a permanent
        # widget that spans the full width.
        sb.addPermanentWidget(self._status_widget, 1)

        # Wire toggle buttons → canvas / engine state.
        self._wire_status_bar()

        # -------------------------------------------------------------------
        # Window sizing/positioning
        # -------------------------------------------------------------------
        self.setMinimumSize(1400, 768)
        self.resize(1400, 768)
        self._center_on_screen()

        # Editor status message → left side of status bar
        self.editor.status_message.connect(self._status_widget.cmd_label.setText)

        # update status with canvas mouse movement
        try:
            canvas.mouseMoved.connect(self._on_canvas_mouse_moved)
        except Exception:
            pass

        # Reusable Layer Manager dialog — created once, re-shown on demand.
        self._layer_dlg: Optional[LayerManagerDialog] = None

        # Sync status-bar buttons when the canvas toggles via F-keys.
        canvas.orthoChanged.connect(self._status_widget.set_ortho)
        canvas.draftmateChanged.connect(self._status_widget.set_draftmate)

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

    # Actions handled directly by MainWindow (not forwarded to the editor)
    _LOCAL_ACTIONS = {"toggleLayerModal", "togglePropertiesPanel", "toggleSettingsModal",
                       "undo", "redo"}

    def _on_action(self, name: str) -> None:
        """Route ribbon actions to the correct handler.

        Actions in :attr:`_LOCAL_ACTIONS` are handled here; everything else
        is forwarded to the editor's command runner.
        """
        if name == "toggleLayerModal":
            self._toggle_layer_modal()
        elif name == "undo":
            self.editor.undo()
        elif name == "redo":
            self.editor.redo()
        elif name in self._LOCAL_ACTIONS:
            # Placeholder — implement additional local actions here.
            pass
        else:
            self.editor.run_command(name)

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
            self._layer_dlg.layers_changed.connect(self._ribbon.refresh_layers)
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
