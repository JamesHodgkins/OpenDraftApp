"""Minimal, dependency-free ``.env`` loader for ai_user.

Only reads ``ai_user/.env`` (never the project root, so it can't be
confused with any other tool's env file) and only sets a variable if it
isn't already present in the environment — an explicitly exported
``MISTRAL_API_KEY``/``ANTHROPIC_API_KEY`` always wins over the file. Not a
generic .env parser: quoting/escaping/multiline values aren't supported,
just ``KEY=value`` lines and blank/``#``-comment lines, which is all a
single API key file needs.
"""
from __future__ import annotations

from pathlib import Path

_ENV_PATH = Path(__file__).parent / ".env"


def load_ai_user_env() -> None:
    import os

    if not _ENV_PATH.exists():
        return

    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
