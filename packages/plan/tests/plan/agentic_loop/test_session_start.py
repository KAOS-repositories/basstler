"""
Tests for :mod:`basstler.plan.agentic_loop.session_start`: starting the loop's next
session in the cloud and on a computer.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from basstler.environment import EnvironmentFlag
from basstler.locations import ClaudeCodeVariable, RepositoryStateLocation
from basstler.plan.agentic_loop.exceptions import ClaudeCodeMissingError
from basstler.plan.agentic_loop.session_start import (
    ClaudeCodeCommand,
    CloudSessionRequest,
    CloudSessionStarter,
    LocalSessionStarter,
    SessionStarter,
    StopDecision,
    StopHookAnswer,
)
from basstler.plan.agentic_loop.stage import LoopStage
from basstler.text_file import TextFile

from basstler_testing.constants.environment import SearchPathVariable
from basstler_testing.executable_stubs import (
    NEEDS_SCRIPT_AS_EXECUTABLE,
    ExecutableStubDirectory,
)
from basstler_testing.scratch_repository import ScratchRepository
from .conftest import session_on_pull_request

# %% which starter runs


def test_a_cloud_session_starts_the_next_one_itself(
    scratch_repository: ScratchRepository, monkeypatch: pytest.MonkeyPatch
):
    """
    Claude Code's remote flag picks the cloud starter.
    """
    monkeypatch.setenv(ClaudeCodeVariable.REMOTE, EnvironmentFlag.TRUE)
    starter = SessionStarter.for_this_machine(scratch_repository.git)
    assert type(starter) is CloudSessionStarter


def test_a_session_on_a_computer_starts_a_process(
    scratch_repository: ScratchRepository, monkeypatch: pytest.MonkeyPatch
):
    """
    Without the remote flag, a process starts in the same checkout.
    """
    monkeypatch.delenv(ClaudeCodeVariable.REMOTE, raising=False)
    starter = SessionStarter.for_this_machine(scratch_repository.git)
    assert starter == LocalSessionStarter(scratch_repository.git)


# %% in the cloud


def test_the_cloud_starter_keeps_the_turn_going_with_the_request(
    capsys: pytest.CaptureFixture[str],
):
    """
    The hook's answer blocks the stop, with the request as its reason.
    """
    session = session_on_pull_request(LoopStage.REVIEW, 1)

    CloudSessionStarter().start(session)

    answer = StopHookAnswer.from_json(json.loads(capsys.readouterr().out))
    assert answer == StopHookAnswer(
        reason=CloudSessionRequest(session).render(), decision=StopDecision.BLOCK
    )


def test_the_cloud_request_carries_the_session_s_prompt():
    """
    The ``create_session`` call the request asks for starts with the session's prompt.
    """
    session = session_on_pull_request(LoopStage.RESOLVE, 2)
    assert f"`{session.prompt}`" in CloudSessionRequest(session).render()


# %% on a computer


@NEEDS_SCRIPT_AS_EXECUTABLE
def test_the_local_starter_runs_claude_with_the_prompt(
    scratch_repository: ScratchRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    The stub ``claude`` prints its arguments into the loop's log.
    """
    stubs = ExecutableStubDirectory.create(tmp_path)
    stubs.install(ClaudeCodeCommand.EXECUTABLE)
    monkeypatch.setenv(
        SearchPathVariable.EXECUTABLE_SEARCH_PATH, stubs.ahead_of_inherited_path()
    )
    session = session_on_pull_request(LoopStage.REVIEW, 1)
    log = scratch_repository.git.repository_state_path(
        RepositoryStateLocation.AGENTIC_LOOP_LOG
    )
    expected = f"{ClaudeCodeCommand.PRINT}\n{session.prompt}\n"

    LocalSessionStarter(scratch_repository.git).start(session)

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and (
        not log.exists() or TextFile(log).read() != expected
    ):
        time.sleep(0.05)
    assert TextFile(log).read() == expected


def test_the_local_starter_refuses_without_claude(
    scratch_repository: ScratchRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    No ``claude`` on the search path is refused before anything starts.
    """
    monkeypatch.setenv(SearchPathVariable.EXECUTABLE_SEARCH_PATH, str(tmp_path))
    with pytest.raises(ClaudeCodeMissingError):
        LocalSessionStarter(scratch_repository.git).start(
            session_on_pull_request(LoopStage.REVIEW, 1)
        )
