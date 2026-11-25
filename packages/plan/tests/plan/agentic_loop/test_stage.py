"""
Tests for :mod:`basstler.plan.agentic_loop.stage`: which session a finished stage starts.
"""

from __future__ import annotations

import pytest

from basstler.plan.agentic_loop.settings import LoopSettings
from basstler.plan.agentic_loop.stage import (
    AgenticLoop,
    ChangesCompletion,
    LoopEnd,
    LoopStage,
    LoopStep,
    NextSession,
    PendingSession,
    ReviewCompletion,
    StageCompletion,
)
from basstler.plan.skills import PlanItemResolveSkill, PlanItemReviewSkill

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import LOOP_PULL_REQUEST, session_on_pull_request

# %% the successor of each finished stage

MAXIMUM_REVIEW_ROUNDS = 2
"""
The rounds the loop allows in these tests.
"""


@pytest.mark.parametrize(
    ("completion", "successor"),
    [
        (
            ChangesCompletion(LOOP_PULL_REQUEST, 0),
            session_on_pull_request(LoopStage.REVIEW, 1),
        ),
        (
            ReviewCompletion(LOOP_PULL_REQUEST, 1, findings=3),
            session_on_pull_request(LoopStage.RESOLVE, 1),
        ),
        (ReviewCompletion(LOOP_PULL_REQUEST, 1, findings=0), LoopEnd.NOTHING_FOUND),
        (
            ChangesCompletion(LOOP_PULL_REQUEST, 1),
            session_on_pull_request(LoopStage.REVIEW, 2),
        ),
        (
            ChangesCompletion(LOOP_PULL_REQUEST, MAXIMUM_REVIEW_ROUNDS),
            LoopEnd.ROUNDS_USED_UP,
        ),
    ],
    ids=[
        "a kickoff starts the first review",
        "a review with findings starts their resolve",
        "a review without findings ends the loop",
        "a resolve starts the next review",
        "the resolve of the last round ends the loop",
    ],
)
def test_a_finished_stage_starts_its_successor(
    completion: StageCompletion, successor: NextSession | LoopEnd
):
    """
    Each finished stage starts the stage after it, or ends the loop.
    """
    loop = AgenticLoop(
        LoopSettings(enabled=True, maximum_review_rounds=MAXIMUM_REVIEW_ROUNDS)
    )
    assert loop.successor(completion) == successor


@pytest.mark.parametrize(
    ("enabled", "requested", "successor"),
    [
        (False, None, LoopEnd.TURNED_OFF),
        (True, False, LoopEnd.TURNED_OFF),
        (False, True, session_on_pull_request(LoopStage.REVIEW, 1)),
    ],
    ids=[
        "the setting off starts nothing",
        "a run asking for it off overrides the setting",
        "a run asking for it on overrides the setting",
    ],
)
def test_a_run_s_request_outranks_the_setting(
    enabled: bool, requested: bool | None, successor: NextSession | LoopEnd
):
    """
    A run's ``--loop`` or ``--no-loop`` decides over the user's setting.
    """
    loop = AgenticLoop(LoopSettings(enabled=enabled), requested)
    assert loop.successor(ChangesCompletion(LOOP_PULL_REQUEST, 0)) == successor


def test_a_step_holds_either_the_session_or_why_there_is_none():
    """
    A printed step holds the successor under the key that says what it is.
    """
    session = session_on_pull_request(LoopStage.REVIEW, 1)
    assert (
        LoopStep.from_successor(session),
        LoopStep.from_successor(LoopEnd.NOTHING_FOUND),
    ) == (LoopStep(next_session=session), LoopStep(loop_end=LoopEnd.NOTHING_FOUND))


# %% the next session's first message


@pytest.mark.parametrize(
    ("stage", "skill"),
    [
        (LoopStage.REVIEW, PlanItemReviewSkill),
        (LoopStage.RESOLVE, PlanItemResolveSkill),
    ],
)
def test_the_prompt_invokes_the_stage_s_skill_on_the_pull_request(stage, skill):
    """
    The prompt names the stage's skill, the pull request, its round and the loop.
    """
    session = session_on_pull_request(stage, 2)
    assert session.prompt == (
        f"/{skill.skill_name} {LOOP_PULL_REQUEST.number} round=2 loop=on"
    )


# %% the session waiting for the turn's end


def test_a_recorded_session_is_taken_once(scratch_repository: ScratchRepository):
    """
    Taking the session forgets it, so a second turn's end starts nothing.
    """
    pending = PendingSession(scratch_repository.git)
    session = session_on_pull_request(LoopStage.RESOLVE, 1)

    pending.record(session)

    assert (pending.take(), pending.take()) == (session, None)
