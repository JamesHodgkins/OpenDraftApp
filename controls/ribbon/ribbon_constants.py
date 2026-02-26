"""
Constants and configuration for the Ribbon UI.

This module centralises all magic numbers, sizes, colours, and styling
constants used throughout the ribbon components for easy maintenance.
"""
from enum import Enum
from typing import NamedTuple


# ===== ENUMS =====

class ButtonType(Enum):
    """Enum representing different types of ribbon buttons."""
    LARGE = "large"
    SMALL = "small"
    SPLIT = "split"
    SPLIT_SMALL = "split-small"
    STACK = "stack"
    SELECT = "select"
    COLOR_PICKER = "color-picker"


class ButtonSize(Enum):
    """Standard button sizes used in the ribbon."""
    LARGE = (52, 64)
    SMALL = (72, 28)
    SPLIT_SMALL = (92, 28)
    ICON_LARGE = (52, 44)
    ICON_SMALL = (36, 28)
    DROPDOWN_ARROW = (20, 28)
    DROPDOWN_TEXT = (52, 20)
    ICON_LABEL = (72, 28)


class IconSize(Enum):
    """Standard icon sizes."""
    LARGE = 40
    SMALL = 24
    MENU = 24


# ===== SIZE CONSTANTS =====

class Sizing(NamedTuple):
    """Container for all sizing constants."""
    # Ribbon dimensions
    RIBBON_HEIGHT: int = 140

    # Button dimensions
    LARGE_BUTTON_WIDTH: int = 52
    LARGE_BUTTON_HEIGHT: int = 64
    SMALL_BUTTON_WIDTH: int = 72
    SMALL_BUTTON_HEIGHT: int = 28
    SPLIT_SMALL_WIDTH: int = 92

    # Icon dimensions
    LARGE_ICON_SIZE: int = 40
    SMALL_ICON_SIZE: int = 24
    LARGE_ICON_BUTTON_HEIGHT: int = 44
    LARGE_ICON_LABEL_SIZE: int = 48

    # Dropdown dimensions
    DROPDOWN_ARROW_WIDTH: int = 20
    DROPDOWN_TEXT_HEIGHT: int = 20

    # Spacing
    PANEL_SPACING: int = 6
    TOOL_SPACING: int = 4
    STACK_SPACING: int = 2
    SPLIT_BUTTON_SPACING: int = 2


SIZE = Sizing(
    RIBBON_HEIGHT=140,
    LARGE_BUTTON_WIDTH=52,
    LARGE_BUTTON_HEIGHT=64,
    SMALL_BUTTON_WIDTH=72,
    SMALL_BUTTON_HEIGHT=28,
    SPLIT_SMALL_WIDTH=92,
    LARGE_ICON_SIZE=40,
    SMALL_ICON_SIZE=24,
    LARGE_ICON_BUTTON_HEIGHT=44,
    LARGE_ICON_LABEL_SIZE=48,
    DROPDOWN_ARROW_WIDTH=20,
    DROPDOWN_TEXT_HEIGHT=20,
    PANEL_SPACING=6,
    TOOL_SPACING=4,
    STACK_SPACING=2,
    SPLIT_BUTTON_SPACING=2,
)


# ===== COLOR CONSTANTS =====

class Colors(NamedTuple):
    """Container for all colour constants."""
    BACKGROUND_DARK: str = "#2D2D2D"
    BACKGROUND_LIGHT: str = "#2D2D2D"
    HOVER_DARK: str = "rgba(255, 255, 255, 0.06)"
    HOVER_LIGHT: str = "rgba(0, 0, 0, 0.06)"
    PRESSED_DARK: str = "rgba(255, 255, 255, 0.12)"
    PRESSED_LIGHT: str = "rgba(0, 0, 0, 0.12)"
    TEXT_PRIMARY_DARK: str = "#eeeeee"
    TEXT_PRIMARY_LIGHT: str = "#000000"
    TEXT_SECONDARY_DARK: str = "#aaaaaa"
    TEXT_SECONDARY_LIGHT: str = "#666666"
    TEXT_PLACEHOLDER: str = "#888888"


COLORS = Colors(
    BACKGROUND_DARK="#2D2D2D",
    BACKGROUND_LIGHT="#2D2D2D",
    HOVER_DARK="rgba(255, 255, 255, 0.06)",
    HOVER_LIGHT="rgba(0, 0, 0, 0.06)",
    PRESSED_DARK="rgba(255, 255, 255, 0.12)",
    PRESSED_LIGHT="rgba(0, 0, 0, 0.12)",
    TEXT_PRIMARY_DARK="#eeeeee",
    TEXT_PRIMARY_LIGHT="#000000",
    TEXT_SECONDARY_DARK="#aaaaaa",
    TEXT_SECONDARY_LIGHT="#666666",
    TEXT_PLACEHOLDER="#888888",
)


