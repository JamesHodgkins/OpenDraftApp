# Dynamic Input Feature

The dynamic input system allows users to input precise values during CAD commands through input boxes that appear near the cursor. This feature supports multiple input formats for vectors, integers, floats, and text inputs.

## Architecture

### Components

1. **DynamicInputParser** (`app/editor/dynamic_input_parser.py`)
   - Parses various input formats for vectors and scalars
   - Supports relative, absolute, and polar coordinate formats
   - Formatting utilities for displaying values in input boxes

2. **DynamicInputWidget** (`app/ui/dynamic_input_widget.py`)
   - PySide6 widget that appears near the cursor
   - Shows input fields that follow cursor movement
   - Handles user input and format cycling
   - Emits `input_submitted` and `input_cancelled` signals

3. **Canvas Integration** (`app/canvas.py`)
   - Creates and manages the DynamicInputWidget
   - Updates widget position and values as cursor moves
   - Forwards user input to the editor

## Input Formats

### Vector Input (Point Selection)

When a command calls `editor.get_point()`, the dynamic input widget shows two fields for coordinate input. Users can switch between formats using **Tab**:

#### Relative Coordinates (Default)
- **Format:** `dx,dy` or `dx dy`
- **Example:** `10,20` or `10 20`
- **Description:** Offset from the previously selected point or origin
- **Display Labels:** `X` (delta X), `Y` (delta Y)

#### Absolute Coordinates
- **Format:** `#x,y` or `#x y`
- **Example:** `#100,50` or `#100 50`
- **Description:** Absolute world coordinates
- **Display Labels:** `X` (world X), `Y` (world Y)

#### Polar Coordinates
- **Format:** `distance<angle` or `distance@angle`
- **Example:** `100<45` or `100@45`
- **Description:** Distance and angle (in degrees) from the reference point
- **Angle Measurement:** Counter-clockwise from positive X-axis
- **Display Labels:** `Distance`, `Angle`

#### Separator Flexibility
- Commas, spaces, and semicolons are accepted as separators
- Examples: `10,20`, `10 20`, `10;20` are all equivalent

### Scalar Input (Integer/Float)

When a command calls `editor.get_integer()` or `editor.get_float()`, a single input field appears:

- **Integer:** Enter whole numbers (e.g., `42`)
- **Float:** Enter decimal numbers (e.g., `3.14`)

### String Input

When a command calls `editor.get_string()`, a text field appears for free-form text input.

## Usage

### For Command Developers

Commands use the existing editor input methods, which automatically integrate with dynamic input:

```python
from app.editor import command
from app.editor.base_command import CommandBase
from app.entities import LineEntity

@command("lineCommand")
class DrawLineCommand(CommandBase):
    def execute(self) -> None:
        # Request a point — dynamic input automatically available
        start = self.editor.get_point("Line: pick start point")
        
        # Optionally set a base point for relative input calculations
        self.editor.snap_from_point = start
        
        end = self.editor.get_point("Line: pick end point")
        self.editor.add_entity(LineEntity(p1=start, p2=end))
```

The dynamic input widget automatically appears during `get_point()` calls and follows the cursor.

### For Users

1. **Point Input:** During point selection requests:
   - Move the mouse to see live coordinate updates
   - Type values directly to override cursor position
   - Press **Tab** to cycle between absolute, relative, and polar formats
   - Press **Enter** to submit the input or click to select a point

2. **Numeric/Text Input:** For integer, float, or string inputs:
   - Type the value in the input box
   - Press **Enter** to submit or **Escape** to cancel

3. **Format Switching:** While in point input mode:
   - Press **Tab** to cycle through coordinate formats
   - The format indicator shows the current format
   - Format changes apply immediately to the display

## Examples

### Drawing a Line with Dynamic Input

1. Click "Line" button to start the line command
2. Dynamic input widget appears near cursor
3. Type `#100,50` to set absolute starting point
4. Press **Enter**
5. Type `#200,150` to set absolute ending point
6. Press **Enter**

### Using Relative Coordinates

If you previously clicked at (100, 50) and want to place the next point 50 units right and 30 units up:

1. The widget shows the previous point as the base
2. Type `50,30` for relative input
3. Press **Tab** to confirm format or **Enter** to submit

