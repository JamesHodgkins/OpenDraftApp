"""
Factory module for creating ribbon buttons and controls.

Provides a clean factory pattern for building typed ribbon UI components,
keeping the creation logic separate from the configuration data.
"""
from typing import Callable, Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QToolButton, QComboBox, QStyle, QStyleOption,
)
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QIcon, QPainter, QColor, QPen, QBrush

from controls.ribbon.ribbon_constants import (
    ButtonType, SIZE, Styles, MARGINS, COLORS,
)
from controls.ribbon.ribbon_models import (
    ToolDefinition, SplitButtonDefinition, StackDefinition,
    LayerSelectDefinition, PropStackDefinition,
)
from controls.ribbon.ribbon_split_button import RibbonSplitButton
from controls.icon_widget import Icon, load_pixmap

__all__ = [
    "ColorSwatchButton",
    "RibbonLargeButton",
    "ButtonFactory",
    "PanelFactory",
]

__all__ = [
    "ColorSwatchButton",
    "RibbonLargeButton",
    "ButtonFactory",
    "PanelFactory",
]


_PROP_LABEL_STYLE = f"color: {COLORS.MUTED_TEXT}; font-size: 8pt; padding: 0;"
_LARGE_BUTTON_ICON_TEXT_GAP = 8
_SWATCH_CIRCLE_SIZE = 10  # diameter of the colour circle inside the button
# Maps PropStackRow.label → QWidget objectName used by RibbonPanel.setup_document()
_PROP_OBJ_NAMES: dict[str, str] = {
    "Color": "colorSwatchBtn",
    "Style": "lineStyleCombo",
    "Weight": "thicknessCombo",
}


