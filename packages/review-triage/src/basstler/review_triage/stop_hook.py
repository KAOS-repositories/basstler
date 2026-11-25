"""
The hook Claude Code runs when a turn ends: it marks the mechanical files viewed of
every open pull request whose head this clone holds as a branch, once for each head
commit.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.review_triage.stop_hook
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from cyclopts import App
from pydantic import AliasChoices, AliasPath, Field

from basstler.exit_codes import StackExitCode
from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubReader, GitHubRestClient
from basstler.github.repository import HasRepository, Repository
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ClaudeCodeVariable, RepositoryStateLocation
from basstler.review_triage.command_line import mark_viewed
from basstler.text_file import TextFile

# %% the pull requests and the heads they were marked at


class PullRequestHeadCommit(ValidatedJSONModel):
    """
    A pull request and the commit its head branch points at.
    """

    number: int
    """
    The pull request's number.
    """

    head_commit: Annotated[
        str,
        Field(validation_alias=AliasChoices("head_commit", AliasPath("head", "sha"))),
    ]
    """
    The hash of the commit its head branch points at.
    """


class ViewedMarkings(ValidatedJSONModel):
    """
    The head each pull request's files were last marked viewed at.
    """

    pull_requests: tuple[PullRequestHeadCommit, ...] = ()
    """
    One entry per pull request.
    """

    def with_marked(self, pull_request: PullRequestHeadCommit) -> ViewedMarkings:
        """
        :param pull_request: A pull request whose files were just marked viewed.
        :return: These markings, with that pull request's entry at its current head.
        """
        others = tuple(
            marked
            for marked in self.pull_requests
            if marked.number != pull_request.number
        )
        return ViewedMarkings(pull_requests=(*others, pull_request))


# %% the pull requests of the session


@dataclass(frozen=True)
class SessionPullRequests(HasRepository):
    """
    The open pull requests of a repository whose head commit a session's clone holds as
    the tip of a local branch, and which of them are not marked viewed at that head.
    """

    git: GitCommandRunner
    """
    The checkout the session works in.
    """

    client: GitHubReader
    """
    Reads the repository's pull requests.
    """

    @property
    def stamp(self) -> Path:
        """
        The file recording the head each pull request was last marked viewed at.
        """
        return self.git.repository_state_path(RepositoryStateLocation.VIEWED_MARKINGS)

    def unmarked(self) -> list[PullRequestHeadCommit]:
        """
        :return: Every open pull request whose head is a local branch's tip and whose
            files are not marked viewed at that head, in the order GitHub lists them.
        """
        branch_tips = set(
            self.git.run("for-each-ref", "--format=%(objectname)", "refs/heads").split()
        )
        marked = self.markings().pull_requests
        listed = [
            PullRequestHeadCommit.from_json(entry)
            for entry in self.client.get_entries(
                self.repository.open_pull_requests_path
            )
        ]
        return [
            pull_request
            for pull_request in listed
            if pull_request.head_commit in branch_tips and pull_request not in marked
        ]

    def markings(self) -> ViewedMarkings:
        """
        :return: The heads the files were last marked viewed at; none before the first
            marking.
        """
        if not self.stamp.exists():
            return ViewedMarkings()
        return ViewedMarkings.from_json(json.loads(TextFile(self.stamp).read()))

    def record_marked(self, pull_request: PullRequestHeadCommit) -> None:
        """
        :param pull_request: A pull request whose files were just marked viewed, at the
            head it has now.
        """
        self.stamp.parent.mkdir(parents=True, exist_ok=True)
        TextFile(self.stamp).write(
            json.dumps(self.markings().with_marked(pull_request).to_json())
        )


# %% the command line

app = App(help=__doc__)
"""
The command, run with the project root as its working directory.
"""


@app.default
def mark_session_pull_requests() -> StackExitCode:
    """
    Mark viewed each open pull request whose head this clone holds as a branch, unless
    it already is at that head.

    :return: :attr:`StackExitCode.SUCCESS`; a failure to mark raises instead.
    """
    project_root = Path(
        os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd())
    )
    git = GitCommandRunner(project_root)
    session = SessionPullRequests(
        Repository.from_name_or_remote(None, git), git, GitHubRestClient()
    )
    for pull_request in session.unmarked():
        mark_viewed(pull_request.number)
        session.record_marked(pull_request)
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
