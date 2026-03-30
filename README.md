# OpenDraft PySide6 CAD Application

A 2D CAD application built with PySide6 featuring dynamic input, object snapping, and precision drawing tools.

## Features

- **Dynamic Input System:** Input boxes that follow your cursor during point selection, supporting multiple coordinate formats (relative, absolute, polar)
- **Object Snapping (OSNAP):** Snap to endpoints, midpoints, centers, and intersections
- **Pan & Zoom:** Navigate the canvas with middle-mouse button for panning and scroll wheel for zooming
- **Layer Management:** Create and manage layers, control visibility and properties
- **Selection Tools:** Single-click and drag-select entities with shift-modifier for toggling
- **Drawing Commands:** Draw lines, circles, arcs, rectangles, polylines, text, and dimensions

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   python main.py
   ```

## Dynamic Input Guide

During point selection in drawing commands:
- **Move mouse:** Live coordinate updates in dynamic input widget
- **Type coordinates:** Override with precise values
  - Relative: `10,20` (offset from previous point)
  - Absolute: `#100,50` (world coordinates)
  - Polar: `100<45` (distance and angle)
- **Press Tab:** Switch between coordinate formats
- **Press Enter:** Confirm input values
- **Press Esc:** Cancel and use cursor selection

See [DYNAMIC_INPUT_GUIDE.md](DYNAMIC_INPUT_GUIDE.md) for detailed usage examples and [DYNAMIC_INPUT.md](DYNAMIC_INPUT.md) for technical documentation.

## Project Structure

```
main.py                      # Application entry point
requirements.txt            # Python dependencies
REFERENCE.md               # Entity and geometry documentation
DYNAMIC_INPUT.md           # Dynamic input system documentation
DYNAMIC_INPUT_GUIDE.md     # User guide for dynamic input
├── app/
│   ├── __init__.py
│   ├── main_window.py      # Main application window
│   ├── canvas.py           # CAD viewport with pan/zoom
│   ├── document.py         # Document and entity storage
│   ├── commands/           # Drawing and editing commands
│   ├── editor/             # Command execution and input handling
│   │   ├── dynamic_input_parser.py  # Input format parsing
│   │   ├── osnap_engine.py          # Object snapping
│   │   └── ...
│   ├── entities/           # Line, circle, arc, text, etc.
│   ├── ui/                 # Dialog and widget components
│   │   └── dynamic_input_widget.py  # Dynamic input UI
│   ├── controls/           # Ribbon and toolbar widget controls
│   └── ...
├── tests/                  # Unit tests
└── assets/                 # Fonts, icons, images
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Esc | Cancel command / Clear selection |
| Tab | Move between X and Y input fields (during point input) |
| Shift+Tab | Cycle coordinate formats (during point input) |
| Enter | Confirm dynamic input |
| Shift+Click | Toggle entity selection |
| Middle-Drag | Pan canvas |
| Scroll | Zoom in/out |

## Documentation

- [Dynamic Input Guide](DYNAMIC_INPUT_GUIDE.md) - User guide with examples and keyboard shortcuts
- [Dynamic Input Technical Docs](DYNAMIC_INPUT.md) - Architecture and implementation details
- [Entity Reference](REFERENCE.md) - Geometry and entity type documentation

## Architecture

The application uses a **worker thread model** where commands run in a separate thread and block on user input. The dynamic input system seamlessly integrates with this architecture through Qt's signal-slot mechanism, allowing precise coordinate input while maintaining a responsive UI.

### Key Components

- **Editor:** Central command controller with thread-safe input handling
- **Canvas:** Viewport with pan/zoom, OSNAP, and dynamic input integration
- **Document:** Stores entities organized by layer
- **Commands:** Discrete, reusable drawing operations

## Customization

Edit configuration files and command implementations to customize:
- Ribbon buttons and panels → `app/config/ribbon_config.py`
- Drawing commands → `app/commands/`
- Dynamic input behavior → `app/ui/dynamic_input_widget.py`
- Styling → `assets/themes/ribbon.qss`
