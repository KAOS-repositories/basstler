"""
The ``basstler review-triage`` commands: reporting which files of a pull request need
review, marking the others viewed, and writing a rename declaration.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from cyclopts import App

from basstler.exit_codes import ExitCode
from basstler.github.client import GitHubRestClient
from basstler.git.commands import GitCommandRunner
from basstler.github.pull_request_changes import PullRequestChangesReader
from basstler.github.repository import Repository
from basstler.locations import PackageLocation
from basstler.review_triage.declaration import ArgumentDeclaration, TriageDeclaration
from basstler.review_triage.outputs import MarkdownReport, TriageOutput, ViewedMarking
from basstler.review_triage.triage import PullRequestTriager
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""

# %% names and exit statuses


class ReviewTriageCommand(StrEnum):
    """
    The ``basstler review-triage`` command group and its commands, by name.
    """

    GROUP = "review-triage"
    """
    The command group itself.
    """

    REPORT = "report"
    """
    Print which files of a pull request need review, as Markdown.
    """

    MARK_VIEWED = "mark-viewed"
    """
    Mark a pull request's mechanical files viewed for the logged-in account.
    """

    DECLARE = "declare"
    """
    Print the description comment declaring renames.
    """

    @property
    def invocation(self) -> str:
        """
        The command line running this command.
        """
        return f"{PackageLocation.DIRECTORY.name} {ReviewTriageCommand.GROUP} {self}"


class ReviewTriageExitCode(ExitCode):
    """
    What a ``basstler review-triage`` command's exit status means.
    """

    SUCCESS = 0
    """
    The command did what it was asked.
    """


# %% publishing the triage


@dataclass(frozen=True)
class TriagePublication:
    """
    Triages one pull request in the current checkout and hands the outcome to outputs.
    """

    pull_request: int
    """
    The pull request's number.
    """

    repository: str | None = None
    """
    Its repository as ``owner/name``, the repository of :attr:`remote` when ``None``.
    """

    declaration: TriageDeclaration = field(default_factory=TriageDeclaration)
    """
    Renames given and rejected beyond the description's, outranking them.
    """

    remote: str = "origin"
    """
    The remote whose repository the pull request is looked up in when
    :attr:`repository` is ``None``.
    """

    def publish(self, outputs: tuple[TriageOutput, ...]) -> None:
        """
        :param outputs: Where the outcome goes, in order.
        """
        git = GitCommandRunner(Path.cwd())
        repository = (
            Repository.parse(self.repository)
            if self.repository
            else Repository.from_remote_url(git.run("remote", "get-url", self.remote))
        )
        changes = PullRequestChangesReader(git, GitHubRestClient()).read(
            repository, self.pull_request
        )
        default = PullRequestTriager()
        triager = replace(
            default,
            rename_sources=(
                *default.rename_sources,
                ArgumentDeclaration(self.declaration),
            ),
        )
        outcome = triager.triage(changes)
        for output in outputs:
            output.publish(outcome)


# %% the commands

review_triage_app = App(
    name=ReviewTriageCommand.GROUP,
    help="Tell a pull request's mechanical files from those a reviewer has to read.",
)
"""
The ``review-triage`` command group.
"""


@review_triage_app.command(name=ReviewTriageCommand.REPORT)
def report(
    pull_request: int,
    *,
    repository: str | None = None,
    rename: tuple[str, ...] = (),
    rejected_rename: tuple[str, ...] = (),
) -> ReviewTriageExitCode:
    """
    Print which files of a pull request need review, as Markdown.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    """
    TriagePublication(
        pull_request,
        repository,
        TriageDeclaration.from_arguments(rename, rejected_rename),
    ).publish((MarkdownReport(),))
    return ReviewTriageExitCode.SUCCESS


@review_triage_app.command(name=ReviewTriageCommand.MARK_VIEWED)
def mark_viewed(
    pull_request: int,
    *,
    repository: str | None = None,
    rename: tuple[str, ...] = (),
    rejected_rename: tuple[str, ...] = (),
) -> ReviewTriageExitCode:
    """
    Mark a pull request's mechanical files viewed for the account whose GitHub
    credential is configured, and print the triage.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    """
    TriagePublication(
        pull_request,
        repository,
        TriageDeclaration.from_arguments(rename, rejected_rename),
    ).publish((ViewedMarking(GitHubRestClient()), MarkdownReport()))
    return ReviewTriageExitCode.SUCCESS


@review_triage_app.command(name=ReviewTriageCommand.DECLARE)
def declare(
    *, rename: tuple[str, ...] = (), rejected_rename: tuple[str, ...] = ()
) -> ReviewTriageExitCode:
    """
    Print the comment declaring renames, to paste into a pull request's description.

    :param rename: A rename as ``old=new``; repeatable.
    :param rejected_rename: An old identifier whose detected rename is rejected;
        repeatable.
    """
    logger.info(TriageDeclaration.from_arguments(rename, rejected_rename).comment())
    return ReviewTriageExitCode.SUCCESS
