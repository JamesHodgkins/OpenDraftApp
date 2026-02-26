"""
Ribbon Split Button Component.

A split button that can display in two modes:
- Large  : vertically-stacked icon button (top) and text dropdown (bottom).
- Small  : horizontally-arranged icon+label button (left) and dropdown arrow (right).
"""
from typing import List, Dict, Any, Callable, Optional
import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QMenu
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize

from controls.icon_widget import Icon
from controls.ribbon.ribbon_constants import SIZE, Styles, ButtonSize, IconSize, COLORS


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
        # Ensure menu item text and hovered item text is visible on dark backgrounds
        menu.setStyleSheet(f"""
            QMenu {{
                color: {COLORS.TEXT_PRIMARY_DARK};
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
                icon_widget = Icon(icon_name, size=IconSize.MENU.value)
                pix = icon_widget.pixmap()
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
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SIZE.SPLIT_BUTTON_SPACING)

        layout.addWidget(self._create_icon_label_button(main_icon, main_label, main_action))
        layout.addWidget(self._create_arrow_button(menu))
        self.setLayout(layout)
        w, h = ButtonSize.SPLIT_SMALL.value
        self.setFixedSize(w, h)

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
        large_w = ButtonSize.LARGE.value[0]
        icon_h = ButtonSize.ICON_LARGE.value[1]
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
    ) -> QToolButton:
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        if main_icon:
            icon_name = os.path.splitext(os.path.basename(main_icon))[0]
            pix = Icon(icon_name, size=IconSize.SMALL.value).pixmap()
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(IconSize.SMALL.value, IconSize.SMALL.value))
        btn.setText(main_label)
        w, h = ButtonSize.ICON_LABEL.value
        btn.setFixedSize(w, h)
        btn.clicked.connect(main_action)
        btn.setStyleSheet(Styles.small_icon_label_button())
        return btn

    def _create_arrow_button(self, menu: QMenu) -> QToolButton:
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.setText(Styles.ARROW_DOWN)
        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        w, h = ButtonSize.DROPDOWN_ARROW.value
        btn.setFixedSize(w, h)
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
            pix = Icon(icon_name, size=IconSize.LARGE.value).pixmap()
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(IconSize.LARGE.value, IconSize.LARGE.value))
        w, h = ButtonSize.ICON_LARGE.value
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
        large_w = ButtonSize.LARGE.value[0]
        btn.setFixedSize(large_w, SIZE.DROPDOWN_TEXT_HEIGHT)
        btn.setStyleSheet(Styles.dropdown_text_button())
        return btn
