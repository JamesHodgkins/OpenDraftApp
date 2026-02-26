"""
Factory module for creating ribbon buttons and controls.

This module provides a clean factory pattern for creating various types
of ribbon UI components while maintaining consistency and reducing code duplication.
"""
from typing import Callable, Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSizePolicy, QToolButton
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from ribbon_constants import (
    ButtonType, ButtonSize, IconSize, SIZE, Styles, MARGINS
)
from ribbon_models import ToolDefinition, SplitButtonDefinition, StackDefinition
from RibbonSplitButton import RibbonSplitButton
from IconWidget import Icon


class ButtonFactory:
    """Factory class for creating ribbon buttons."""
    
    def __init__(self, dark: bool = False, action_handler: Optional[Callable] = None):
        """
        Initialize the button factory.
        
        Args:
            dark: Whether to use dark mode styling
            action_handler: Optional callback for handling button actions
        """
        self.dark = dark
        self.action_handler = action_handler or self._default_action_handler
    
    @staticmethod
    def _default_action_handler(action: str) -> None:
        """Default action handler that prints the action name."""
        print(f"Action: {action}")
    
    def _get_action_callback(self, action: str) -> Callable:
        """Create a callback function for the given action."""
        return lambda: self.action_handler(action)
    
    def create_button(self, tool: ToolDefinition) -> QWidget:
        """
        Create a button widget based on the tool definition.
        
        Args:
            tool: The tool definition describing the button to create
            
        Returns:
            QWidget representing the button
        """
        button_type = tool.type
        
        if button_type == ButtonType.LARGE.value:
            return self._create_large_button(tool)
        elif button_type == ButtonType.SMALL.value:
            return self._create_small_button(tool)
        elif button_type == ButtonType.SPLIT.value:
            return self._create_split_button(tool, large=True)
        elif button_type == ButtonType.SPLIT_SMALL.value:
            return self._create_split_button(tool, large=False)
        elif button_type == ButtonType.STACK.value:
            return self._create_stack(tool)
        else:
            # Fallback to large button
            return self._create_large_button(tool)
    
    def _create_large_button(self, tool: ToolDefinition) -> QWidget:
        """
        Create a large button with icon and label.
        
        Args:
            tool: Tool definition containing button properties
            
        Returns:
            QWidget containing the large button
        """
        btn_widget = QWidget()
        vbox = QVBoxLayout()
        vbox.setSpacing(0)
        vbox.setContentsMargins(*MARGINS.NONE)
        vbox.setContentsMargins(0, 2, 0, 2)
        
        # Icon label
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(SIZE.LARGE_ICON_LABEL_SIZE, SIZE.LARGE_ICON_LABEL_SIZE)
        
        if tool.icon:
            icon = Icon(tool.icon, size=SIZE.LARGE_ICON_SIZE)
            pix = icon.pixmap()
            if pix and not pix.isNull():
                icon_label.setPixmap(pix)
            else:
                self._set_placeholder_icon(icon_label)
        
        vbox.addWidget(icon_label, alignment=Qt.AlignHCenter)
        
        # Text label
        text_label = QLabel(tool.label)
        text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        text_label.setStyleSheet(
            f"font-size: {Styles.FONT_SIZE_SMALL}px; "
            f"color: #eee; margin-top: 0px; margin-bottom: 0px;"
        )
        vbox.addWidget(text_label, alignment=Qt.AlignHCenter)
        
        btn_widget.setLayout(vbox)
        btn_widget.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
        btn_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Overlay transparent button for click handling
        btn = QPushButton(btn_widget)
        btn.setFlat(True)
        btn.setStyleSheet("QPushButton { background: transparent; border: none; }")
        btn.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
        
        if tool.action:
            btn.clicked.connect(self._get_action_callback(tool.action))
        
        btn.raise_()
        
        return btn_widget
    
    def _create_small_button(self, tool: ToolDefinition) -> QPushButton:
        """
        Create a small button with icon and text.
        
        Args:
            tool: Tool definition containing button properties
            
        Returns:
            QPushButton configured as a small button
        """
        btn = QPushButton()
        btn.setText(tool.label)
        
        if tool.icon:
            icon = Icon(tool.icon, size=SIZE.SMALL_ICON_SIZE)
            pix = icon.pixmap()
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
                btn.setIconSize(QSize(28, 20))
        
        btn.setFixedSize(SIZE.SMALL_BUTTON_WIDTH, SIZE.SMALL_BUTTON_HEIGHT)
        btn.setStyleSheet(Styles.small_button(self.dark))
        
        if tool.action:
            btn.clicked.connect(self._get_action_callback(tool.action))
        
        return btn
    
    def _create_split_button(self, tool: ToolDefinition, large: bool = True) -> RibbonSplitButton:
        """
        Create a split button with dropdown menu.
        
        Args:
            tool: SplitButtonDefinition containing button properties
            large: Whether to create a large or small split button
            
        Returns:
            RibbonSplitButton widget
        """
        if not isinstance(tool, SplitButtonDefinition):
            raise ValueError("Split button requires SplitButtonDefinition")
        
        # Get main icon from first item if available
        main_icon = None
        if tool.items and tool.items[0].icon:
            main_icon = f"assets/icons/{tool.items[0].icon}.png"
        
        # Convert menu items to format expected by RibbonSplitButton
        menu_items = []
        for item in tool.items:
            menu_item = {
                "label": item.label,
                "action": self._get_action_callback(item.action)
            }
            if item.icon:
                menu_item["icon"] = f"assets/icons/{item.icon}.png"
            menu_items.append(menu_item)
        
        # Get main action
        main_action_name = tool.mainAction or tool.action or tool.label
        main_action = self._get_action_callback(main_action_name)
        
        return RibbonSplitButton(
            main_icon=main_icon,
            main_label=tool.label,
            items=menu_items,
            main_action=main_action,
            small=not large
        )
    
    def _create_stack(self, tool: ToolDefinition) -> QWidget:
        """
        Create a stacked group of buttons.
        
        Args:
            tool: StackDefinition containing stack properties
            
        Returns:
            QWidget containing the stacked buttons
        """
        if not isinstance(tool, StackDefinition):
            raise ValueError("Stack requires StackDefinition")
        
        stack_widget = QWidget()
        stack_layout = QHBoxLayout()
        stack_layout.setSpacing(SIZE.TOOL_SPACING)
        stack_layout.setContentsMargins(*MARGINS.NONE)
        
        for column in tool.columns:
            col_widget = QWidget()
            col_layout = QVBoxLayout()
            col_layout.setSpacing(SIZE.STACK_SPACING)
            col_layout.setContentsMargins(*MARGINS.NONE)
            
            for btn_def in column:
                # Create a temporary ToolDefinition for each button
                temp_tool = ToolDefinition(
                    label=btn_def["label"],
                    type=btn_def.get("type", "small"),
                    icon=btn_def.get("icon"),
                    action=btn_def.get("action")
                )
                btn = self._create_small_button(temp_tool)
                col_layout.addWidget(btn, alignment=Qt.AlignLeft)
            
            col_layout.addStretch()
            col_widget.setLayout(col_layout)
            stack_layout.addWidget(col_widget)
        
        stack_widget.setLayout(stack_layout)
        return stack_widget
    
    @staticmethod
    def _set_placeholder_icon(label: QLabel) -> None:
        """Set a placeholder icon when icon file is not found."""
        label.setText('?')
        label.setStyleSheet('color: #888; font-size: 18px;')


