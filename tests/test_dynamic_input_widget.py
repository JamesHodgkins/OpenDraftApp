"""Dynamic input overlay tests removed.

OpenDraft now uses the top-of-viewport terminal as the single consolidated
input surface, and the cursor-following DynamicInputWidget has been removed.
"""
from __future__ import annotations

import pytest


pytest.skip("DynamicInputWidget removed (replaced by TopTerminalWidget).", allow_module_level=True)
