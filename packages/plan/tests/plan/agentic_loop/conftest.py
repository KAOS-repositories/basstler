"""
The pull request and the sessions the agentic loop tests start on it.
"""

from __future__ import annotations

import pytest

from basstler.github.repository import Repository
from basstler.locations import ProjectLocation
from basstler.plan.agentic_loop.stage import LoopPullRequest, LoopStage, NextSession

from basstler_testing.scratch_repository import ScratchRepository

# %% the pull request

LOOP_REPOSITORY = Repository("example", "project")
"""
The repository the loop's pull request is opened on.
"""

LOOP_BRANCH = "claude/item-work"
"""
The pull request's head branch.
"""

LOOP_PULL_REQUEST = LoopPullRequest(LOOP_REPOSITORY, 17, LOOP_BRANCH)
"""
The pull request every stage in these tests works on.
"""


def session_on_pull_request(stage: LoopStage, review_round: int) -> NextSession:
    """
    :param stage: The stage the session runs.
    :param review_round: The review it runs or resolves.
    :return: A session of that stage on :data:`LOOP_PULL_REQUEST`.
    """
    return NextSession(
        stage=stage,
        repository=LOOP_PULL_REQUEST.repository,
        branch=LOOP_PULL_REQUEST.branch,
        pull_request=LOOP_PULL_REQUEST.number,
        review_round=review_round,
    )


@pytest.fixture
def loop_checkout(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    :return: A checkout of :data:`LOOP_BRANCH`, whose ``origin`` names
        :data:`LOOP_REPOSITORY`, with a notes branch that holds no loop setting.
    """
    scratch_repository.serve_origin_as(LOOP_REPOSITORY.clone_url)
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {ProjectLocation.PERSONAL_NOTES_DOCUMENT: "notes\n"}
    )
    scratch_repository.resolve_notes_remote_to()
    scratch_repository.run_git("switch", "--quiet", "--create", LOOP_BRANCH)
    return scratch_repository
