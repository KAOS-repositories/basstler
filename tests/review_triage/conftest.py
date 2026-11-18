"""
Fixtures the review triage suites share: the sample rename and the sample pull request
committed to a scratch repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import pytest

from basstler.github.client import (
    GitHubReader,
    GitHubResponse,
    GitHubWrite,
    GitHubWriter,
)
from basstler.github.graphql import GraphQLRequest, GraphQLResponse
from basstler.github.repository import Repository
from basstler.github.pull_request_changes import (
    PullRequestChanges,
    PullRequestChangesReader,
)
from basstler.github.review_models import PageInfo
from basstler.locations import ReviewTriageLocation
from basstler.review_triage.detection import RenameDetection
from basstler.review_triage.outputs import (
    FilesPageRequest,
    ListedFile,
    ListedFilesAnswer,
    ListedFilesPage,
    ListedPullRequest,
    ViewedFile,
)
from basstler.review_triage.renames import Rename, RenameMap

from ..scratch_repository import ScratchRepository
from .samples import DescriptionSample, PullRequestSample

# %% stand-ins for GitHub

SAMPLE_REPOSITORY = Repository("example", "project")
"""
The repository the sample pull request is opened on.
"""


@dataclass(frozen=True)
class OnePullRequestReader(GitHubReader):
    """
    Answers every read with one pull request's payload.
    """

    payload: dict[str, Any]
    """
    The pull request's REST payload.
    """

    def get(self, path: str) -> Any:
        return self.payload

    def get_pages(self, path: str) -> list[Any]:
        return [self.payload]


@dataclass
class RecordingWriter(GitHubWriter):
    """
    Records every write and answers each with the same body.
    """

    answer: dict[str, Any]
    """
    The body every write is answered with.
    """

    sent: list[GitHubWrite] = field(default_factory=list)
    """
    Every write sent, oldest first.
    """

    def attempt_send(self, write: GitHubWrite) -> GitHubResponse:
        self.sent.append(write)
        return GitHubResponse(self.answer)


@dataclass
class FileListingWriter(GitHubWriter):
    """
    Records every write, answers the query for a pull request's files with one page per
    entry of :attr:`pages`, and every other request with an empty result.
    """

    head_commit: str
    """
    The pull request's head commit the listing reports.
    """

    pages: tuple[tuple[PurePosixPath, ...], ...]
    """
    The paths on each page of the listing, first page first.
    """

    sent: list[GraphQLRequest] = field(default_factory=list)
    """
    Every request sent, oldest first.
    """

    @property
    def marked_paths(self) -> list[PurePosixPath]:
        """
        The path of every file a mutation marked viewed, in the order they were sent.
        """
        document = ReviewTriageLocation.MARK_FILE_AS_VIEWED.read_text()
        return [
            ViewedFile.from_json(request.variables).path
            for request in self.sent
            if request.query == document
        ]

    def attempt_send(self, write: GitHubWrite) -> GitHubResponse:
        assert isinstance(write, GraphQLRequest)
        self.sent.append(write)
        if write.query != ReviewTriageLocation.PULL_REQUEST_FILES.read_text():
            return GitHubResponse(GraphQLResponse(data={}).to_json())
        cursor = FilesPageRequest.from_json(write.variables).cursor
        index = int(cursor) if cursor else 0
        next_page = index + 1
        page = ListedFilesPage(
            tuple(ListedFile(path) for path in self.pages[index]),
            PageInfo(next_page < len(self.pages), str(next_page)),
        )
        answer = ListedFilesAnswer(ListedPullRequest(self.head_commit, page))
        return GitHubResponse(GraphQLResponse(data=answer.to_json()).to_json())


# %% fixtures


@pytest.fixture
def old_name_renamed() -> RenameMap:
    """
    :return: The renames of the samples: ``old_name`` to ``new_name``.
    """
    return RenameMap((Rename("old_name", "new_name", RenameDetection()),))


@pytest.fixture
def sample_payload(scratch_repository: ScratchRepository) -> dict[str, Any]:
    """
    Commit the sample pull request's base tree, then its head tree on top.

    :param scratch_repository: The repository to commit in.
    :return: The pull request's payload, naming the two commits.
    """
    for path, text in PullRequestSample.BASE_TREE.files().items():
        scratch_repository.write(path, text)
    scratch_repository.commit_everything("base")
    base_commit = scratch_repository.git.commit_at("HEAD")
    scratch_repository.run_git("rm", "-r", "--quiet", ".")
    for path, text in PullRequestSample.HEAD_TREE.files().items():
        scratch_repository.write(path, text)
    scratch_repository.commit_everything("head")
    payload = PullRequestSample.PAYLOAD.payload()
    payload["base"]["sha"] = base_commit
    payload["head"]["sha"] = scratch_repository.git.commit_at("HEAD")
    return payload


def read_sample(
    scratch_repository: ScratchRepository,
    payload: dict[str, Any],
    description: DescriptionSample,
) -> PullRequestChanges:
    """
    :param scratch_repository: The repository the sample is committed in.
    :param payload: The sample's payload.
    :param description: The description the pull request carries.
    :return: The sample pull request read with that description.
    """
    payload["body"] = description.read()
    return PullRequestChangesReader(
        scratch_repository.git, OnePullRequestReader(payload)
    ).read(SAMPLE_REPOSITORY, payload["number"])


@pytest.fixture
def sample_changes(
    scratch_repository: ScratchRepository, sample_payload: dict[str, Any]
) -> PullRequestChanges:
    """
    :return: The sample pull request, its description declaring nothing.
    """
    return read_sample(
        scratch_repository, sample_payload, DescriptionSample.WITHOUT_DECLARATION
    )
