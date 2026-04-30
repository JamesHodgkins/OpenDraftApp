"""Dynamic input overlay tests removed.

The old cursor-following dynamic input widget was removed. Command and value
typing use the docked Controller (:mod:`app.ui.properties_panel`).
"""
from __future__ import annotations

import pytest


pytest.skip(
    "DynamicInputWidget removed; use PropertiesPanel (Controller) command input.",
    allow_module_level=True,
)
