"""
A token that may not read check runs reads a commit's CI from its workflow runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest

from basstler.credential_origin import CredentialOrigin
from basstler.github.exceptions import GitHubRequestFailed
from basstler.github.repository import Repository
from basstler.github.repository_access import GitHubRepository
from basstler.github.states import CombinedCheckState

COMMIT = "5885cc06f4c9408bb3bb0bb5e8d7abd976856b9c"
"""
The commit whose CI is read.
"""


class FineGrainedToken(CredentialOrigin):
    """
    A token with no checks permission, as every fine-grained token is.
    """

    def describe_credential(self) -> str:
        return "a fine-grained token"

    def suggest_renewal(self) -> str:
        return "create another"


class ChecksRefusingClient:
    """
    Answers like GitHub to a fine-grained token: check runs refused, workflow runs read
    unless ``reads_actions`` is false.
    """

    def __init__(self, workflow_runs: list[dict[str, Any]], reads_actions: bool = True):
        self.workflow_runs = workflow_runs
        self.reads_actions = reads_actions

    def refuse(self, path: str) -> GitHubRequestFailed:
        return GitHubRequestFailed.for_status(
            HTTPStatus.FORBIDDEN,
            "Resource not accessible by personal access token",
            "GET",
            path,
            FineGrainedToken(),
        )

    def get_pages(self, path: str) -> Iterator[dict[str, Any]]:
        raise self.refuse(path)

    def get(self, path: str) -> dict[str, Any]:
        assert f"head_sha={COMMIT}" in path
        if not self.reads_actions:
            raise self.refuse(path)
        return {
            "total_count": len(self.workflow_runs),
            "workflow_runs": self.workflow_runs,
        }


def state_over(
    runs: list[dict[str, Any]], reads_actions: bool = True
) -> CombinedCheckState:
    """
    :param runs: The commit's workflow runs.
    :param reads_actions: Whether the token may read them.
    :return: The commit's check state as the repository reads it.
    """
    repository = GitHubRepository(
        Repository.parse("team/project"), ChecksRefusingClient(runs, reads_actions)
    )
    return repository.check_state(COMMIT)


@pytest.mark.parametrize(
    ("runs", "state"),
    [
        (
            [{"status": "completed", "conclusion": "success"}],
            CombinedCheckState.SUCCESS,
        ),
        (
            [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "failure"},
            ],
            CombinedCheckState.FAILURE,
        ),
        (
            [
                {"status": "completed", "conclusion": "skipped"},
                {"status": "in_progress", "conclusion": None},
            ],
            CombinedCheckState.PENDING,
        ),
        ([], CombinedCheckState.NOT_REPORTED),
    ],
    ids=["passed", "one-failed", "one-running", "none"],
)
def test_refused_check_runs_read_the_workflow_runs(
    runs: list[dict[str, Any]], state: CombinedCheckState
):
    assert state_over(runs) == state


def test_a_token_that_reads_neither_leaves_the_state_unreported():
    assert (
        state_over(
            [{"status": "completed", "conclusion": "failure"}], reads_actions=False
        )
        == CombinedCheckState.NOT_REPORTED
    )
