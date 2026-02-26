# Ribbon UI Quick Reference Guide

## Common Tasks

### Changing Button Sizes

**File**: `ribbon_constants.py`

```python
SIZE = Sizing(
    RIBBON_HEIGHT=140,           # Overall ribbon height
    LARGE_BUTTON_WIDTH=52,       # Large button width
    LARGE_BUTTON_HEIGHT=64,      # Large button height
    SMALL_BUTTON_WIDTH=72,       # Small button width
    SMALL_BUTTON_HEIGHT=28,      # Small button height
    SPLIT_SMALL_WIDTH=92,        # Small split button total width
    LARGE_ICON_SIZE=40,          # Large icon size in pixels
    SMALL_ICON_SIZE=24,          # Small icon size in pixels
    PANEL_SPACING=6,             # Space between panels
    TOOL_SPACING=4,              # Space between tools
    STACK_SPACING=2,             # Space between stacked buttons
)
```

### Changing Colors

**File**: `ribbon_constants.py`

```python
COLORS = Colors(
    BACKGROUND_DARK="#2D2D2D",                  # Dark mode background
    BACKGROUND_LIGHT="#F0F0F0",                 # Light mode background
    HOVER_DARK="rgba(255, 255, 255, 0.06)",    # Dark mode hover
    HOVER_LIGHT="rgba(0, 0, 0, 0.06)",         # Light mode hover
    PRESSED_DARK="rgba(255, 255, 255, 0.12)",  # Dark mode pressed
    PRESSED_LIGHT="rgba(0, 0, 0, 0.12)",       # Light mode pressed
    TEXT_PRIMARY_DARK="#eeeeee",                # Dark mode text
    TEXT_SECONDARY_DARK="#aaaaaa",              # Dark mode labels
)
```

### Adding a New Tool/Button

**File**: `main.py`

Add to appropriate panel in `panel_definitions`:

```python
# Large button
{"label": "My Tool", "icon": "my_icon", "type": "large", "action": "myAction"}

# Small button
{"label": "My Tool", "icon": "my_icon", "type": "small", "action": "myAction"}

# Split button (large)
{
    "label": "My Tool",
    "type": "split",
    "mainAction": "defaultAction",
    "items": [
        {"label": "Option 1", "icon": "icon1", "action": "action1"},
        {"label": "Option 2", "icon": "icon2", "action": "action2"}
    ]
}

# Split button (small)
{
    "label": "My Tool",
    "type": "split-small",
    "mainAction": "defaultAction",
    "items": [...]
}

# Stacked buttons
{
    "type": "stack",
    "columns": [
        [
            {"label": "Tool 1", "icon": "icon1", "type": "small", "action": "action1"},
            {"label": "Tool 2", "icon": "icon2", "type": "small", "action": "action2"}
        ],
        [
            {"label": "Tool 3", "icon": "icon3", "type": "small", "action": "action3"}
        ]
    ]
}
```

### Adding a New Panel

**File**: `main.py`

1. Add panel definition:
```python
panel_definitions = {
    # ... existing panels ...
    "MyPanel": {
        "tools": [
            {"label": "Tool 1", "icon": "icon1", "type": "large", "action": "action1"},
            {"label": "Tool 2", "icon": "icon2", "type": "small", "action": "action2"}
        ]
    }
}
```

2. Add panel to tab:
```python
ribbon_structure = [
    {"name": "Home", "panels": ["File", "Edit", "MyPanel"]},  # Add "MyPanel"
    # ... other tabs ...
]
```

### Adding a New Tab

**File**: `main.py`

```python
ribbon_structure = [
    # ... existing tabs ...
    {
        "name": "MyTab",
        "panels": ["Panel1", "Panel2", "Panel3"]
    }
]
```

### Changing Font Sizes

**File**: `ribbon_constants.py`

```python
class Styles:
    FONT_SIZE_LARGE: int = 10   # Large button labels
    FONT_SIZE_SMALL: int = 9    # Small button labels
```

### Changing Border Radius

**File**: `ribbon_constants.py`

```python
class Styles:
    BORDER_RADIUS_SMALL: int = 3   # Small buttons
    BORDER_RADIUS_LARGE: int = 4   # Large buttons
```

### Changing Padding

**File**: `ribbon_constants.py`

```python
class Styles:
    PADDING_SMALL: int = 2    # Tight padding
    PADDING_MEDIUM: int = 8   # Normal padding
```

## File Organization

```
OpenDraft/
├── ribbon_constants.py      → All constants (sizes, colors, styles)
├── ribbon_models.py         → Data models (type-safe definitions)
├── ribbon_factory.py        → Factory pattern (button creation)
├── RibbonPanel.py           → Main ribbon widget (tabs and panels)
├── RibbonPanelWidget.py     → Panel container (title + content)
├── RibbonSplitButton.py     → Split button component
├── panel_factory.py         → Legacy factory (backward compatible)
├── IconWidget.py            → Icon loading widget
├── main.py                  → Application entry + configuration
├── ribbon.qss               → Qt stylesheet
├── ARCHITECTURE.md          → Detailed architecture docs
├── REFACTORING_SUMMARY.md   → Summary of improvements
└── REFERENCE.md             → This file
```

## Component Hierarchy

