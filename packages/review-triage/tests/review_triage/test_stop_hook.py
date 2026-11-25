"""
Tests for :mod:`basstler.review_triage.stop_hook`: marking viewed, when a turn ends, every
open pull request whose head the clone holds as a branch, once per head commit.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import basstler.review_triage.stop_hook
from basstler.github.client import GitHubReader
from basstler.locations import BasstlerVariable, PluginLocation, RepositoryStateLocation
from basstler.playbook.plugin import HookCommand
from basstler.review_triage.stop_hook import SessionPullRequests
from basstler.text_file import TextFile

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.scratch_repository import ScratchRepository
from .conftest import SAMPLE_REPOSITORY

# %% stand-ins and fixtures

SESSION_BRANCH = "claude/session-work"
"""
The branch the session works on, which the dataset's pull request is opened from.
"""

STACKED_BRANCH = "claude/stacked-work"
"""
A second local branch the session pushed, which another pull request is opened from.
"""


@dataclass
class OpenPullRequestsReader(GitHubReader):
    """
    Answers the listing of a repository's open pull requests with the ones it holds,
    and every other read with nothing.
    """

    listing_path: str
    """
    The one path whose listing is answered.
    """

    pull_requests: list[dict[str, Any]]
    """
    The listing's pull requests, as REST describes them.
    """

    def get(self, path: str) -> Any:
        raise AssertionError(f"no single resource is read, but {path}")

    def get_pages(self, path: str) -> list[Any]:
        return [self.pull_requests if path == self.listing_path else []]


def pull_request_at(number: int, head_commit: str) -> dict[str, Any]:
    """
    :param number: The pull request's number.
    :param head_commit: The commit the pull request's branch points at.
    :return: The sample pull request, renumbered, opened at that commit.
    """
    payload = json.loads(TextFile(DatasetLocation.SESSION_PULL_REQUEST).read())
    payload["number"] = number
    payload["head"]["sha"] = head_commit
    return payload


def branch_tip(scratch_repository: ScratchRepository, branch: str) -> str:
    """
    :return: The commit *branch* points at in the scratch clone.
    """
    return scratch_repository.git.run("rev-parse", branch)


@pytest.fixture
def clone(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    :return: A clone holding :data:`SESSION_BRANCH`, checked out, and
        :data:`STACKED_BRANCH` at a commit of its own.
    """
    scratch_repository.serve_origin_as(SAMPLE_REPOSITORY.clone_url)
    scratch_repository.write("work.txt", "work")
    scratch_repository.commit_everything("work")
    scratch_repository.run_git("switch", "--quiet", "--create", STACKED_BRANCH)
    scratch_repository.write("stacked.txt", "stacked")
    scratch_repository.commit_everything("stacked")
    scratch_repository.run_git("switch", "--quiet", "--create", SESSION_BRANCH, "HEAD~")
    return scratch_repository


def session_listing(
    clone: ScratchRepository, pull_requests: list[dict[str, Any]]
) -> SessionPullRequests:
    """
    :param clone: The checkout the session works in.
    :param pull_requests: The open pull requests GitHub lists.
    :return: The session, as it reads GitHub then.
    """
    return SessionPullRequests(
        repository=SAMPLE_REPOSITORY,
        git=clone.git,
        client=OpenPullRequestsReader(
            SAMPLE_REPOSITORY.open_pull_requests_path, pull_requests
        ),
    )


# %% which pull requests to mark


def test_every_open_pull_request_at_a_local_branch_tip_is_to_be_marked(
    clone: ScratchRepository,
):
    """
    The checked-out branch's pull request and the one of another local branch are both
    marked; one whose head this clone does not hold is not.
    """
    session = session_listing(
        clone,
        [
            pull_request_at(1, branch_tip(clone, SESSION_BRANCH)),
            pull_request_at(2, branch_tip(clone, STACKED_BRANCH)),
            pull_request_at(3, "c" * 40),
        ],
    )
    assert [pull_request.number for pull_request in session.unmarked()] == [1, 2]


def test_a_head_already_marked_is_not_marked_again(clone: ScratchRepository):
    """
    Only the pull request not marked at its head is left.
    """
    session = session_listing(
        clone,
        [
            pull_request_at(1, branch_tip(clone, SESSION_BRANCH)),
            pull_request_at(2, branch_tip(clone, STACKED_BRANCH)),
        ],
    )
    first, second = session.unmarked()
    session.record_marked(first)
    assert session.unmarked() == [second]


def test_a_head_pushed_since_is_marked_again(clone: ScratchRepository):
    """
    A new commit on a marked branch makes its pull request unmarked again.
    """
    session = session_listing(
        clone, [pull_request_at(1, branch_tip(clone, SESSION_BRANCH))]
    )
    (marked,) = session.unmarked()
    session.record_marked(marked)
    clone.write("more.txt", "more")
    clone.commit_everything("more")
    pushed = session_listing(
        clone, [pull_request_at(1, branch_tip(clone, SESSION_BRANCH))]
    )
    assert [pull_request.head_commit for pull_request in pushed.unmarked()] == [
        branch_tip(clone, SESSION_BRANCH)
    ]


def test_the_mark_is_kept_where_the_checkout_keeps_its_scratch_state(
    clone: ScratchRepository,
):
    """
    The stamp lives in the repository's state directory, shared by its worktrees.
    """
    session = session_listing(
        clone, [pull_request_at(1, branch_tip(clone, SESSION_BRANCH))]
    )
    session.record_marked(session.unmarked()[0])
    assert session.stamp.parent == clone.git.repository_state_path(
        RepositoryStateLocation.DIRECTORY
    )


# %% what the plugin and the workflow do


def test_the_plugin_runs_the_hook_when_a_turn_ends():
    plugin_root = Path(os.environ[BasstlerVariable.PLUGIN_ROOT])
    manifest = json.loads(
        (plugin_root / PluginLocation.HOOKS / "hooks.json").read_text(encoding="utf-8")
    )
    commands = [
        hook["command"]
        for registration in manifest["hooks"]["Stop"]
        for hook in registration["hooks"]
    ]
    expected_ending = (
        f"{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()} "
        f"{basstler.review_triage.stop_hook.__spec__.name.removeprefix('basstler.')}"
    )
    assert [command for command in commands if command.endswith(expected_ending)] == [
        f"{HookCommand.plugin_root_placeholder}/{expected_ending}"
    ]
