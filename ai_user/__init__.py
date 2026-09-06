"""ai_user — an automated, AI-driven "user" for OpenDraft.

This package drives the real OpenDraft GUI (a PySide6 desktop app) the way a
human would: it only ever "sees" a rendered screenshot of the app window and
only ever acts through mouse/keyboard input events delivered to real widgets.
Nothing here calls into ``Editor``/``DocumentStore`` to perform the task
directly — that would defeat the point. Verifying whether a task was
*completed* is the one place internal state is read (see ``ai_user.tasks``),
kept deliberately separate from the actions available to the agent.

Modules:

* ``app_harness`` — boots the app offscreen, captures screenshots, classifies
  screen regions (viewport vs. properties panel), executes actions via
  ``QTest``, and detects focus changes.
* ``actions`` — the typed action vocabulary the agent can request, modelled
  on Anthropic's ``computer_toolset_20260801`` tool.
* ``scoring`` — implements the point rules for a run.
* ``best_scores`` — persists the best (fewest-steps) run per task.
* ``tasks`` — task prompts + programmatic completion verifiers.
* ``agent`` — the Claude computer-use agent loop.
* ``run`` — CLI entry point.
"""
