# OpenDraft

![ODLogo](./Docs/Branding/od_logo.png#gh-light-mode-only)  
![ODLogo](./Docs/Branding/od_logo_reverse.png#gh-dark-mode-only)

OpenDraft is an open-source 2D CAD application built with Python and PySide6. It aims to provide a lightweight, user-friendly, and extendable CAD solution for 2D drafting. The project is currently in active early development.

> **Note:** This project is in early development. Breaking changes may occur without notice.

## Features

The following features are currently implemented:

**Drawing Tools**
- Lines, circles, arcs (3-point and center-radius), rectangles, polylines
- Ellipses, splines, and point/node entities
- Text annotation and basic dimensioning

**Modify Tools**
- Move, Copy, Rotate, Scale, Mirror
- Offset, Fillet, Chamfer
- Extend, Trim, Delete

**Canvas & Interaction**
- Zoomable, pannable viewport with grid display
- Object snap engine (endpoint, midpoint, center, nearest, perpendicular)
- Dynamic input widget for keyboard-driven coordinate entry
- Undo/redo support
- Entity selection with grip editing

**UI**
- Ribbon-based interface with tab/panel layout and overflow handling
- Layer manager
- Status bar and command palette
- Color picker with AutoCAD Color Index (ACI) support

## Roadmap

The following features are planned or in progress — see [TODO.md](./TODO.md) for the full list:

- Hatch fills (solid, ANSI31, crosshatch patterns)
- Dimension styles (arrowhead types, text height, precision)
- PDF and SVG export
- Construction lines (Xline/Ray)
- Array commands (rectangular and polar)
- Advanced selection modes (crossing window, Select All, Quick Select)
- Additional snap modes (intersection, quadrant, tangent, node)
- Properties palette and Match Properties
- Layer enhancements (lock, freeze, linetypes)

## Dependencies

OpenDraft depends on:

- [PySide6](https://doc.qt.io/qtforpython/) — Qt6 bindings for Python (UI framework and rendering)
- [watchfiles](https://watchfiles.helpmanual.io/) — File watching for auto-reload during development

**Development / Testing:**
- [pytest](https://pytest.org/) — Test runner
- [pytest-qt](https://pytest-qt.readthedocs.io/) — Qt integration for pytest

## Getting Started

```bash
# Clone the repository
git clone https://github.com/JamesHodgkins/OpenDraft.git
cd OpenDraft

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Running Tests

```bash
pytest
```

## Why Another CAD Package?

While existing open-source CAD solutions such as LibreCAD and FreeCAD are capable tools, OpenDraft aims to offer a distinct approach:

- **Lightweight**: Minimal resource usage while maintaining essential functionality.
- **User-Friendly**: Familiar ribbon-based interface designed for users of all experience levels.
- **Extendable**: Command-based architecture designed for easy addition of new tools.
- **Modern Stack**: Pure Python with PySide6 — no compiled extensions required.
- **Free Forever**: Open-source and community-driven, providing professional-grade CAD functionality at no cost.

## License

OpenDraft is licensed under the GNU General Public License v3.0 (GPL-3.0). Full license text is available in the [LICENSE](./LICENSE) file.

## Contributing

We welcome contributions! Please review the [contribution guidelines](./CONTRIBUTING.md) for details.

## Feedback, Support and Contact

Please use the [issue tracker](https://github.com/JamesHodgkins/OpenDraft/issues) for bug reports or feature requests.

Email: jhodgkins@proton.me

## Acknowledgments

We extend our gratitude to the creators and contributors of open-source CAD projects, whose work has inspired and supported OpenDraft's development.

Thank you for your interest in OpenDraft!  
