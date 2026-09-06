"""Backstage-style file menu opened by the title bar's merged File button.

A frameless popup anchored under the File button, listing document-level
actions (New/Open/Save/Save As/Exit). Kept intentionally simple — a flat
list rather than a full multi-pane Backstage view — since OpenDraft's
File panel already exposes these actions on the ribbon too; this menu is
a faster, Office-style shortcut to the same handlers.
"""
from typing import Callable, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QCursor, QIcon, QPixmap
from PySide6.QtWidgets import QFrame, QVBoxLayout, QToolButton, QWidget, QFrame as QFrameSep

from controls.icon_widget import load_pixmap
from controls.ribbon.ribbon_constants import COLORS

__all__ = ["BackstageMenu"]

_ITEM_HEIGHT = 34
_ICON_SIZE = 18
_MENU_WIDTH = 220


def _blank_icon(size: int) -> QIcon:
    """A fully transparent icon, used to reserve an unused action's icon
    column so its label still lines up with icon-bearing rows above it."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    return QIcon(pixmap)


class BackstageMenu(QFrame):
    """Frameless popup menu listing file-level actions."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("BackstageMenu")
        self.setStyleSheet(f"""
            QFrame#BackstageMenu {{
                background: {COLORS.BACKGROUND_DARK};
                border: 1px solid {COLORS.MENU_BORDER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)
        self._layout = layout
        self.setFixedWidth(_MENU_WIDTH)
        self._anchor: Optional[QWidget] = None

    def add_action(self, label: str, icon_name: Optional[str], handler: Callable[[], None]) -> QToolButton:
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setFixedHeight(_ITEM_HEIGHT)
        btn.setSizePolicy(btn.sizePolicy().horizontalPolicy(), btn.sizePolicy().verticalPolicy())
        btn.setMinimumWidth(_MENU_WIDTH - 8)
        btn.setText(f"  {label}")
        # Always reserve the icon's width, even for actions with no icon of
        # their own (e.g. Exit) - QToolButton collapses that space when no
        # icon is set, which would otherwise pull just that row's label left
        # of the others and break the column's alignment.
        btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        pix = load_pixmap(icon_name, _ICON_SIZE) if icon_name else None
        btn.setIcon(QIcon(pix) if pix is not None else _blank_icon(_ICON_SIZE))
        btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background: transparent;
                color: {COLORS.TEXT_PRIMARY_DARK};
                text-align: left;
                padding-left: 6px;
                font-size: 9pt;
            }}
            QToolButton:hover {{ background: {COLORS.HOVER_DARK}; }}
            QToolButton:pressed {{ background: {COLORS.PRESSED_DARK}; }}
        """)

        def _on_click():
            self.close()
            handler()

        btn.clicked.connect(_on_click)
        self._layout.addWidget(btn)
        return btn

    def add_separator(self) -> None:
        sep = QFrameSep(self)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS.SEPARATOR}; border: none;")
        self._layout.addWidget(sep)

    def popup_below(self, anchor: QWidget) -> None:
        """Show the menu anchored to the bottom-left of *anchor*."""
        from PySide6.QtCore import QPoint

        self._anchor = anchor
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(0, anchor.height()))
        screen = anchor.screen()
        if screen:
            sr = screen.availableGeometry()
            if pos.x() + self.width() > sr.right():
                pos.setX(sr.right() - self.width())
            if pos.y() + self.height() > sr.bottom():
                pos = anchor.mapToGlobal(QPoint(0, -self.height()))
        self.move(pos)
        self.show()

    def closeEvent(self, event) -> None:  # noqa: N802
        # Qt.Popup grabs the mouse for the menu's lifetime, so the anchor
        # button's own hover tracking never sees the enter/leave that
        # actually happened underneath it - its stylesheet ``:hover`` state
        # can be left stuck on (or off) once the popup goes away. Force a
        # style re-polish against the real cursor position so the button's
        # look matches reality again.
        anchor = self._anchor
        if anchor is not None:
            under_mouse = anchor.rect().contains(anchor.mapFromGlobal(QCursor.pos()))
            if under_mouse and hasattr(anchor, "suppress_next_click"):
                anchor.suppress_next_click()
            anchor.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, under_mouse)
            anchor.style().unpolish(anchor)
            anchor.style().polish(anchor)
            anchor.update()
        super().closeEvent(event)
