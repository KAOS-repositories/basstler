"""
A pull request as GitHub's REST API describes it, and the files it changes, as git reads
them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from basstler.git.commands import GitCommandRunner
from basstler.git.commit_range import CommitRange, FileChange
from basstler.github.client import GitHubReader
from basstler.github.repository import Repository
from basstler.github.web_page import AbsentAsEmpty
from basstler.json_model import ValidatedJSONModel

# %% the pull request


class BranchTip(ValidatedJSONModel):
    """
    One end of a pull request: a branch and the commit it points at.
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
    The commits its change runs between, from its merge base to its head commit.
    """

    files: tuple[FileChange, ...]
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

    def read(self, repository: Repository, number: int) -> PullRequestChanges:
        """
        :param repository: The repository the pull request is opened on.
        :param number: The pull request's number.
        :return: The pull request and its changes, its commits fetched first when the
            checkout lacks either end.
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
        merge_base = self.git.run(
            "merge-base", pull_request.base.commit, pull_request.head.commit
        )
        commits = CommitRange(self.git, merge_base, pull_request.head.commit)
        return PullRequestChanges(pull_request, commits, commits.changes())
