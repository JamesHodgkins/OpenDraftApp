"""
Canvas context menu.

Encapsulates right-click actions for the CAD canvas so CADCanvas stays focused
on interaction + rendering rather than menu wiring.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from PySide6.QtWidgets import QMenu, QWidget


class CanvasContextMenu(QMenu):
    """Right-click context menu for the CAD canvas."""

    def __init__(
        self,
        *,
        parent: QWidget,
        is_idle: bool,
        can_undo: bool,
        can_redo: bool,
        undo_text: str,
        redo_text: str,
        has_selection: bool,
        repeat_label: str,
        can_repeat: bool,
        command_option_labels: Optional[Iterable[str]],
        on_command_option: Optional[Callable[[str], None]],
        on_cancel: Callable[[], None],
        on_undo: Callable[[], None],
        on_redo: Callable[[], None],
        on_delete: Callable[[], None],
        on_repeat: Callable[[], None],
        on_move: Callable[[], None],
        on_rotate: Callable[[], None],
        on_scale: Callable[[], None],
    ) -> None:
        super().__init__(parent)

        # Keep the canvas menu comfortable for mouse use: larger font + padding.
        # Scoped to this menu instance so it doesn't affect the rest of the app.
        self.setStyleSheet("""
            QMenu {
                background: #2D2D2D;
                color: #E5E7EB;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                padding: 8px 0px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 20px 8px 10px; /* top right bottom left */
                margin: 2px 6px;
                border-radius: 4px;
                min-width: 180px;
            }
            QMenu::item:hover {
                background: rgba(14, 156, 216, 0.22);
            }
            QMenu::item:selected {
                background: rgba(14, 156, 216, 0.30);
            }
            QMenu::item:disabled {
                color: rgba(229, 231, 235, 0.35);
                background: transparent;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255,255,255,0.10);
                margin: 6px 10px;
            }
        """)

        # When a command is running we still allow a small set of safe actions,
        # e.g. "Cancel" and any command-provided (choice) options.
        if not is_idle:
            labels = list(command_option_labels or [])
            if labels and on_command_option is not None:
                for label in labels:
                    act = self.addAction(label)
                    act.triggered.connect(lambda _checked=False, v=label: on_command_option(v))
                self.addSeparator()

            act_cancel = self.addAction("Cancel")
            act_cancel.triggered.connect(on_cancel)
            return

        act_repeat = self.addAction(repeat_label or "Repeat")
        act_repeat.setEnabled(bool(can_repeat))
        act_repeat.triggered.connect(on_repeat)

        self.addSeparator()

        act_undo = self.addAction(undo_text or "Undo")
        act_undo.setEnabled(bool(can_undo))
        act_undo.triggered.connect(on_undo)

        act_redo = self.addAction(redo_text or "Redo")
        act_redo.setEnabled(bool(can_redo))
        act_redo.triggered.connect(on_redo)

        self.addSeparator()

        act_delete = self.addAction("Delete")
        act_delete.setEnabled(bool(has_selection))
        act_delete.triggered.connect(on_delete)

        # Fixed modify commands
        act_move = self.addAction("Move")
        act_move.setEnabled(bool(has_selection))
        act_move.triggered.connect(on_move)

        act_rotate = self.addAction("Rotate")
        act_rotate.setEnabled(bool(has_selection))
        act_rotate.triggered.connect(on_rotate)

        act_scale = self.addAction("Scale")
        act_scale.setEnabled(bool(has_selection))
        act_scale.triggered.connect(on_scale)

