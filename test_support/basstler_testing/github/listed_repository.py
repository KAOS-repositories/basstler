"""
A repository answering its open pull requests and its commits' checks from fixed
records, and the records themselves as the REST API returns them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field as dataclasses_field
from enum import StrEnum

from basstler.github.pull_request_record import (
    CommitChecks,
    PullRequestField,
    PullRequestHeadKey,
)
from basstler.github.repository import Repository
from basstler.github.repository_access import PullRequestReader
from basstler.github.states import CombinedCheckState

from ..fork_checkout import UPSTREAM_BASE
from .pull_request_samples import PullRequestHeadRepository

# %% the commits a head points at, and their checks


class HeadCommit(StrEnum):
    """
    The commits a fetched pull request's head can point at.
    """

    CHECKED = "c0ffee0000000000000000000000000000000000"
    """
    A head commit the checks under test reported on.
    """

    UNCHECKED = "dec0de0000000000000000000000000000000000"
    """
    A head commit nothing has reported on.
    """


@dataclass(frozen=True)
class ChecksReportedOn(CommitChecks):
    """
    Answers each commit's check verdict from a fixed table rather than from GitHub.
    """

    state_by_commit: Mapping[str, CombinedCheckState] = dataclasses_field(
        default_factory=dict
    )
    """
    The verdict over each commit's checks; a commit absent here has no checks.
    """

    def check_state(self, commit: str) -> CombinedCheckState:
        return self.state_by_commit.get(commit, CombinedCheckState.NOT_REPORTED)


# %% pull request records


def an_api_record(
    number: int = 7,
    head: str = "a-branch",
    base: str = UPSTREAM_BASE,
    draft: bool = False,
    labels: list[str] | None = None,
    body: str = "",
    head_repository: Repository | None = PullRequestHeadRepository.FORK.value,
    title: str | None = None,
    head_commit: str = HeadCommit.UNCHECKED,
) -> dict:
    """
    :param number: The pull request number.
    :param head: The head branch reference.
    :param base: The base branch reference.
    :param draft: Whether the pull request is a draft.
    :param labels: The label names it carries.
    :param body: The description to read a session link out of.
    :param head_repository: The repository the head lives in, ``None`` once deleted.
    :param title: The pull request's title.
    :param head_commit: The commit the head points at.
    :return: One pull request in the shape the REST API returns it.
    """
    return {
        PullRequestField.NUMBER.key: number,
        PullRequestField.HEAD.key: {
            PullRequestHeadKey.REFERENCE: head,
            PullRequestHeadKey.HEAD_REPOSITORY: (
                None
                if head_repository is None
                else {PullRequestHeadKey.FULL_NAME: head_repository.full_name}
            ),
            PullRequestHeadKey.COMMIT: head_commit,
        },
        PullRequestField.BASE.key: {"ref": base},
        PullRequestField.DRAFT.key: draft,
        PullRequestField.LABELS.key: [{"name": name} for name in labels or []],
        PullRequestField.BODY.key: body,
        PullRequestField.TITLE.key: title,
    }


# %% a repository listing them


@dataclass(frozen=True)
class ListedRepository(ChecksReportedOn, PullRequestReader):
    """
    A repository answering its open pull requests and its commits' checks from fixed
    records.
    """

    records: tuple[dict, ...] = ()
    """
    Its open pull requests, as the REST API returns them.
    """

    def open_pull_requests(self) -> list[dict]:
        return list(self.records)

    def pull_request(self, number: int) -> dict:
        return next(
            record
            for record in self.records
            if record[PullRequestField.NUMBER.key] == number
        )
