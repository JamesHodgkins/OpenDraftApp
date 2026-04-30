"""Contract tests for command architecture lifecycle and helper guarantees."""
from __future__ import annotations

import threading
import time

from app.document import DocumentStore
from app.editor.base_command import CommandBase
from app.editor.command_registry import command
from app.editor.editor import Editor
from app.editor.undo import UndoCommand


def _wait_until(predicate, timeout: float = 1.0) -> bool:
    """Poll *predicate* until true or timeout."""
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@command("tests.contract_wait_point", source="tests")
class _WaitPointCommand(CommandBase):
    """Command that blocks on point input until cancelled or satisfied."""

    def execute(self) -> None:
        self.editor.get_point("Contract: pick a point")


@command("tests.contract_txn_command", source="tests")
class _TransactionCommand(CommandBase):
    """Command using transaction helpers to enforce undo semantics."""

    class _MarkerUndo(UndoCommand):
        def __init__(self, log: list[str], label: str) -> None:
            self._log = log
            self.description = label

        def redo(self) -> None:
            self._log.append(f"redo:{self.description}")

        def undo(self) -> None:
            self._log.append(f"undo:{self.description}")

    def __init__(self, editor: Editor) -> None:
        super().__init__(editor)
        self.log: list[str] = []

    def execute(self) -> None:
        with self.editor.transaction("Contract transaction") as tx:
            tx.add_undo(self._MarkerUndo(self.log, "first"))
            tx.add_undo(self._MarkerUndo(self.log, "second"))
            tx.emit_document_changed()


@command("tests.contract_helper_undo", source="tests")
class _HelperUndoCommand(CommandBase):
    """Command that uses push_undo_command helper directly."""

    class _SimpleUndo(UndoCommand):
        description = "Helper push"

        def __init__(self, log: list[str]) -> None:
            self._log = log

        def redo(self) -> None:
            self._log.append("redo")

        def undo(self) -> None:
            self._log.append("undo")

    def __init__(self, editor: Editor) -> None:
        super().__init__(editor)
        self.log: list[str] = []

    def execute(self) -> None:
        self.editor.push_undo_command(self._SimpleUndo(self.log))
        self.editor.notify_document()


def test_command_cancel_lifecycle_resets_editor_state() -> None:
    ed = Editor(document=DocumentStore())

    ed.run_command("tests.contract_wait_point")
    assert _wait_until(lambda: ed.is_running)
    assert ed.active_command is not None

    ed.cancel()
    assert _wait_until(lambda: not ed.is_running)

    assert ed.last_command_name == "tests.contract_wait_point"
    assert ed.active_command is None
    assert ed.is_running is False
    assert ed._thread is None
    assert ed.input_mode == "none"
    assert ed.command_option_labels == []


def test_cancelled_command_does_not_block_next_command_start() -> None:
    ed = Editor(document=DocumentStore())

    ed.run_command("tests.contract_wait_point")
    assert _wait_until(lambda: ed.is_running)

    ed.cancel()
    assert _wait_until(lambda: not ed.is_running)

    # Should start cleanly after previous cancellation finalized.
    ed.run_command("tests.contract_wait_point")
    assert _wait_until(lambda: ed.is_running)
    ed.cancel()
    assert _wait_until(lambda: not ed.is_running)


def test_transaction_command_undo_redo_contract() -> None:
    ed = Editor(document=DocumentStore())

    ed.run_command("tests.contract_txn_command")
    assert _wait_until(lambda: not ed.is_running)

    cmd = ed.last_command_name
    assert cmd == "tests.contract_txn_command"
    assert ed.undo_stack.undo_text == "Contract transaction"

    # Recover the command instance by recreating and inspecting its log contract.
    # Undo/redo should run child commands in reverse/forward order.
    tx_cmd = _TransactionCommand(ed)
    tx_cmd.execute()
    assert ed.undo() is True
    assert tx_cmd.log == ["undo:second", "undo:first"]
    assert ed.redo() is True
    assert tx_cmd.log == [
        "undo:second",
        "undo:first",
        "redo:first",
        "redo:second",
    ]


def test_push_undo_helper_contract_with_undo_redo() -> None:
    ed = Editor(document=DocumentStore())

    cmd = _HelperUndoCommand(ed)
    cmd.execute()

    assert ed.undo_stack.undo_text == "Helper push"
    assert ed.undo() is True
    assert cmd.log == ["undo"]
    assert ed.redo() is True
    assert cmd.log == ["undo", "redo"]


def test_run_command_rejects_start_when_previous_thread_alive(monkeypatch) -> None:
    ed = Editor(document=DocumentStore())

    class _FakeThread:
        def join(self, timeout: float | None = None) -> None:
            return None

        def is_alive(self) -> bool:
            return True

        name = "fake-command-thread"

    fake_thread = _FakeThread()

    # Patch the class property so this instance reports a running command.
    monkeypatch.setattr(Editor, "is_running", property(lambda _self: True))
    ed._thread = fake_thread  # type: ignore[assignment]

    messages: list[str] = []
    ed.status_message.connect(messages.append)

    ed.run_command("tests.contract_wait_point")

    assert messages
    assert "still cancelling" in messages[-1].lower()


def test_run_command_handles_thread_cleared_during_join(monkeypatch) -> None:
    ed = Editor(document=DocumentStore())

    class _RaceThread:
        def join(self, timeout: float | None = None) -> None:
            # Simulate worker finalization clearing the shared thread slot while
            # run_command is waiting on join.
            ed._thread = None

        def is_alive(self) -> bool:
            return False

        name = "race-command-thread"

    monkeypatch.setattr(Editor, "is_running", property(lambda _self: True))
    ed._thread = _RaceThread()  # type: ignore[assignment]

    messages: list[str] = []
    ed.status_message.connect(messages.append)

    # Must not raise if the thread slot is cleared between join() and
    # the liveness check.
    ed.run_command("tests.unknown_command")

    assert messages
    assert "unknown command" in messages[-1].lower()
