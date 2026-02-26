"""
Factory module for creating ribbon buttons and controls.

Provides a clean factory pattern for building typed ribbon UI components,
keeping the creation logic separate from the configuration data.
"""
from typing import Callable, Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QToolButton,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from controls.ribbon.ribbon_constants import (
    ButtonType, ButtonSize, IconSize, SIZE, Styles, MARGINS,
)
from controls.ribbon.ribbon_models import ToolDefinition, SplitButtonDefinition, StackDefinition
from controls.ribbon.ribbon_split_button import RibbonSplitButton
from controls.icon_widget import Icon


class ButtonFactory:
    """Factory for creating individual ribbon button widgets."""

    def __init__(self, dark: bool = False, action_handler: Optional[Callable] = None):
        self.dark = dark
        self.action_handler = action_handler or self._default_action_handler

    @staticmethod
    def _default_action_handler(action: str) -> None:
        print(f"Action: {action}")

    def _get_action_callback(self, action: str) -> Callable:
        return lambda: self.action_handler(action)

    def create_button(self, tool: ToolDefinition) -> QWidget:
        """Dispatch to the correct builder based on *tool.type*."""
        bt = tool.type
        if bt == ButtonType.LARGE.value:
            return self._create_large_button(tool)
        elif bt == ButtonType.SMALL.value:
            return self._create_small_button(tool)
        elif bt == ButtonType.SPLIT.value:
            return self._create_split_button(tool, large=True)
        elif bt == ButtonType.SPLIT_SMALL.value:
            return self._create_split_button(tool, large=False)
        elif bt == ButtonType.STACK.value:
            return self._create_stack(tool)
        else:
            return self._create_large_button(tool)

    # ------------------------------------------------------------------
    # Individual builders
    # ------------------------------------------------------------------

    def _create_large_button(self, tool: ToolDefinition) -> QWidget:
        btn_widget = QWidget()
        vbox = QVBoxLayout()
        vbox.setSpacing(0)
        vbox.setContentsMargins(0, 2, 0, 2)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(SIZE.LARGE_ICON_LABEL_SIZE, SIZE.LARGE_ICON_LABEL_SIZE)
        if tool.icon:
            pix = Icon(tool.icon, size=SIZE.LARGE_ICON_SIZE).pixmap()
            if pix and not pix.isNull():
                icon_label.setPixmap(pix)
            else:
                self._set_placeholder_icon(icon_label)
        vbox.addWidget(icon_label, alignment=Qt.AlignHCenter)

        text_label = QLabel(tool.label)
        text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        text_label.setStyleSheet(
            f"font-size: {Styles.FONT_SIZE_SMALL}px; "
            "color: #eee; margin-top: 0px; margin-bottom: 0px;"
        )
        vbox.addWidget(text_label, alignment=Qt.AlignHCenter)

        btn_widget.setLayout(vbox)
        btn_widget.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
        btn_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        btn = QPushButton(btn_widget)
        btn.setFlat(True)
        btn.setStyleSheet("QPushButton { background: transparent; border: none; }")
        btn.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
        if tool.action:
            btn.clicked.connect(self._get_action_callback(tool.action))
        btn.raise_()

        return btn_widget

    def _create_small_button(self, tool: ToolDefinition) -> QPushButton:
        btn = QPushButton()
        btn.setText(tool.label)
        if tool.icon:
            pix = Icon(tool.icon, size=SIZE.SMALL_ICON_SIZE).pixmap()
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
                btn.setIconSize(QSize(SIZE.SMALL_ICON_SIZE, SIZE.SMALL_ICON_SIZE))
        btn.setFixedSize(SIZE.SMALL_BUTTON_WIDTH, SIZE.SMALL_BUTTON_HEIGHT)
        btn.setStyleSheet(Styles.small_button(self.dark))
        if tool.action:
            btn.clicked.connect(self._get_action_callback(tool.action))
        return btn

    def _create_split_button(
        self, tool: ToolDefinition, large: bool = True
    ) -> RibbonSplitButton:
        if not isinstance(tool, SplitButtonDefinition):
            raise ValueError("Split button requires SplitButtonDefinition")

        main_icon = (
            f"assets/icons/{tool.items[0].icon}.png"
            if tool.items and tool.items[0].icon
            else None
        )
        menu_items = [
            {
                "label": item.label,
                "action": self._get_action_callback(item.action),
                **({"icon": f"assets/icons/{item.icon}.png"} if item.icon else {}),
            }
            for item in tool.items
        ]
        main_action_name = tool.mainAction or tool.action or tool.label
        return RibbonSplitButton(
            main_icon=main_icon,
            main_label=tool.label,
            items=menu_items,
            main_action=self._get_action_callback(main_action_name),
            small=not large,
        )

    def _create_stack(self, tool: ToolDefinition) -> QWidget:
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
                temp = ToolDefinition(
                    label=btn_def["label"],
                    type=btn_def.get("type", "small"),
                    icon=btn_def.get("icon"),
                    action=btn_def.get("action"),
                )
                col_layout.addWidget(self._create_small_button(temp), alignment=Qt.AlignLeft)
            col_layout.addStretch()
            col_widget.setLayout(col_layout)
            stack_layout.addWidget(col_widget)

        stack_widget.setLayout(stack_layout)
        return stack_widget

    @staticmethod
    def _set_placeholder_icon(label: QLabel) -> None:
        label.setText("?")
        label.setStyleSheet("color: #888; font-size: 18px;")


class PanelFactory:
    """Factory for creating ribbon panel content widgets."""

    def __init__(self, dark: bool = False, action_handler: Optional[Callable] = None):
        self.dark = dark
        self.button_factory = ButtonFactory(dark=dark, action_handler=action_handler)

    def create_panel_content(self, tools: List[ToolDefinition]) -> QWidget:
        """Return a horizontal QWidget containing all tool buttons."""
        content = QWidget()
        content.setProperty("dark", self.dark)
        layout = QHBoxLayout()
        layout.setSpacing(SIZE.TOOL_SPACING)
        layout.setContentsMargins(*MARGINS.SMALL)

        small_buttons: List[QWidget] = []

        for tool in tools:
            if tool.type in [ButtonType.SMALL.value, ButtonType.SPLIT_SMALL.value]:
                small_buttons.append(self.button_factory.create_button(tool))
            else:
                if small_buttons:
                    layout.addWidget(self._create_small_button_column(small_buttons))
                    small_buttons = []
                layout.addWidget(self.button_factory.create_button(tool))

        if small_buttons:
            layout.addWidget(self._create_small_button_column(small_buttons))

        content.setLayout(layout)
        return content

    @staticmethod
    def _create_small_button_column(buttons: List[QWidget]) -> QWidget:
        col = QWidget()
        vbox = QVBoxLayout()
        vbox.setSpacing(SIZE.STACK_SPACING)
        vbox.setContentsMargins(*MARGINS.NONE)
        for btn in buttons:
            vbox.addWidget(btn, alignment=Qt.AlignLeft)
        vbox.addStretch()
        col.setLayout(vbox)
        return col