class ColorSwatchButton(QPushButton):
    """Wide ribbon color control: colored circle + hex label, styled like combo boxes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hex_color: Optional[str] = None  # None = "by layer"
        self.setFixedSize(110, 22)
        self.setStyleSheet(
            f"QPushButton {{ background: {COLORS.CONTROL_BG}; color: {COLORS.CONTROL_TEXT};"
            f" border: 1px solid {COLORS.CONTROL_BORDER};"
            f" border-radius: 3px; padding: 0; font-size: 9pt; }}"
            f"QPushButton:hover {{ background: {COLORS.HOVER_DARK}; }}"
            f"QPushButton:pressed {{ background: {COLORS.BACKGROUND_DARK}; }}"
        )

    def set_color(self, hex_color: Optional[str]) -> None:
        self._hex_color = hex_color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.rect()
        circle_d = _SWATCH_CIRCLE_SIZE
        cx = 8 + circle_d // 2  # left margin + radius
        cy = r.height() // 2

        if self._hex_color:
            fill = QColor(self._hex_color)
        else:
            fill = QColor(COLORS.CONTROL_BG)

        painter.setPen(QPen(QColor(COLORS.SWATCH_OUTLINE), 1))
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(cx - circle_d // 2, cy - circle_d // 2, circle_d, circle_d)

        label = self._hex_color.upper() if self._hex_color else "— by layer —"
        text_x = cx + circle_d // 2 + 6
        painter.setPen(QColor(COLORS.CONTROL_TEXT))
        painter.setFont(self.font())
        painter.drawText(QRect(text_x, 0, r.width() - text_x - 2, r.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, label)
        painter.end()


class RibbonLargeButton(QToolButton):
    """QToolButton variant with explicit icon/label spacing for ribbon large buttons."""

    def __init__(self, icon_text_gap: int = _LARGE_BUTTON_ICON_TEXT_GAP, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_text_gap = icon_text_gap

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PE_Widget, option, painter, self)

        content_rect = self.rect().adjusted(2, 2, -2, -2)
        icon_rect = QRect(
            (self.width() - self.iconSize().width()) // 2,
            content_rect.top() + 1,
            self.iconSize().width(),
            self.iconSize().height(),
        )

        if not self.icon().isNull():
            mode = QIcon.Normal if self.isEnabled() else QIcon.Disabled
            state = QIcon.On if self.isDown() else QIcon.Off
            pixmap = self.icon().pixmap(self.iconSize(), mode, state)
            painter.drawPixmap(icon_rect, pixmap)

        text_rect = QRect(
            content_rect.left(),
            icon_rect.bottom() + self._icon_text_gap,
            content_rect.width(),
            max(0, content_rect.bottom() - (icon_rect.bottom() + self._icon_text_gap) + 1),
        )
        painter.setPen(self.palette().buttonText().color())
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.text())
        painter.end()


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
        elif bt == ButtonType.LAYER_SELECT.value:
            return self._create_layer_select(tool)
        elif bt == ButtonType.PROP_STACK.value:
            return self._create_prop_stack(tool)
        else:
            return self._create_large_button(tool)

    # ------------------------------------------------------------------
    # Individual builders
    # ------------------------------------------------------------------

    def _create_large_button(self, tool: ToolDefinition) -> QWidget:
        # Use QToolButton with icon-over-text so QSS hover/pressed rules apply
        btn = RibbonLargeButton()
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        if tool.icon:
            pix = load_pixmap(tool.icon, SIZE.LARGE_ICON_SIZE)
            if pix and not pix.isNull():
                btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(SIZE.LARGE_ICON_SIZE, SIZE.LARGE_ICON_SIZE))
        btn.setText(tool.label)
        btn.setFixedSize(SIZE.LARGE_BUTTON_WIDTH, SIZE.LARGE_BUTTON_HEIGHT)
        btn.setStyleSheet(Styles.large_button(self.dark))
        if tool.action:
            btn.clicked.connect(self._get_action_callback(tool.action))
        return btn

    def _create_small_button(self, tool: ToolDefinition) -> QPushButton:
        btn = QPushButton()
        btn.setText(tool.label)
        if tool.icon:
            pix = load_pixmap(tool.icon, SIZE.SMALL_ICON_SIZE)
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

    _MAX_STACK_ROWS = 3

    def _create_stack(self, tool: ToolDefinition) -> QWidget:
        if not isinstance(tool, StackDefinition):
            raise ValueError("Stack requires StackDefinition")

        stack_widget = QWidget()
        stack_layout = QHBoxLayout()
        stack_layout.setSpacing(SIZE.TOOL_SPACING)
        stack_layout.setContentsMargins(*MARGINS.NONE)

        for column in tool.columns:
            # Auto-chunk columns with more than 3 items into groups of 3,
            # matching the standard Office / AutoCAD ribbon row limit.
            for chunk in self._chunk(column, self._MAX_STACK_ROWS):
                col_widget = QWidget()
                col_layout = QVBoxLayout()
                col_layout.setSpacing(SIZE.STACK_SPACING)
                col_layout.setContentsMargins(*MARGINS.NONE)
                for btn_def in chunk:
                    col_layout.addWidget(
                        self._create_small_button(btn_def),
                        alignment=Qt.AlignLeft | Qt.AlignTop,
                    )
                col_layout.addStretch()
                col_widget.setLayout(col_layout)
                stack_layout.addWidget(col_widget, alignment=Qt.AlignTop)

        stack_widget.setLayout(stack_layout)
        return stack_widget

    @staticmethod
    def _chunk(lst: list, n: int) -> list:
        """Split *lst* into sub-lists of at most *n* items."""
        return [lst[i:i + n] for i in range(0, len(lst), n)]

    def _create_layer_select(self, tool: ToolDefinition) -> QWidget:
        """Build a labeled layer-selection combo.

        Sets ``objectName='layerSelectCombo'`` on the inner :class:`QComboBox`
        so that :meth:`RibbonPanel.setup_document` can locate and wire it.
        """
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(2)

        lbl = QLabel(tool.label or "Layer")
        lbl.setStyleSheet(_PROP_LABEL_STYLE)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        vbox.addWidget(lbl)

        combo = QComboBox()
        combo.setObjectName("layerSelectCombo")
        combo.setFixedWidth(130)
        combo.setFixedHeight(22)
        combo.setStyleSheet(Styles.combo_style())
        combo.setMaxVisibleItems(12)
        vbox.addWidget(combo)
        vbox.addStretch()
        return container

    def _create_prop_stack(self, tool: ToolDefinition) -> QWidget:
        """Build a vertical stack of property-override controls.

        Object names assigned (for :meth:`RibbonPanel.setup_document`):
            ``colorSwatchBtn``, ``lineStyleCombo``, ``thicknessCombo``.
        """
        if not isinstance(tool, PropStackDefinition):
            raise ValueError("Prop stack requires PropStackDefinition")

        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 2, 4)
        vbox.setSpacing(6)

        for row in tool.rows:
            obj_name = _PROP_OBJ_NAMES.get(row.label, "")

            row_w = QWidget()
            row_w.setFixedHeight(24)
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 1, 0, 1)
            row_h.setSpacing(3)

            lbl = QLabel(row.label)
            lbl.setStyleSheet(_PROP_LABEL_STYLE)
            lbl.setFixedWidth(38)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_h.addWidget(lbl)

            if row.type == "color-swatch":
                btn = ColorSwatchButton()
                btn.setObjectName(obj_name)
                btn.setToolTip("Override colour (click to change, blank = use layer colour)")
                row_h.addWidget(btn)
            else:
                combo = QComboBox()
                combo.setObjectName(obj_name)
                combo.addItem("\u2014 by layer \u2014")
                for opt in row.options:
                    combo.addItem(opt)
                combo.setFixedHeight(22)
                combo.setFixedWidth(110)
                combo.setStyleSheet(Styles.combo_style())
                row_h.addWidget(combo)

            vbox.addWidget(row_w)

        vbox.addStretch()
        return container

    @staticmethod
    def _set_placeholder_icon(label: QLabel) -> None:
        label.setText("?")
        label.setStyleSheet(f"color: {COLORS.SWATCH_OUTLINE}; font-size: 13pt;")


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
                    layout.addWidget(
                        self._create_small_button_column(small_buttons),
                        alignment=Qt.AlignTop,
                    )
                    small_buttons = []
                layout.addWidget(self.button_factory.create_button(tool), alignment=Qt.AlignTop)

        if small_buttons:
            layout.addWidget(
                self._create_small_button_column(small_buttons),
                alignment=Qt.AlignTop,
            )

        content.setLayout(layout)
        return content

    @staticmethod
    def _create_small_button_column(buttons: List[QWidget]) -> QWidget:
        """Stack buttons vertically, auto-chunking into columns of 3."""
        if len(buttons) <= ButtonFactory._MAX_STACK_ROWS:
            col = QWidget()
            vbox = QVBoxLayout()
            vbox.setSpacing(SIZE.STACK_SPACING)
            vbox.setContentsMargins(*MARGINS.NONE)
            for btn in buttons:
                vbox.addWidget(btn, alignment=Qt.AlignLeft | Qt.AlignTop)
            vbox.addStretch()
            col.setLayout(vbox)
            return col

        # More than 3 buttons — wrap into side-by-side columns of 3.
        wrapper = QWidget()
        hbox = QHBoxLayout()
        hbox.setSpacing(SIZE.TOOL_SPACING)
        hbox.setContentsMargins(*MARGINS.NONE)
        for chunk in ButtonFactory._chunk(buttons, ButtonFactory._MAX_STACK_ROWS):
            col = QWidget()
            vbox = QVBoxLayout()
            vbox.setSpacing(SIZE.STACK_SPACING)
            vbox.setContentsMargins(*MARGINS.NONE)
            for btn in chunk:
                vbox.addWidget(btn, alignment=Qt.AlignLeft | Qt.AlignTop)
            vbox.addStretch()
            col.setLayout(vbox)
            hbox.addWidget(col, alignment=Qt.AlignTop)
        wrapper.setLayout(hbox)
        return wrapper
