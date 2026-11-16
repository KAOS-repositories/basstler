"""
A pull request as GitHub's REST API describes it, and the files it changes, as git reads
them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from basstler.git.commands import GitCommandRunner
from basstler.git.commit_range import CommitRange, FileVersions
from basstler.github.client import GitHubReader
from basstler.github.repository import Repository
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


class ComparisonStart(ABC):
    """
    The commit a pull request's changes are read from.
    """

    @abstractmethod
    def commit(self, git: GitCommandRunner, pull_request: RestPullRequest) -> str:
        """
        :param git: The checkout holding the pull request's commits.
        :param pull_request: The pull request.
        :return: The commit its changes are read from.
        """


@dataclass(frozen=True)
class MergeBaseStart(ComparisonStart):
    """
    The pull request's merge base, from which its whole change is read.
    """

    def commit(self, git: GitCommandRunner, pull_request: RestPullRequest) -> str:
        return git.merge_base(pull_request.base.commit, pull_request.head.commit)


@dataclass(frozen=True)
class CommitStart(ComparisonStart):
    """
    A commit given, such as the head commit a reviewer last read.
    """

    reference: str
    """
    Any reference git can resolve to the commit.
    """

    def commit(self, git: GitCommandRunner, pull_request: RestPullRequest) -> str:
        return git.commit_at(self.reference)


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

    def commit(self, git: GitCommandRunner, pull_request: RestPullRequest) -> str:
        return git.commit_at(f"{pull_request.head.commit}~{self.count}")


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


@dataclass(frozen=True)
class PullRequestChangesReader:
    """
    Reads pull requests of GitHub and their changes in one checkout.
    """

    git: GitCommandRunner
    """
    The checkout the changes are read in.
    """

    github: GitHubReader
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
        whole_change = CommitRange(
            self.git,
            self.git.merge_base(pull_request.base.commit, pull_request.head.commit),
            pull_request.head.commit,
        )
        start_commit = start.commit(self.git, pull_request)
        if start_commit == whole_change.base_commit:
            return PullRequestChanges(
                pull_request, whole_change, whole_change.file_versions()
            )
        commits = CommitRange(self.git, start_commit, pull_request.head.commit)
        own_paths = frozenset(change.path for change in whole_change.file_changes())
        return PullRequestChanges(
            pull_request, commits, commits.file_versions(own_paths)
        )
