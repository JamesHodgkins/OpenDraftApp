---
title: Simplify rotate command options
source_plan_path: c:\Users\james\.cursor\plans\simplify_rotate_command_options_63067cca.plan.md
---

## Findings (current behavior)
- `RotateCommand` loops on `get_point(...allow_command_options=True)` and uses right-click “Command options” to branch into:
  - Enter angle (typed)
  - Set base vector (currently 2-click `get_vector`)
  - Set destination vector (currently 2-click `get_vector`)
  See `[app/commands/modify_rotate.py](app/commands/modify_rotate.py)`.
- The editor already has richer primitives we can lean on:
  - `get_angle(prompt, center=..., allow_command_options=...)` accepts either typed degrees **or a click on canvas** to derive an angle from `center`.
  - `get_vector_from(base, ...)` gives a 1-click “ray from base” workflow (base point implied).
  - `get_command_option(prompt, options)` exists for “wait only for context option” flows.
  See `[app/editor/editor.py](app/editor/editor.py)`.

## Target UX principles
- Default path is always the common case: **pick base point → click for angle or type angle**, with minimal branching.
- Optional “power” options must be strictly **opt-in** and must not introduce required extra steps unless the user explicitly chooses them.
- The command must never dead-end waiting for an option; if the user ignores options, the command should still complete via the default inputs.
- Optional reference workflows (base/dest) should be **1 click per ray** (anchored at center), not “pick start + pick end”.
- Command authors should not have to hand-roll loops and option plumbing each time; provide a small reusable helper.

## Proposed redesign
### 1) Rotate becomes “angle-first”, with reference mode as an option
- After selecting the base point (`center`), use `get_angle(..., center=center, allow_command_options=True)` as the main interaction:
  - **Typed angle** works immediately (no extra clicks).
  - **Click** sets the angle from the base point (no additional steps).
- Provide a small set of optional actions via command options (right-click), but make them *feel* lightweight:
  - **Set_base_axis**: pick a single point to define base ray from center (`get_vector_from(center, ...)`).
  - **Reference_rotate**: pick base ray (1 click) then dest ray (1 click) and compute signed delta.
  - **Reset_reference**: clear base axis.
- Keep preview continuous while waiting for the angle/rays.

### 2) Introduce a reusable “step + options” helper for commands
Add a tiny abstraction to remove the ad-hoc while-loops from commands like Rotate/Scale:
- A helper function (or small class) that:
  - sets command options
  - runs a blocking `get_*` call that may yield `CommandOptionSelection`
  - routes option selections to handlers
  - guarantees cleanup (`clear_command_options`) and makes state explicit

Where to place it (pick one during implementation):
- **Editor-side**: add something like `Editor.prompt_with_options(...)` in `[app/editor/editor.py](app/editor/editor.py)`
- **SDK-facing**: add the helper on `CommandContext` in `[app/sdk/commands/context.py](app/sdk/commands/context.py)` so user/plugin commands naturally reuse it

### 3) Make “reference vectors” center-anchored everywhere it makes sense
- Refactor Rotate (and any similar commands later) to prefer `get_vector_from(center, ...)` over `get_vector(...)` when the start point is logically implied.

## How this reduces clicks (Rotate)
- **Simple rotate**: center click + angle type (0 extra clicks) or center click + angle click (1 extra click).
- **Reference rotate**: center click + base ray click + dest ray click (2 extra clicks), instead of 4.

## Files likely touched
- `[app/commands/modify_rotate.py](app/commands/modify_rotate.py)`: replace prototype loop with angle-first + center-anchored reference rays.
- `[app/editor/editor.py](app/editor/editor.py)` and/or `[app/sdk/commands/context.py](app/sdk/commands/context.py)`: add reusable “prompt-with-options” helper.
- `[TODO.md](TODO.md)` and `[TODO_COMPLETED.md](TODO_COMPLETED.md)`: update roadmap + completed tracking per workspace rule.

## Test/verification
- Manual: rotate with typed angle, rotate with click-derived angle, reference rotate (base+dest rays), reset base axis, cancel with Escape at each step.
- Quick regression: confirm Scale still works (it uses the same option mechanism).

