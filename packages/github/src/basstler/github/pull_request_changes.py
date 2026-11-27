"""
A pull request as GitHub's REST API describes it, and the files it changes, as git reads
them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from pydantic import Field

from basstler.git.commands import GitCommandRunner
from basstler.git.commit_range import CommitRange, FileVersions
from basstler.github.client import GitHubFullReader
from basstler.github.repository import Repository
from basstler.github.repository_access import GitHubPath
from basstler.github.rest_models import RestReview
from basstler.github.review_models import Author
from basstler.github.states import ReviewState
from basstler.github.web_page import AbsentAsEmpty
from basstler.json_model import ValidatedJSONModel

# %% the pull request


class RepositoryName(ValidatedJSONModel):
    """
    A repository as a pull request's end names it.
    """

    full_name: str
    """
    The repository as ``owner/name``.
    """

    @property
    def repository(self) -> Repository:
        """
        The repository it names.
        """
        return Repository.parse(self.full_name)


class BranchTip(ValidatedJSONModel):
    """
    One end of a pull request: a branch and the commit it points at.
    """

    repository: Annotated[RepositoryName | None, Field(alias="repo")]
    """
    The repository holding the branch, ``None`` once it is deleted.
    """

    commit: Annotated[str, Field(alias="sha")]
    """
    The commit the branch points at.
    """

    branch: Annotated[str, Field(alias="ref")]
    """
    The branch's name.
    """


class RestPullRequest(ValidatedJSONModel):
    """
    One pull request as REST describes it, read for its description and its two ends.
    """

    number: int
    """
    Its number in its repository.
    """

    node_identifier: Annotated[str, Field(alias="node_id")]
    """
    What GitHub's GraphQL API identifies it by.
    """

    description: Annotated[str, AbsentAsEmpty(), Field(alias="body")]
    """
    Its description, in Markdown; empty when it has none.
    """

    base: BranchTip
    """
    The branch it merges into.
    """

    head: BranchTip
    """
    The branch carrying its changes.
    """

    @property
    def head_reference(self) -> str:
        """
        The ref the base repository keeps the pull request's head commit under.
        """
        return f"refs/pull/{self.number}/head"


# %% where the changes are read from


@dataclass(frozen=True)
class FetchedPullRequest:
    """
    A pull request whose commits a checkout holds, with where it was read from.
    """

    git: GitCommandRunner
    """
    The checkout holding its commits.
    """

    github: GitHubFullReader
    """
    Where it was read from.
    """

    repository: Repository
    """
    The repository it is opened on.
    """

    pull_request: RestPullRequest
    """
    The pull request.
    """

    @property
    def merge_base(self) -> str:
        """
        The commit its whole change is read from.
        """
        return self.git.merge_base(
            self.pull_request.base.commit, self.pull_request.head.commit
        )


class StartReason(StrEnum):
    """
    Why the changes are read from the commit they start at, as the report says it.
    """

    MERGE_BASE = "the merge base"
    """
    The whole change is read.
    """

    GIVEN_COMMIT = "the commit given"
    """
    The commit was named on the command line.
    """

    LAST_COMMITS = "the commit before the last commits"
    """
    Only the pull request's last commits are read.
    """

    LAST_REVIEW = "your last review"
    """
    The commit is the head the viewer's last submitted review was made against.
    """

    VIEWED_FILES = "where you last viewed each file"
    """
    Each file is read from the head the viewer last viewed it at, else the merge base.
    """


@dataclass(frozen=True)
class StartCommit:
    """
    The commit a pull request's changes are read from, and why.
    """

    commit: str
    """
    The commit.
    """

    reason: StartReason
    """
    Why the changes start there.
    """


class ComparisonStart(ABC):
    """
    The commit a pull request's changes are read from.
    """

    @abstractmethod
    def start_commit(self, fetched: FetchedPullRequest) -> StartCommit:
        """
        :param fetched: The pull request, its commits in the checkout.
        :return: The commit its changes are read from.
        """


@dataclass(frozen=True)
class MergeBaseStart(ComparisonStart):
    """
    The pull request's merge base, from which its whole change is read.
    """

    def start_commit(self, fetched: FetchedPullRequest) -> StartCommit:
        return StartCommit(fetched.merge_base, StartReason.MERGE_BASE)


@dataclass(frozen=True)
class CommitStart(ComparisonStart):
    """
    A commit given, such as the head commit a reviewer last read.
    """

    reference: str
    """
    Any reference git can resolve to the commit.
    """

    def start_commit(self, fetched: FetchedPullRequest) -> StartCommit:
        return StartCommit(
            fetched.git.commit_at(self.reference), StartReason.GIVEN_COMMIT
        )


@dataclass(frozen=True)
class LastCommitsStart(ComparisonStart):
    """
    The commit before the pull request's last commits, following first parents from its
    head, so a merge into it counts as one commit.
    """

    count: int
    """
    How many of its last commits the changes span.
    """

    def start_commit(self, fetched: FetchedPullRequest) -> StartCommit:
        return StartCommit(
            fetched.git.commit_at(f"{fetched.pull_request.head.commit}~{self.count}"),
            StartReason.LAST_COMMITS,
        )


@dataclass(frozen=True)
class LastReviewStart(ComparisonStart):
    """
    The head commit of the last review the credential's account submitted on the pull
    request, else its merge base, as for a credential GitHub names no account for, such
    as an Actions token.
    """

    def start_commit(self, fetched: FetchedPullRequest) -> StartCommit:
        account = fetched.github.attempt_get(GitHubPath.AUTHENTICATED_USER)
        if account.is_forbidden:
            return MergeBaseStart().start_commit(fetched)
        viewer = Author.from_json(account.raise_if_failed()).login
        reviewed_commits = [
            review.commit
            for page in fetched.github.get_pages(
                fetched.repository.pull_request_reviews_path(
                    fetched.pull_request.number
                )
            )
            for review in map(RestReview.from_json, page)
            if review.author.login == viewer
            and review.state != ReviewState.PENDING
            and review.commit is not None
        ]
        if not reviewed_commits:
            return MergeBaseStart().start_commit(fetched)
        commit = reviewed_commits[-1]
        if fetched.git.commit_or_none(f"{commit}^{{commit}}") is None:
            fetched.git.fetch(fetched.repository.clone_url, commit)
        return StartCommit(commit, StartReason.LAST_REVIEW)


# %% the pull request with its changes


@dataclass(frozen=True)
class PullRequestChanges:
    """
    A pull request and the files it changes.
    """

    pull_request: RestPullRequest
    """
    The pull request.
    """

    commits: CommitRange
    """
    The commits its change runs between, from the commit the changes are read from to
    its head commit.
    """

    files: tuple[FileVersions, ...]
    """
    Every file it changes.
    """

    start: StartCommit
    """
    The commit the changes are read from, and why.
    """


@dataclass(frozen=True)
class PullRequestChangesReader:
    """
    Reads pull requests of GitHub and their changes in one checkout.
    """

    git: GitCommandRunner
    """
    The checkout the changes are read in.
    """

    github: GitHubFullReader
    """
    Where the pull request is read from.
    """

    def read(
        self,
        repository: Repository,
        number: int,
        start: ComparisonStart,
    ) -> PullRequestChanges:
        """
        :param repository: The repository the pull request is opened on.
        :param number: The pull request's number.
        :param start: Where the changes are read from.
        :return: The pull request and the changes of the files it changes, its commits
            fetched first when the checkout lacks either end.
        """
        pull_request = RestPullRequest.from_json(
            self.github.get(repository.pull_request_path(number))
        )
        if None in (
            self.git.commit_or_none(f"{pull_request.base.commit}^{{commit}}"),
            self.git.commit_or_none(f"{pull_request.head.commit}^{{commit}}"),
        ):
            self.git.fetch(
                repository.clone_url,
                pull_request.head_reference,
                pull_request.base.branch,
            )
        fetched = FetchedPullRequest(self.git, self.github, repository, pull_request)
        whole_change = CommitRange(
            self.git, fetched.merge_base, pull_request.head.commit
        )
        start_commit = start.start_commit(fetched)
        if start_commit.commit == whole_change.base_commit:
            return PullRequestChanges(
                pull_request, whole_change, whole_change.file_versions(), start_commit
            )
        commits = CommitRange(self.git, start_commit.commit, pull_request.head.commit)
        own_paths = frozenset(change.path for change in whole_change.file_changes())
        return PullRequestChanges(
            pull_request, commits, commits.file_versions(own_paths), start_commit
        )
