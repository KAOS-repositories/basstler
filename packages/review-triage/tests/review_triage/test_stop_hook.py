"""
Tests for :mod:`basstler.review_triage.stop_hook`: marking the pull request a session
works on viewed when a turn ends, once per head commit.
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
from basstler.review_triage.stop_hook import SessionPullRequest

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.scratch_repository import ScratchRepository
from .conftest import SAMPLE_REPOSITORY

# %% stand-ins and fixtures

SESSION_BRANCH = "claude/session-work"
"""
The branch the session works on, which the dataset's pull request is opened from.
"""


@dataclass
class BranchSearchReader(GitHubReader):
    """
    Answers the search for the open pull requests of one branch with the pull requests
    it holds, and every other read with nothing.
    """

    searched_path: str
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
        return [self.pull_requests if path == self.searched_path else []]


def pull_request_at(head_commit: str) -> dict[str, Any]:
    """
    :param head_commit: The commit the pull request's branch points at.
    :return: The sample pull request, opened from the session's branch at that commit.
    """
    payload = json.loads(
        DatasetLocation.SESSION_PULL_REQUEST.read_text(encoding="utf-8")
    )
    payload["head"]["sha"] = head_commit
    return payload


@pytest.fixture
def session(scratch_repository: ScratchRepository) -> SessionPullRequest:
    """
    :return: The session working on :data:`SESSION_BRANCH`, whose pull request is open
        at one commit.
    """
    scratch_repository.serve_origin_as(SAMPLE_REPOSITORY.clone_url)
    scratch_repository.write("work.txt", "work")
    scratch_repository.commit_everything("work")
    scratch_repository.run_git("switch", "--create", SESSION_BRANCH)
    return session_reading(scratch_repository, "a" * 40)


def session_reading(
    scratch_repository: ScratchRepository, head_commit: str
) -> SessionPullRequest:
    """
    :param scratch_repository: The checkout the session works in.
    :param head_commit: The commit GitHub reports the pull request's branch at.
    :return: The session, as it reads GitHub then.
    """
    return SessionPullRequest(
        repository=SAMPLE_REPOSITORY,
        git=scratch_repository.git,
        client=BranchSearchReader(
            SAMPLE_REPOSITORY.open_pull_requests_from_branch_path(SESSION_BRANCH),
            [pull_request_at(head_commit)],
        ),
    )


# %% which pull request to mark


def test_the_open_pull_request_of_the_checked_out_branch_is_to_be_marked(
    session: SessionPullRequest,
):
    assert session.unmarked().number == pull_request_at("a" * 40)["number"]


def test_a_branch_without_an_open_pull_request_marks_nothing(
    scratch_repository: ScratchRepository, session: SessionPullRequest
):
    scratch_repository.run_git("switch", "--detach")
    assert session.unmarked() is None


def test_a_head_already_marked_is_not_marked_again(session: SessionPullRequest):
    session.record_marked(session.unmarked())
    assert session.unmarked() is None


def test_a_head_pushed_since_is_marked_again(
    scratch_repository: ScratchRepository, session: SessionPullRequest
):
    session.record_marked(session.unmarked())
    pushed = session_reading(scratch_repository, "b" * 40)
    assert pushed.unmarked().head.object_hash == "b" * 40


def test_the_mark_is_kept_where_the_checkout_keeps_its_scratch_state(
    scratch_repository: ScratchRepository, session: SessionPullRequest
):
    session.record_marked(session.unmarked())
    assert session.stamp.parent == scratch_repository.git.repository_state_path(
        RepositoryStateLocation.DIRECTORY
    )


# %% what the plugin and the workflow do


def test_the_plugin_runs_the_hook_when_a_turn_ends():
    plugin_root = Path(os.environ[BasstlerVariable.PLUGIN_ROOT])
    manifest = json.loads(
        (plugin_root / PluginLocation.HOOKS / "hooks.json").read_text(encoding="utf-8")
    )
    (registration,) = manifest["hooks"]["Stop"]
    (hook,) = registration["hooks"]
    assert hook["command"].endswith(
        f"{PluginLocation.ENTRY_POINT_SCRIPT.as_posix()} "
        f"{basstler.review_triage.stop_hook.__spec__.name.removeprefix('basstler.')}"
    )
