"""Unit tests for ai_user.dotenv_loader — the minimal ai_user/.env reader."""
from __future__ import annotations

import importlib

import ai_user.dotenv_loader as dotenv_loader


def _reload_pointed_at(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(dotenv_loader, "_ENV_PATH", env_file)
    return env_file


def test_sets_variable_from_file(tmp_path, monkeypatch) -> None:
    env_file = _reload_pointed_at(tmp_path, monkeypatch)
    env_file.write_text("MISTRAL_API_KEY=abc123\n", encoding="utf-8")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    dotenv_loader.load_ai_user_env()

    import os
    assert os.environ["MISTRAL_API_KEY"] == "abc123"


def test_does_not_override_existing_env_var(tmp_path, monkeypatch) -> None:
    env_file = _reload_pointed_at(tmp_path, monkeypatch)
    env_file.write_text("MISTRAL_API_KEY=from_file\n", encoding="utf-8")
    monkeypatch.setenv("MISTRAL_API_KEY", "from_real_env")

    dotenv_loader.load_ai_user_env()

    import os
    assert os.environ["MISTRAL_API_KEY"] == "from_real_env"


def test_ignores_blank_lines_and_comments(tmp_path, monkeypatch) -> None:
    env_file = _reload_pointed_at(tmp_path, monkeypatch)
    env_file.write_text(
        "\n# a comment\nMISTRAL_API_KEY=abc123\n\n# ANTHROPIC_API_KEY=commented_out\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    dotenv_loader.load_ai_user_env()

    import os
    assert os.environ["MISTRAL_API_KEY"] == "abc123"
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_strips_surrounding_quotes(tmp_path, monkeypatch) -> None:
    env_file = _reload_pointed_at(tmp_path, monkeypatch)
    env_file.write_text('MISTRAL_API_KEY="abc123"\n', encoding="utf-8")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    dotenv_loader.load_ai_user_env()

    import os
    assert os.environ["MISTRAL_API_KEY"] == "abc123"


def test_missing_file_is_a_harmless_noop(tmp_path, monkeypatch) -> None:
    _reload_pointed_at(tmp_path, monkeypatch)  # file never written

    dotenv_loader.load_ai_user_env()  # must not raise
