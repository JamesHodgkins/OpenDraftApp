## Contributing to OpenDraft

Thank you for your interest in contributing to OpenDraft! We welcome contributions from the community to help improve and enhance the project.

### 1. Fork the Repository

Fork the OpenDraft repository to your GitHub account to create your own copy of the project.

### 2. Set Up Your Development Environment

**Requirements:**

- Python 3.12+
- A virtual environment tool (the project uses `.venv`)

**Install dependencies:**

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

This installs:
- [PySide6](https://doc.qt.io/qtforpython/) — Qt6 bindings (UI framework and rendering)
- [watchfiles](https://watchfiles.helpmanual.io/) — File watching for auto-reload during development
- [pytest](https://pytest.org/) and [pytest-qt](https://pytest-qt.readthedocs.io/) — Test runner and Qt integration

**Run the application:**

```bash
python main.py
```

### 3. Understand the Project Structure

```
app/
  commands/       # Drawing and modify command implementations
  config/         # Ribbon and UI configuration
  editor/         # Core editor logic
  entities/       # CAD entity classes (line, circle, arc, etc.)
  ui/             # Widgets (status bar, dynamic input, properties panel)
  canvas.py       # Main drawing canvas
  main_window.py  # Application window
controls/
  ribbon/         # Ribbon UI control components
assets/
  themes/         # QSS stylesheets
  svg/            # Icons and branding
tests/            # pytest test suite
```

### 4. Create a Feature Branch

Create a new branch for your contribution before making changes:

```bash
git checkout -b feature/your-feature-name
```

### 5. Make Your Changes

Follow these conventions when contributing:

- Commands live in `app/commands/` and should follow the existing command pattern
- Public command SDK lives in `app/sdk/commands/` (`CommandContext`, `CommandSpec`, `@command`) for plugin/third-party command authors
- Command logic should use helper APIs (`preview`, `highlighted`, `transaction`, `push_undo`, `notify_document`) instead of touching private internals like `editor._undo_stack` or `doc._notify`
- Third-party command IDs must be namespaced (for example `vendor.toolName`) to avoid registry collisions
- Third-party command packages should expose an `opendraft.commands` entry point whose target imports/registers plugin commands
- New entity types go in `app/entities/` with a corresponding entry in `app/entities/__init__.py`
- Ribbon entries are configured in `app/config/ribbon_config.py`
- Keep code clean and consistent with the surrounding style — avoid unnecessary abstractions

### 6. Test Your Changes

Run the test suite before submitting:

```bash
pytest
```

Also perform manual testing by running the application and exercising the relevant functionality directly.

### 7. Commit and Push

Commit your changes with clear, descriptive messages and push to your fork:

```bash
git add <files>
git commit -m "Add: brief description of change"
git push origin feature/your-feature-name
```

### 8. Submit a Pull Request

Open a pull request against the `main` branch of the original OpenDraft repository. Include a description of what you changed, why, and any relevant context. Reference any related issue or TODO item if applicable.

### 9. Review and Iteration

Project maintainers will review your PR and may request changes. Address any feedback and push additional commits as needed.

### 10. Merge

Once approved, your contribution will be merged into `main`.

## Code of Conduct

OpenDraft follows a code of conduct. All contributors are expected to be respectful and considerate in their interactions with others. See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) for details.

## Get Help

If you have questions or need assistance, open an issue on the GitHub repository or refer to the project documentation.

Thank you for contributing to OpenDraft!