### Using Polar Coordinates

To place a point 100 units away at 45 degrees from the origin:

1. Press **Tab** until "Format: distance<angle" appears
2. Type `100<45`
3. Press **Enter**

## Implementation Details

### Widget Lifecycle

1. **Creation:** CADCanvas creates DynamicInputWidget in `__init__`
2. **Activation:** When editor changes input mode to "point", "integer", "float", or "string"
3. **Operation:** Widget updates position and values as cursor moves via `mouseMoveEvent`
4. **Focus Locking:** Event filter (FieldTabFilter) intercepts Tab key to keep focus between the two input fields
5. **Submission:** User presses Enter or clicks canvas → value forwarded to editor
6. **Deactivation:** Input mode returns to "none" after command completes

### Focus Locking (FieldTabFilter)

The `FieldTabFilter` event filter ensures that Tab key presses don't allow keyboard focus to escape the dynamic input widget:

- **Tab:** Moves focus from field_1 → field_2 → field_1 (in point mode)
- **Shift+Tab:** Cycles through coordinate formats backwards (relative → polar → absolute → relative)
- **In scalar mode:** Tab is consumed and focus stays in field_1

This prevents accidental tab-out to other UI elements while users are entering precise coordinates.

### Signal Flow

```
Command calls get_point()
↓
Editor emits input_mode_changed("point")
↓
Canvas._on_editor_input_mode_changed() → shows DynamicInputWidget
↓
User types/clicks → DynamicInputWidget.input_submitted
↓
Canvas._on_dynamic_input_submitted() → Editor.provide_point(Vec2)
↓
Command thread unblocks and continues
```

### Auto-Hide Behavior

The dynamic input widget automatically hides when:
- Input mode changes to "none"
- User presses Escape
- Widget loses focus
- Input mode becomes something other than "point", "integer", "float", or "string"

## Technical Notes

- **Thread Safety:** Dynamic input submission calls `editor.provide_point()` etc. which handle thread-safe queue communication
- **Input Validation:** Parser returns `None` for invalid input; widget emits `input_cancelled` in this case
- **Canvas Coordinates:** Widget uses screen coordinates for positioning and updates based on cursor movement
- **Snap Integration:** Dynamic input works seamlessly with OSNAP (object snap) — snapped coordinates update the display

## Customization

### Styling

The dynamic input widget's appearance can be customized via the stylesheet in `DynamicInputWidget.setStyleSheet()`. Current colors:

- Background: `#2E2E2E` (dark gray)
- Border: `#555`
- Input fields: `#1E1E1E` with white text
- Focused border: `#0E639C` (blue)

### Input Format Colors and Sizes

Modify in `DynamicInputWidget._setup_vector_input()` or `_setup_scalar_input()`:

```python
self._field_1.setMaximumWidth(70)  # Width of first input field
```

### Coordinate System

The parser assumes:
- **X-axis:** Horizontal (positive right)
- **Y-axis:** Vertical (positive up)
- **Angle:** Measured counter-clockwise from positive X-axis in degrees

## Testing

The parser can be tested directly:

```python
from app.editor.dynamic_input_parser import DynamicInputParser
from app.entities import Vec2

# Parse relative input
result = DynamicInputParser.parse_vector("10,20", Vec2(0, 0), Vec2(0, 0))
print(result)  # Vec2(10.0, 20.0)

# Parse absolute input
result = DynamicInputParser.parse_vector("#100,50", Vec2(0, 0), None)
print(result)  # Vec2(100.0, 50.0)

# Parse polar input
result = DynamicInputParser.parse_vector("100<45", Vec2(0, 0), Vec2(0, 0))
print(result)  # Vec2(70.71..., 70.71...)
```

## Future Enhancements

Potential improvements to the dynamic input system:

1. **Input History:** Remember and cycle through previous inputs with arrow keys
2. **Unit Support:** Accept input with units (e.g., "10mm", "1.5in")
3. **Calculation:** Support mathematical expressions (e.g., "10+5", "sqrt(2)")
4. **Format Presets:** Save and load commonly used format preferences
5. **Multi-line Input:** Support for complex inputs requiring multiple values
6. **Autocomplete:** Suggest previously entered values
