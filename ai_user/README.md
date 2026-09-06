# ai_user — an AI-driven "user" for OpenDraft

Drives the real OpenDraft GUI the way a human would: it only ever sees a
rendered screenshot of the app and only ever acts through simulated
mouse/keyboard input at screen coordinates. Nothing here calls into
`Editor`/`DocumentStore` to perform a task directly — that's the entire
point of the exercise. Completion is checked afterward by inspecting the
document, which is the one place internal state is read, kept separate from
the actions the agent can take.

## Setup

```bash
pip install -r requirements.txt   # installs anthropic + mistralai alongside the app's own deps
```

Provide whichever provider's key you actually have, either as a real
environment variable:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # for --provider claude (default)
# or
export MISTRAL_API_KEY=...            # for --provider mistral
```

or via `ai_user/.env` (gitignored — never commit it):

```bash
cp ai_user/.env.example ai_user/.env
# then edit ai_user/.env and fill in the key(s) you have
```

`run.py` loads `ai_user/.env` automatically before touching either
provider's SDK; a real exported env var always takes precedence over the
file. You only need a key for whichever provider you actually run with —
the other's SDK is imported lazily and never touched.

## Running a task

```bash
python -m ai_user.run --list                                   # see available tasks
python -m ai_user.run --task draw_a_line                        # Claude, headless (offscreen)
python -m ai_user.run --task draw_a_line --provider mistral      # Mistral (Pixtral Large) instead
python -m ai_user.run --task draw_rectangle_100x50 --visible     # show the window on-screen
```

Each run prints a step-by-step score breakdown and the total, e.g.:

```
Steps taken: 6
Completed: True
  [  0] screenshot   +0
  [  1] key          +1  keyboard input (+1)
  [  2] type         +1  keyboard input (+1)
  ...
Total points: 12
New best! (previous best: 9)
```

## How scoring works (`scoring.py`)

* **+1** for each action that uses the keyboard area (A-Z, 0-9, Ctrl, Shift, Space).
* **-2** for each click landing in the Controller dock (properties/control panel).
* **-10** for a repeated identical action, or a click that lands on a widget
  but doesn't move keyboard focus — the observable symptom of a
  focus-stealing/dropped-input bug (see `KNOWN_BUGS.md` items #11/#33 for
  real examples this is designed to catch).
* **+10** if the task completes in fewer steps than the best previously
  recorded run for that task id (`best_scores.py`, persisted to
  `ai_user/scores/best_runs.json`).

## Architecture

* `app_harness.py` — boots `MainWindow` (offscreen by default), captures
  screenshots, classifies coordinates into the viewport/properties-panel/
  other regions, and executes actions via real `QTest` events. Modal
  dialogs (e.g. Save As) are in scope: the harness always screenshots and
  targets whichever top-level window is actually active, exactly like a
  human would see it.
* `actions.py` — the small action vocabulary (screenshot, left_click,
  double_click, type, key, scroll, wait, done), modelled on Anthropic's
  `computer_toolset_20260801` tool.
* `agent.py` — `AgentRunner` drives the perceive → decide → act → score
  loop against any `Brain` implementation (the `Brain` protocol: `reset`,
  `next_action`, `observe_result`).
* `brains_claude.py` — `ClaudeComputerUseBrain`, backed by the Anthropic API
  (Opus 5 + the `computer_toolset_20260801` computer-use tool).
* `brains_mistral.py` — `MistralVisionBrain`, backed by the Mistral API
  (Pixtral Large + a custom `computer_action` function-calling tool, since
  Mistral has no computer-use preset). Both brains produce the same
  `Action` objects via the shared `brain_common.action_from_tool_input`.
* `tasks/` — task prompts + a programmatic verifier per task (checked
  against `DocumentStore`, never shown to the agent).
* `scoring.py` / `best_scores.py` — the point rules and their persistence.

## Adding a task

Add a `Task(task_id, prompt, verify, max_steps)` to `tasks/basic_shapes.py`
(or a new module under `tasks/`) — `verify` takes the real `DocumentStore`
and returns whether the task is objectively done.

## Testing

`tests/test_ai_user_*.py` covers every module except the live Anthropic API
call itself (`ClaudeComputerUseBrain`), which is exercised via a scripted
fake `Brain` in `test_ai_user_agent.py` instead — no network/API key needed
to run the suite:

```bash
python -m pytest tests/test_ai_user_*.py -q
```
