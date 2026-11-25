"""
Tests for :mod:`basstler.plan.agentic_loop.command_line` and
:mod:`basstler.plan.agentic_loop.stop_hook`: recording a finished stage, and starting
its successor when the turn ends.
"""

from __future__ import annotations

import json

import pytest

from basstler.environment import EnvironmentFlag
from basstler.locations import ClaudeCodeVariable
from basstler.plan.agentic_loop.command_line import (
    finish_changes,
    finish_review,
    turn_off,
    turn_on,
)
from basstler.plan.agentic_loop.session_start import CloudSessionRequest, StopHookAnswer
from basstler.plan.agentic_loop.settings import LoopSettings, LoopSettingsStore
from basstler.plan.agentic_loop.stage import LoopStage, PendingSession
from basstler.plan.agentic_loop.stop_hook import start_pending_session

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import LOOP_PULL_REQUEST, session_on_pull_request

# %% fixtures


@pytest.fixture
def entered_checkout(
    loop_checkout: ScratchRepository, monkeypatch: pytest.MonkeyPatch
) -> ScratchRepository:
    """
    :return: :func:`loop_checkout`, as the project Claude Code names.
    """
    monkeypatch.setenv(
        ClaudeCodeVariable.PROJECT_DIRECTORY, str(loop_checkout.project_root)
    )
    return loop_checkout


def pending_session(checkout: ScratchRepository):
    """
    :return: The session the checkout's finished stage recorded, taken.
    """
    return PendingSession(checkout.git).take()


# %% the setting


def test_turning_the_loop_on_pushes_the_rounds(entered_checkout: ScratchRepository):
    """
    The setting read back is on, with the rounds asked for.
    """
    turn_on(rounds=5)
    store = LoopSettingsStore.from_project_root(entered_checkout.project_root)
    assert store.read() == LoopSettings(enabled=True, maximum_review_rounds=5)


def test_turning_the_loop_off_keeps_the_rounds(entered_checkout: ScratchRepository):
    """
    Turning it off changes nothing but whether it is on.
    """
    turn_on(rounds=5)
    turn_off()
    store = LoopSettingsStore.from_project_root(entered_checkout.project_root)
    assert store.read() == LoopSettings(enabled=False, maximum_review_rounds=5)


# %% finished stages


def test_a_kickoff_with_the_loop_on_records_the_first_review(
    entered_checkout: ScratchRepository,
):
    """
    The first review of the checked-out pull request waits for the turn's end.
    """
    turn_on()
    finish_changes(pull_request=LOOP_PULL_REQUEST.number)
    assert pending_session(entered_checkout) == session_on_pull_request(
        LoopStage.REVIEW, 1
    )


def test_a_kickoff_with_the_loop_off_records_nothing(
    entered_checkout: ScratchRepository,
):
    """
    With no setting, the loop is off and no session waits.
    """
    finish_changes(pull_request=LOOP_PULL_REQUEST.number)
    assert pending_session(entered_checkout) is None


def test_a_review_asked_to_loop_records_its_resolve(
    entered_checkout: ScratchRepository,
):
    """
    ``--loop`` starts the resolve though the setting is off.
    """
    finish_review(
        pull_request=LOOP_PULL_REQUEST.number, review_round=1, findings=2, loop=True
    )
    assert pending_session(entered_checkout) == session_on_pull_request(
        LoopStage.RESOLVE, 1
    )


# %% the turn's end


def test_the_turn_s_end_starts_the_recorded_cloud_session(
    entered_checkout: ScratchRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """
    The hook asks the cloud session to start the recorded one, and forgets it.
    """
    monkeypatch.setenv(ClaudeCodeVariable.REMOTE, EnvironmentFlag.TRUE)
    session = session_on_pull_request(LoopStage.REVIEW, 1)
    PendingSession(entered_checkout.git).record(session)

    start_pending_session()

    answer = StopHookAnswer.from_json(json.loads(capsys.readouterr().out))
    assert (answer.reason, pending_session(entered_checkout)) == (
        CloudSessionRequest(session).render(),
        None,
    )


def test_a_turn_s_end_without_a_recorded_session_prints_nothing(
    entered_checkout: ScratchRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """
    A turn that finished no stage ends as it would without the hook.
    """
    monkeypatch.setenv(ClaudeCodeVariable.REMOTE, EnvironmentFlag.TRUE)
    start_pending_session()
    assert capsys.readouterr().out == ""