```
RibbonPanel (tabs + stacked panels)
└── Tab Widget (horizontal layout)
    └── RibbonPanelWidget (panel container)
        └── Content Widget (tools)
            ├── Large Button
            ├── Small Button
            ├── RibbonSplitButton (split button)
            │   ├── Icon Button
            │   └── Dropdown Button/Arrow
            └── Stack Widget (columns of buttons)
```

## Button Types Reference

| Type | Display | Use Case | Size |
|------|---------|----------|------|
| `large` | Icon above text | Primary actions | 52×64 |
| `small` | Icon + text inline | Secondary actions | 72×28 |
| `split` | Large split button | Multiple related actions | 52×64 |
| `split-small` | Small split button | Compact multi-actions | 92×28 |
| `stack` | Multiple small buttons | Button groups | Variable |

## Icon Requirements

**Location**: `assets/icons/`

**Formats**: SVG (preferred) or PNG

**Naming**: `icon_name.svg` or `icon_name.png`

**Sizes**:
- Large buttons: 40×40px
- Small buttons: 24×24px
- Menu items: 24×24px

## Style Customization

### Custom Button Style

**File**: `ribbon_constants.py`

```python
class Styles:
    @staticmethod
    def my_custom_button(dark: bool = False) -> str:
        return f"""
            QPushButton {{
                font-size: 12px;
                background: {COLORS.BACKGROUND_DARK if dark else COLORS.BACKGROUND_LIGHT};
                border: 1px solid #555;
                padding: 5px;
            }}
            QPushButton:hover {{
                {Styles.button_hover(dark)}
            }}
        """
```

### Using Custom Style

**File**: Component file (e.g., `panel_factory.py`)

```python
btn.setStyleSheet(Styles.my_custom_button(dark))
```

## Common Enums

### ButtonType
```python
from ribbon_constants import ButtonType

ButtonType.LARGE.value          # "large"
ButtonType.SMALL.value          # "small"
ButtonType.SPLIT.value          # "split"
ButtonType.SPLIT_SMALL.value    # "split-small"
ButtonType.STACK.value          # "stack"
```

### ButtonSize
```python
from ribbon_constants import ButtonSize

ButtonSize.LARGE.value          # (52, 64)
ButtonSize.SMALL.value          # (72, 28)
ButtonSize.SPLIT_SMALL.value    # (92, 28)
```

### IconSize
```python
from ribbon_constants import IconSize

IconSize.LARGE.value            # 40
IconSize.SMALL.value            # 24
IconSize.MENU.value             # 24
```

## Data Models Usage

### Creating Tool Definitions

```python
from ribbon_models import ToolDefinition, SplitButtonDefinition, MenuItem

# Simple tool
tool = ToolDefinition(
    label="Save",
    type="large",
    icon="file_save",
    action="save_action"
)

# Split button
split_tool = SplitButtonDefinition(
    label="Line",
    type="split",
    mainAction="line_action",
    items=[
        MenuItem(label="Line", icon="line", action="line_action"),
        MenuItem(label="Polyline", icon="pline", action="pline_action")
    ]
)
```

### Creating Panel Definitions

```python
from ribbon_models import PanelDefinition

panel = PanelDefinition(
    name="File",
    tools=[tool1, tool2, tool3]
)
```

### Creating Full Configuration

```python
from ribbon_models import RibbonConfiguration

config = RibbonConfiguration.from_dict(
    structure=ribbon_structure,
    panel_defs=panel_definitions
)

# Access panels
file_panel = config.get_panel("File")
```

## Factory Usage

### ButtonFactory

```python
from ribbon_factory import ButtonFactory

def my_action_handler(action: str):
    print(f"Action: {action}")

factory = ButtonFactory(
    dark=True,
    action_handler=my_action_handler
)

button = factory.create_button(tool_definition)
```

### PanelFactory

```python
from ribbon_factory import PanelFactory

factory = PanelFactory(dark=True, action_handler=my_handler)
content_widget = factory.create_panel_content(tools_list)
```

## Debugging Tips

### Enable Debug Prints

Add to action handler:
```python
def debug_action_handler(action: str):
    print(f"DEBUG: Action triggered: {action}")
    # Your action logic here
```

### Check Button Sizes

```python
btn = factory.create_button(tool)
print(f"Button size: {btn.size()}")
```

### Verify Icon Loading

```python
icon = Icon("my_icon", size=40)
if icon.pixmap() and not icon.pixmap().isNull():
    print("Icon loaded successfully")
else:
    print("Icon not found or failed to load")
```

## Performance Tips

1. **Icon Caching**: Icons are loaded once and cached by Qt
2. **Lazy Loading**: Create panels only when tabs are switched (future enhancement)
3. **Widget Reuse**: Use factories to ensure consistent widget creation

## Migration Path

### Old Style → New Style

```python
# Old
btn = QPushButton()
btn.setFixedSize(72, 28)
btn.setStyleSheet("QPushButton { font-size: 9px; }")

# New
from ribbon_factory import ButtonFactory
factory = ButtonFactory()
btn = factory._create_small_button(tool_def)
```

## Getting Help

- **Architecture Details**: See `ARCHITECTURE.md`
- **Refactoring Changes**: See `REFACTORING_SUMMARY.md`
- **This Guide**: Quick reference for common tasks

## Version

This reference is for the refactored production-ready version created on February 26, 2026.
