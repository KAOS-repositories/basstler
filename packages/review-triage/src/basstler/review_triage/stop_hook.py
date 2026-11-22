"""
The hook Claude Code runs when a turn ends: it marks the mechanical files of the pull
request the session works on viewed, once for each head commit.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.review_triage.stop_hook
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from cyclopts import App

from basstler.exit_codes import StackExitCode
from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubReader, GitHubRestClient
from basstler.github.repository import HasRepository, Repository
from basstler.github.rest_models import PullRequestAtHead, RestPullRequestSummary
from basstler.locations import ClaudeCodeVariable, RepositoryStateLocation
from basstler.review_triage.command_line import mark_viewed

# %% the pull request of the session


@dataclass(frozen=True)
class SessionPullRequest(HasRepository):
    """
    The open pull request of the branch a session has checked out in its repository, and
    whether the files of its current head are marked viewed.
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
        The file recording the head the files were last marked viewed at.
        """
        return self.git.repository_state_path(
            RepositoryStateLocation.VIEWED_MARKING_STAMP
        )

    def unmarked(self) -> RestPullRequestSummary | None:
        """
        :return: The pull request of the checked-out branch when the files of its
            current head are not marked viewed yet, ``None`` when there is none or they
            are.
        """
        branch = self.git.checked_out_branch()
        if not branch:
            return None
        pages = self.client.get_pages(
            self.repository.open_pull_requests_from_branch_path(branch)
        )
        listed = [
            RestPullRequestSummary.from_json(entry) for page in pages for entry in page
        ]
        if not listed:
            return None
        pull_request = listed[0]
        marked = self.marked_head()
        if marked is not None and marked.is_at(pull_request):
            return None
        return pull_request

    def marked_head(self) -> PullRequestAtHead | None:
        """
        :return: The head the files were last marked viewed at, ``None`` when they never
            were.
        """
        if not self.stamp.exists():
            return None
        return PullRequestAtHead.from_json(
            json.loads(self.stamp.read_text(encoding="utf-8"))
        )

    def record_marked(self, pull_request: RestPullRequestSummary) -> None:
        """
        :param pull_request: The pull request whose files were just marked viewed, at
            the head it has now.
        """
        self.stamp.parent.mkdir(parents=True, exist_ok=True)
        self.stamp.write_text(
            json.dumps(PullRequestAtHead.from_json(pull_request.to_json()).to_json()),
            encoding="utf-8",
        )


# %% the command line

app = App(help=__doc__)
"""
The command, run with the project root as its working directory.
"""


@app.default
def mark_session_pull_request() -> StackExitCode:
    """
    Mark the checked-out branch's pull request viewed, unless it already is at its
    current head or the branch has none open.

    :return: :attr:`StackExitCode.SUCCESS`; a failure to mark raises instead.
    """
    project_root = Path(
        os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd())
    )
    git = GitCommandRunner(project_root)
    session = SessionPullRequest(
        Repository.from_name_or_remote(None, git), git, GitHubRestClient()
    )
    pull_request = session.unmarked()
    if pull_request is not None:
        mark_viewed(pull_request.number)
        session.record_marked(pull_request)
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
