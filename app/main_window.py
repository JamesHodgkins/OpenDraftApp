"""
Main application window for OpenDraft.

Assembles the top-level layout and wires all major subsystems together.
Ribbon configuration data lives in :mod:`app.config.ribbon_config`.
"""
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt

from controls.ribbon import RibbonPanel
from app.canvas import CADCanvas
from app.document import DocumentStore
from app.editor import Editor
from app.entities import Vec2
from app.ui.layer_manager import LayerManagerDialog
from app.config.ribbon_config import RIBBON_CONFIG
from app.editor.command_registry import autodiscover

# Trigger @command decorator registration for all command modules.
# Using autodiscover() instead of a bare `import app.commands` side-effect
# import makes the intent explicit and prevents linters from stripping it.
autodiscover("app.commands")

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenDraft 2D CAD App")

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

        # Canvas left-click → provide world point to the active command
        canvas.pointSelected.connect(
            lambda x, y: self.editor.provide_point(Vec2(x, y))
        )
        # Escape key on canvas → cancel the active command
        canvas.cancelRequested.connect(self.editor.cancel)

        # Wire PropertyPanel controls to the live document
        ribbon.setup_document(doc)

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

        # Status bar — command prompt (left) and cursor coordinates (right)
        self.cmd_label = QLabel("")
        self.coord_label = QLabel("X: 0.00 Y: 0.00")
        sb = self.statusBar()
        sb.setObjectName("MainStatusBar")
        # rely on the separator/QSS for the top border; remove forced inline styling
        sb.addWidget(self.cmd_label)              # stretches on the left
        sb.addPermanentWidget(self.coord_label)   # pinned to the right

        # -------------------------------------------------------------------
        # Window sizing/positioning
        # -------------------------------------------------------------------
        # Ensure the initial size isn't too small or too large and center it on screen.
        # A separate minimum is already enforced by the canvas, but we add a default
        # resize to avoid unusually large automatic geometry which on some systems
        # resulted in the window appearing in the lower-right corner when the
        # content size exceeded the available screen size.
        self.setMinimumSize(1400, 768)
        self.resize(1400, 768)
        self._center_on_screen()

        # Editor status message → left side of status bar
        self.editor.status_message.connect(self.cmd_label.setText)

        # update status with canvas mouse movement
        try:
            canvas.mouseMoved.connect(self._on_canvas_mouse_moved)
        except Exception:
            pass

        # Reusable Layer Manager dialog — created once, re-shown on demand.
        self._layer_dlg: Optional[LayerManagerDialog] = None

    def _on_canvas_mouse_moved(self, x: float, y: float) -> None:
        self.coord_label.setText(f"X: {x:.2f} Y: {y:.2f}")

    # -----------------------------------------------------------------------
    # Action routing
    # -----------------------------------------------------------------------

    # Actions handled directly by MainWindow (not forwarded to the editor)
    _LOCAL_ACTIONS = {"toggleLayerModal", "togglePropertiesPanel", "toggleSettingsModal"}

    def _on_action(self, name: str) -> None:
        """Route ribbon actions to the correct handler.

        Actions in :attr:`_LOCAL_ACTIONS` are handled here; everything else
        is forwarded to the editor's command runner.
        """
        if name == "toggleLayerModal":
            self._toggle_layer_modal()
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
            self._layer_dlg = LayerManagerDialog(self._doc, parent=self)
            # Live-refresh the canvas whenever a layer property changes
            self._layer_dlg.layers_changed.connect(self._canvas.refresh)
            # Repopulate the layer combo if layers are added/removed/renamed
            self._layer_dlg.layers_changed.connect(self._ribbon.refresh_layers)
        self._layer_dlg.exec()  # modal — canvas refresh signal still fires during exec()

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
