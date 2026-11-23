"""
Tests for the bodies GitHub's writes send: their own fields, under GitHub's keys,
without the target they are sent to.
"""

from __future__ import annotations

from typing import Any

import pytest

from basstler.github.client import GitHubWrite
from basstler.github.issue import (
    ClosingReason,
    IssueClosing,
    IssueComment,
    IssueState,
    NewIssue,
)
from basstler.github.label import LabelReplacement, NewLabel, RepositoryLabel
from basstler.github.pull_request import NewPullRequest, PullRequestDescription
from basstler.git.branch import Branch
from basstler.github.file_proposal import NewBranch
from basstler.github.fork_sync import ForkFastForward
from basstler.github.repository import Repository
from basstler.github.workflow_run import WorkflowDispatch
from basstler.locations import WorkflowLocation

# %% the writes and the bodies GitHub reads from them

REPOSITORY = Repository("example-owner", "example-repo")
LABEL = RepositoryLabel("bug", "Something is broken")

FORK = Repository("a-forker", REPOSITORY.name)
"""
A fork of :data:`REPOSITORY`, carrying a branch proposed to it.
"""

WRITTEN_BODIES: list[tuple[GitHubWrite, dict[str, Any]]] = [
    (
        NewIssue(REPOSITORY, "a title", "a body", ["bug"]),
        {"title": "a title", "body": "a body", "labels": ["bug"]},
    ),
    (IssueComment(REPOSITORY, 1, "a comment"), {"body": "a comment"}),
    (
        IssueClosing(REPOSITORY, 1, ClosingReason.COMPLETED),
        {"state": IssueState.CLOSED, "state_reason": ClosingReason.COMPLETED},
    ),
    (
        IssueClosing(REPOSITORY, 1),
        {"state": IssueState.CLOSED, "state_reason": None},
    ),
    (NewLabel(REPOSITORY, LABEL), LABEL.to_json()),
    (LabelReplacement(REPOSITORY, 1, ["bug"]), {"labels": ["bug"]}),
    (
        NewPullRequest(
            Branch(REPOSITORY, "main"),
            Branch(REPOSITORY, "feature"),
            "a title",
        ),
        {
            "title": "a title",
            "head": "feature",
            "base": "main",
            "body": "",
            "draft": True,
        },
    ),
    (
        NewPullRequest(
            Branch(REPOSITORY, "main"),
            Branch(FORK, "feature"),
            "a title",
        ),
        {
            "title": "a title",
            "head": f"{FORK.owner}:feature",
            "base": "main",
            "body": "",
            "draft": True,
        },
    ),
    (
        NewBranch(
            repository=REPOSITORY,
            branch=Branch(REPOSITORY, "feature"),
            start_commit="a-commit",
        ),
        {"ref": Branch(REPOSITORY, "feature").reference, "sha": "a-commit"},
    ),
    (
        ForkFastForward(
            repository=FORK, object_hash="a-commit", branch=Branch(FORK, "main")
        ),
        {"sha": "a-commit"},
    ),
    (PullRequestDescription(REPOSITORY, 1, "a description"), {"body": "a description"}),
    (
        WorkflowDispatch(REPOSITORY, WorkflowLocation.PLAN_SITE, "main"),
        {"ref": "main"},
    ),
]


# %% bodies


@pytest.mark.parametrize(
    ("write", "body"),
    WRITTEN_BODIES,
    ids=[type(write).__name__ for write, _ in WRITTEN_BODIES],
)
def test_a_write_sends_its_own_fields_without_its_target(
    write: GitHubWrite, body: dict[str, Any]
):
    assert write.to_json() == body