class PanelFactory:
    """Factory class for creating ribbon panels."""
    
    def __init__(self, dark: bool = False, action_handler: Optional[Callable] = None):
        """
        Initialize the panel factory.
        
        Args:
            dark: Whether to use dark mode styling
            action_handler: Optional callback for handling button actions
        """
        self.dark = dark
        self.button_factory = ButtonFactory(dark=dark, action_handler=action_handler)
    
    def create_panel_content(self, tools: List[ToolDefinition]) -> QWidget:
        """
        Create the content widget for a panel containing multiple tools.
        
        Args:
            tools: List of tool definitions to include in the panel
            
        Returns:
            QWidget containing all the tools
        """
        content = QWidget()
        content.setProperty("dark", self.dark)
        layout = QHBoxLayout()
        layout.setSpacing(SIZE.TOOL_SPACING)
        layout.setContentsMargins(*MARGINS.SMALL)
        
        small_buttons = []
        
        for tool in tools:
            # Collect small buttons and split-small buttons to stack them
            if tool.type in [ButtonType.SMALL.value, ButtonType.SPLIT_SMALL.value]:
                button = self.button_factory.create_button(tool)
                small_buttons.append(button)
            else:
                # Add any accumulated small buttons first
                if small_buttons:
                    small_col = self._create_small_button_column(small_buttons)
                    layout.addWidget(small_col)
                    small_buttons = []
                
                # Add the current tool
                button = self.button_factory.create_button(tool)
                layout.addWidget(button)
        
        # Add any remaining small buttons
        if small_buttons:
            small_col = self._create_small_button_column(small_buttons)
            layout.addWidget(small_col)
        
        content.setLayout(layout)
        return content
    
    @staticmethod
    def _create_small_button_column(buttons: List[QWidget]) -> QWidget:
        """
        Create a vertical column of small buttons.
        
        Args:
            buttons: List of button widgets to stack vertically
            
        Returns:
            QWidget containing the stacked buttons
        """
        col_widget = QWidget()
        vbox = QVBoxLayout()
        vbox.setSpacing(SIZE.STACK_SPACING)
        vbox.setContentsMargins(*MARGINS.NONE)
        
        for btn in buttons:
            vbox.addWidget(btn, alignment=Qt.AlignLeft)
        
        vbox.addStretch()
        col_widget.setLayout(vbox)
        return col_widget