# ===== STYLE CONSTANTS =====

class Styles:
    """Style templates for ribbon components."""

    FONT_SIZE_LARGE: int = 10
    FONT_SIZE_SMALL: int = 9
    BORDER_RADIUS_SMALL: int = 3
    BORDER_RADIUS_LARGE: int = 4
    PADDING_SMALL: int = 2
    PADDING_MEDIUM: int = 8
    ARROW_DOWN: str = "\u25BC"

    @staticmethod
    def button_base(dark: bool = False) -> str:
        return "border: none; background: transparent;"

    @staticmethod
    def button_hover(dark: bool = False) -> str:
        color = COLORS.HOVER_DARK if dark else COLORS.HOVER_LIGHT
        return f"background: {color};"

    @staticmethod
    def button_pressed(dark: bool = False) -> str:
        color = COLORS.PRESSED_DARK if dark else COLORS.PRESSED_LIGHT
        return f"background: {color};"

    @staticmethod
    def large_icon_button(dark: bool = False) -> str:
        return f"""
            QToolButton {{
                {Styles.button_base(dark)}
                padding: {Styles.PADDING_SMALL}px;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
                border-radius: {Styles.BORDER_RADIUS_LARGE}px;
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_LARGE}px;
            }}
        """

    @staticmethod
    def dropdown_text_button(dark: bool = False) -> str:
        return f"""
            QToolButton {{
                font-size: {Styles.FONT_SIZE_LARGE}px;
                font-weight: 500;
                {Styles.button_base(dark)}
                padding: 0 {Styles.PADDING_SMALL}px;
                text-align: center;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton::menu-indicator {{
                image: url(none);
                width: 0;
                height: 0;
            }}
        """

    @staticmethod
    def small_icon_label_button(dark: bool = False) -> str:
        return f"""
            QToolButton {{
                font-size: {Styles.FONT_SIZE_SMALL}px;
                font-weight: 500;
                {Styles.button_base(dark)}
                padding: 0 {Styles.PADDING_MEDIUM}px;
                text-align: left;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
            }}
        """

    @staticmethod
    def dropdown_arrow_button(dark: bool = False) -> str:
        return f"""
            QToolButton {{
                {Styles.button_base(dark)}
                padding: 0;
            }}
            QToolButton:hover {{
                {Styles.button_hover(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton:pressed {{
                {Styles.button_pressed(dark)}
                border-radius: {Styles.BORDER_RADIUS_SMALL}px;
            }}
            QToolButton::menu-indicator {{
                image: url(none);
                width: 0;
                height: 0;
            }}
        """

    @staticmethod
    def small_button(dark: bool = False) -> str:
        return f"""
            QPushButton {{
                font-size: {Styles.FONT_SIZE_SMALL}px;
                white-space: nowrap;
                text-align: left;
                padding-left: {Styles.PADDING_MEDIUM}px;
                min-width: {SIZE.SMALL_BUTTON_WIDTH}px;
                max-width: {SIZE.SMALL_BUTTON_WIDTH}px;
                min-height: {SIZE.SMALL_BUTTON_HEIGHT}px;
                max-height: {SIZE.SMALL_BUTTON_HEIGHT}px;
            }}
        """

    @staticmethod
    def panel_title(dark: bool = False) -> str:
        color = COLORS.TEXT_SECONDARY_DARK if dark else COLORS.TEXT_SECONDARY_LIGHT
        return f"""
            font-size: {Styles.FONT_SIZE_LARGE}px;
            color: {color};
            font-weight: normal;
            margin-top: {Styles.PADDING_SMALL}px;
            margin-bottom: 1px;
        """


# ===== MARGIN CONSTANTS =====

class Margins(NamedTuple):
    """Standard margin values."""
    NONE: tuple = (0, 0, 0, 0)
    SMALL: tuple = (2, 2, 2, 2)
    MEDIUM: tuple = (4, 4, 4, 4)


MARGINS = Margins(
    NONE=(0, 0, 0, 0),
    SMALL=(2, 2, 2, 2),
    MEDIUM=(4, 4, 4, 4),
)


# ===== PATH CONSTANTS =====

class Paths:
    """File path constants."""
    ASSETS_DIR = "assets"
    ICONS_DIR = "assets/icons"
    STYLESHEET_FILE = "assets/themes/ribbon.qss"

    @staticmethod
    def icon_path(icon_name: str, extension: str = "png") -> str:
        """Generate icon path from icon name."""
        return f"{Paths.ICONS_DIR}/{icon_name}.{extension}"
