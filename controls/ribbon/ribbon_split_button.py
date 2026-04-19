"""
Ribbon Split Button Component.

A split button that can display in two modes:
- Large  : vertically-stacked icon button (top) and text dropdown (bottom).
- Small  : horizontally-arranged icon+label button (left) and dropdown arrow (right).
"""
from typing import List, Dict, Any, Callable, Optional
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QMenu, QPushButton,
    QStyle, QStyleOptionButton,
)
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtCore import Qt, QSize

from controls.icon_widget import Icon, load_pixmap
from controls.ribbon.ribbon_constants import SIZE, Styles, COLORS

__all__ = ["RibbonSplitButton"]

__all__ = ["RibbonSplitButton"]


class _SmallSplitMainButton(QPushButton):
    """Custom-painted small split-button main half for precise icon alignment."""

    _ICON_LEFT_OFFSET = -1
    _ICON_TOP_OFFSET = 1
    _ICON_TEXT_GAP = 4
    _TEXT_RIGHT_PADDING = 2

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)

        option.icon = QIcon()
        option.text = ""
        self.style().drawControl(QStyle.CE_PushButtonBevel, option, painter, self)

        icon_size = self.iconSize()
        icon_top = ((self.height() - icon_size.height()) // 2) + self._ICON_TOP_OFFSET
        icon_left = self._ICON_LEFT_OFFSET
        if not self.icon().isNull():
            mode = QIcon.Normal if self.isEnabled() else QIcon.Disabled
            state = QIcon.On if self.isDown() else QIcon.Off
            pixmap = self.icon().pixmap(icon_size, mode, state)
            painter.drawPixmap(icon_left, icon_top, pixmap)

        text_left = icon_left + icon_size.width() + self._ICON_TEXT_GAP
        text_width = max(0, self.width() - text_left - self._TEXT_RIGHT_PADDING)
        painter.setPen(self.palette().buttonText().color())
        painter.drawText(
            text_left,
            0,
            text_width,
            self.height(),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.text(),
        )
        painter.end()


class RibbonSplitButton(QWidget):
    """
    A split button widget for the ribbon interface.

    Args:
        main_icon: Path to the icon file (may be ``None``).
        main_label: Text label displayed on the button.
        items: Menu items — each a dict with ``'label'``, ``'action'`` callable,
               and optional ``'icon'`` path.
        main_action: Callback triggered by the primary (non-dropdown) click.
        parent: Optional parent widget.
        small: If ``True``, uses the compact horizontal layout.
    """

    def __init__(
        self,
        main_icon: Optional[str],
        main_label: str,
        items: List[Dict[str, Any]],
        main_action: Callable,
        parent: Optional[QWidget] = None,
        small: bool = False,
    ):
        super().__init__(parent)

        menu = self._build_menu(items)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # Use the shared split-button spacing for the large (vertical) layout
        layout.setSpacing(SIZE.SPLIT_BUTTON_SPACING)

        if small:
            self._create_small_layout(layout, menu, main_icon, main_label, main_action)
        else:
            self._create_large_layout(layout, menu, main_icon, main_label, main_action)

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu(self, items: List[Dict[str, Any]]) -> QMenu:
        menu = QMenu(self)
        # Style the dropdown to match the ribbon's dark theme
        menu.setStyleSheet(f"""
            QMenu {{
                background: {COLORS.BACKGROUND_DARK};
                color: {COLORS.TEXT_PRIMARY_DARK};
                border: 1px solid {COLORS.CONTROL_BG};
                border-radius: 4px;
                padding: 4px 0px;
            }}
            QMenu::icon {{
                padding-left: 6px;
            }}
            QMenu::item {{
                padding: 6px 12px 6px 6px;
            }}
            QMenu::item:selected {{
                color: {COLORS.TEXT_PRIMARY_DARK};
                background: {COLORS.HOVER_DARK};
            }}
        """)
        for item in items:
            icon_path = item.get("icon", "")
            icon_obj = None
            if icon_path:
                icon_name = os.path.splitext(os.path.basename(icon_path))[0]
                pix = load_pixmap(icon_name, SIZE.MENU_ICON_SIZE)
                if pix and not pix.isNull():
                    icon_obj = QIcon(pix)
            action = menu.addAction(icon_obj if icon_obj else QIcon(), item["label"])
            action.triggered.connect(item["action"])
        return menu

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _create_small_layout(
        self,
        _outer: QVBoxLayout,
        menu: QMenu,
        main_icon: Optional[str],
        main_label: str,
        main_action: Callable,
    ) -> None:
        # Horizontal split button: icon+label on left, arrow on right.  We want the
        # *total* width to equal a normal small button so the ribbon stays compact.
        total_w = SIZE.SMALL_BUTTON_WIDTH
        arrow_w = SIZE.DROPDOWN_ARROW_WIDTH
        label_w = total_w - arrow_w

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SIZE.SPLIT_BUTTON_SPACING)

        layout.addWidget(
            self._create_icon_label_button(main_icon, main_label, main_action, width=label_w)
        )
        layout.addWidget(self._create_arrow_button(menu))
        self.setLayout(layout)
        self.setFixedSize(total_w, SIZE.SMALL_BUTTON_HEIGHT)

    def _create_large_layout(
        self,
        layout: QVBoxLayout,
        menu: QMenu,
        main_icon: Optional[str],
        main_label: str,
        main_action: Callable,
    ) -> None:
        layout.addWidget(
            self._create_large_icon_button(main_icon, main_action),
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(
            self._create_dropdown_text_button(main_label, menu),
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        self.setLayout(layout)
        # Compute height from child sizes to avoid overlap (icon + dropdown + spacing)
        large_w = SIZE.LARGE_BUTTON_WIDTH
        icon_h = SIZE.ICON_LARGE_HEIGHT
        dropdown_h = SIZE.DROPDOWN_TEXT_HEIGHT
        spacing = layout.spacing()
        total_h = icon_h + dropdown_h + spacing
        self.setFixedSize(large_w, total_h)

    # ------------------------------------------------------------------
    # Individual button factories
    # ------------------------------------------------------------------

    def _create_icon_label_button(
        self,
        main_icon: Optional[str],
        main_label: str,
        main_action: Callable,
        width: Optional[int] = None,
    ) -> QPushButton:
        btn = _SmallSplitMainButton(self)
        if main_icon:
            icon_name = os.path.splitext(os.path.basename(main_icon))[0]
            pix = load_pixmap(icon_name, SIZE.SMALL_ICON_SIZE)
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(SIZE.SMALL_ICON_SIZE, SIZE.SMALL_ICON_SIZE))
        btn.setText(main_label)
        # default size originates from the ICON_LABEL constant, but callers can
        # override via the `width` argument (used by small split buttons).
        default_w = SIZE.ICON_LABEL_WIDTH
        btn.setFixedSize(width or default_w, SIZE.SMALL_BUTTON_HEIGHT)
        btn.clicked.connect(main_action)
        btn.setStyleSheet(Styles.small_icon_label_button())
        return btn

    def _create_arrow_button(self, menu: QMenu) -> QToolButton:
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.setText(Styles.ARROW_DOWN)
        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        w = SIZE.DROPDOWN_ARROW_WIDTH
        btn.setFixedSize(w, SIZE.SMALL_BUTTON_HEIGHT)
        btn.setStyleSheet(Styles.dropdown_arrow_button())
        return btn

    def _create_large_icon_button(
        self,
        main_icon: Optional[str],
        main_action: Callable,
    ) -> QToolButton:
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        if main_icon:
            icon_name = os.path.splitext(os.path.basename(main_icon))[0]
            pix = load_pixmap(icon_name, SIZE.LARGE_ICON_SIZE)
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(SIZE.LARGE_ICON_SIZE, SIZE.LARGE_ICON_SIZE))
        w, h = SIZE.ICON_LARGE_WIDTH, SIZE.ICON_LARGE_HEIGHT
        btn.setFixedSize(w, h)
        btn.clicked.connect(main_action)
        btn.setStyleSheet(Styles.large_icon_button())
        return btn

    def _create_dropdown_text_button(self, main_label: str, menu: QMenu) -> QToolButton:
        btn = QToolButton(self)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setText(f"{main_label} {Styles.ARROW_DOWN}")
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setMenu(menu)
        btn.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.DROPDOWN_TEXT_HEIGHT)
        btn.setStyleSheet(Styles.dropdown_text_button())
        return btn
