"""
Ribbon Split Button Component.

This module provides a split button widget that can display in two modes:
- Large: Vertically stacked icon button and text dropdown
- Small: Horizontally arranged icon+label button and dropdown arrow
"""
from typing import List, Dict, Any, Callable, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QMenu, QHBoxLayout
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize
import os
from IconWidget import Icon
from ribbon_constants import SIZE, Styles, ButtonSize, IconSize


class RibbonSplitButton(QWidget):
    """
    A split button widget for the ribbon interface.
    
    Large mode:
      - Top: Icon-only button that triggers the main action
      - Bottom: Text button with dropdown arrow that opens the menu
    
    Small mode:
      - Left: Icon and label button that triggers the main action
      - Right: Dropdown arrow button that opens the menu
    
    Attributes:
        main_icon: Path to the icon file
        main_label: Text label for the button
        items: List of menu items
        main_action: Callback for the main button action
        small: Whether to use small mode layout
    """
    
    def __init__(
        self,
        main_icon: Optional[str],
        main_label: str,
        items: List[Dict[str, Any]],
        main_action: Callable,
        parent: Optional[QWidget] = None,
        small: bool = False
    ):
        """
        Initialize the split button.
        
        Args:
            main_icon: Path to the icon file for the button
            main_label: Text label displayed on the button
            items: List of dictionaries defining menu items with 'label', 'action', and optional 'icon'
            main_action: Callback function triggered when main button is clicked
            parent: Optional parent widget
            small: If True, uses horizontal small layout; if False, uses vertical large layout
        """
        super().__init__(parent)

        # Build shared menu
        menu = self._build_menu(items)
        
        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if small:
            self._create_small_layout(layout, menu, main_icon, main_label, main_action)
        else:
            self._create_large_layout(layout, menu, main_icon, main_label, main_action)
    
    def _build_menu(self, items: List[Dict[str, Any]]) -> QMenu:
        """
        Build the dropdown menu from item definitions.
        
        Args:
            items: List of menu item definitions
            
        Returns:
            QMenu populated with the defined items
        """
        menu = QMenu(self)
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
    
    def _create_small_layout(
        self,
        layout: QHBoxLayout,
        menu: QMenu,
        main_icon: Optional[str],
        main_label: str,
        main_action: Callable
    ) -> None:
        """
        Create the small (horizontal) layout with two separate buttons.
        
        Args:
            layout: Layout to add widgets to
            menu: Dropdown menu to attach
            main_icon: Path to main icon
            main_label: Label text
            main_action: Callback for main action
        """
        # Two separate buttons: one for icon+label, one for dropdown arrow
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SIZE.SPLIT_BUTTON_SPACING)

        # Icon + Label button
        icon_label_btn = self._create_icon_label_button(main_icon, main_label, main_action)
        
        # Dropdown arrow button
        arrow_btn = self._create_arrow_button(menu)

        layout.addWidget(icon_label_btn)
        layout.addWidget(arrow_btn)
        self.setLayout(layout)
        button_size = ButtonSize.SPLIT_SMALL.value
        self.setFixedSize(button_size[0], button_size[1])
    
    def _create_large_layout(
        self,
        layout: QVBoxLayout,
        menu: QMenu,
        main_icon: Optional[str],
        main_label: str,
        main_action: Callable
    ) -> None:
        """
        Create the large (vertical) layout with icon button on top and text dropdown below.
        
        Args:
            layout: Layout to add widgets to
            menu: Dropdown menu to attach
            main_icon: Path to main icon
            main_label: Label text
            main_action: Callback for main action
        """
        # Large 2-part layout: icon-only button on top, text dropdown below (vertical alignment)

        # Top: icon-only action button
        icon_btn = self._create_large_icon_button(main_icon, main_action)
        
        # Bottom: text label that opens menu on click
        drop_btn = self._create_dropdown_text_button(main_label, menu)

        layout.addWidget(icon_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(drop_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.setLayout(layout)
        button_size = ButtonSize.LARGE.value
        self.setFixedSize(button_size[0], button_size[1])
    
    def _create_icon_label_button(
        self,
        main_icon: Optional[str],
        main_label: str,
        main_action: Callable
    ) -> QToolButton:
        """
        Create a button with icon and label for small layout.
        
        Args:
            main_icon: Path to icon file
            main_label: Button text
            main_action: Click callback
            
        Returns:
            Configured QToolButton
        """
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        if main_icon:
            icon_name = os.path.splitext(os.path.basename(main_icon))[0]
            icon_widget = Icon(icon_name, size=IconSize.SMALL.value)
            pix = icon_widget.pixmap()
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(IconSize.SMALL.value, IconSize.SMALL.value))
        btn.setText(main_label)
        button_size = ButtonSize.ICON_LABEL.value
        btn.setFixedSize(button_size[0], button_size[1])
        btn.clicked.connect(main_action)
        btn.setStyleSheet(Styles.small_icon_label_button())
        return btn
    
    def _create_arrow_button(self, menu: QMenu) -> QToolButton:
        """
        Create a dropdown arrow button.
        
        Args:
            menu: Menu to attach to button
            
        Returns:
            Configured QToolButton
        """
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.setText(Styles.ARROW_DOWN)
        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button_size = ButtonSize.DROPDOWN_ARROW.value
        btn.setFixedSize(button_size[0], button_size[1])
        btn.setStyleSheet(Styles.dropdown_arrow_button())
        return btn
    
    def _create_large_icon_button(
        self,
        main_icon: Optional[str],
        main_action: Callable
    ) -> QToolButton:
        """
        Create a large icon-only button.
        
        Args:
            main_icon: Path to icon file
            main_action: Click callback
            
        Returns:
            Configured QToolButton
        """
        btn = QToolButton(self)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        if main_icon:
            icon_name = os.path.splitext(os.path.basename(main_icon))[0]
            icon_widget = Icon(icon_name, size=IconSize.LARGE.value)
            pix = icon_widget.pixmap()
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(IconSize.LARGE.value, IconSize.LARGE.value))
        button_size = ButtonSize.ICON_LARGE.value
        btn.setFixedSize(button_size[0], button_size[1])
        btn.clicked.connect(main_action)
        btn.setStyleSheet(Styles.large_icon_button())
        return btn
    
    def _create_dropdown_text_button(self, main_label: str, menu: QMenu) -> QToolButton:
        """
        Create a text button with dropdown menu.
        
        Args:
            main_label: Button text
            menu: Menu to attach
            
        Returns:
            Configured QToolButton
        """
        btn = QToolButton(self)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setText(f"{main_label} {Styles.ARROW_DOWN}")
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setMenu(menu)
        button_size = (ButtonSize.LARGE.value[0], SIZE.DROPDOWN_TEXT_HEIGHT)
        btn.setFixedSize(button_size[0], button_size[1])
        btn.setStyleSheet(Styles.dropdown_text_button())
        return btn

