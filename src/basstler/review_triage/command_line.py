"""
The ``basstler review-triage`` commands: reporting which files of a pull request need
review, marking the others viewed, and writing a rename declaration.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from cyclopts import App

from basstler.exit_codes import ExitCode
from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubRestClient
from basstler.github.pull_request_changes import PullRequestChangesReader
from basstler.github.repository import PullRequestReference, Repository
from basstler.locations import ClaudeCodeVariable
from basstler.review_triage.command_names import ReviewTriageCommand
from basstler.review_triage.declaration import ArgumentDeclaration, TriageDeclaration
from basstler.review_triage.outputs import MarkdownReport, TriageOutput, ViewedMarking
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome
from basstler.review_triage.viewed_request import (
    MarkViewedRequest,
    ViewedMarkingRoutes,
)
from basstler.review_triage.viewed_setup import MarkViewedSetup
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""

# %% names and exit statuses


class ReviewTriageExitCode(ExitCode):
    """
    What a ``basstler review-triage`` command's exit status means.
    """

    SUCCESS = 0
    """
    The command did what it was asked.
    """


# %% publishing the triage


def named_or_remote(
    repository: str | None, git: GitCommandRunner, remote: str = "origin"
) -> Repository:
    """
    :param repository: A repository as ``owner/name``, or ``None``.
    :param git: The current checkout.
    :param remote: The remote whose repository is meant when none is named.
    :return: That repository, the one of ``remote`` when ``None``.
    """
    if repository:
        return Repository.parse(repository)
    return Repository.from_remote_url(git.run("remote", "get-url", remote))


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

    def outcome(self) -> TriageOutcome:
        """
        :return: The triage of the pull request.
        """
        git = GitCommandRunner(Path.cwd())
        changes = PullRequestChangesReader(git, GitHubRestClient()).read(
            named_or_remote(self.repository, git, self.remote), self.pull_request
        )
        default = PullRequestTriager()
        triager = replace(
            default,
            rename_sources=(
                *default.rename_sources,
                ArgumentDeclaration(self.declaration),
            ),
        )
        return triager.triage(changes)

    def publish(self, outputs: tuple[TriageOutput, ...]) -> None:
        """
        :param outputs: Where the outcome goes, in order.
        """
        outcome = self.outcome()
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
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
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
    workflow_repository: str | None = None,
    directly: bool = False,
    rename: tuple[str, ...] = (),
    rejected_rename: tuple[str, ...] = (),
) -> ReviewTriageExitCode:
    """
    Mark a pull request's mechanical files viewed for the logged-in account, or, where
    that fails, ask a repository's Actions to; then print the triage.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param workflow_repository: The repository whose Actions are asked when marking
        directly fails, as ``owner/name``; the checkout's ``origin`` by default.
    :param directly: Only mark them directly, never through Actions, as the workflow
        that marks them does.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    :raises GraphQLErrorsReturned: If marking them directly, alone, fails.
    :raises FilesNotMarkedViewed: If neither way marks them.
    """
    git = GitCommandRunner(Path.cwd())
    outcome = TriagePublication(
        pull_request,
        repository,
        TriageDeclaration.from_arguments(rename, rejected_rename),
    ).outcome()
    MarkdownReport().publish(outcome)
    routes = ViewedMarkingRoutes(
        ViewedMarking(GitHubRestClient()),
        MarkViewedRequest(
            named_or_remote(workflow_repository, git),
            PullRequestReference(named_or_remote(repository, git), pull_request),
        ),
        GitHubRestClient(),
        ClaudeCodeVariable.REMOTE.is_true(),
        directly,
    )
    logger.info(routes.mark(outcome))
    return ReviewTriageExitCode.SUCCESS


@review_triage_app.command(name=ReviewTriageCommand.REQUEST_MARK_VIEWED)
def request_mark_viewed(
    pull_request: int,
    *,
    repository: str | None = None,
    workflow_repository: str | None = None,
) -> ReviewTriageExitCode:
    """
    Ask a repository's mark-viewed workflow to mark a pull request's mechanical files
    viewed, for the account whose token that repository stores.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param workflow_repository: The repository whose workflow marks the files, as
        ``owner/name``; the checkout's ``origin`` by default.
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    """
    git = GitCommandRunner(Path.cwd())
    reference = PullRequestReference(named_or_remote(repository, git), pull_request)
    request = MarkViewedRequest(named_or_remote(workflow_repository, git), reference)
    runs = request.send(GitHubRestClient())
    logger.info(
        f"Asked {request.workflow_repository.full_name}'s Actions to mark the "
        f"mechanical files of {reference.url} viewed; the run shows at {runs}"
    )
    return ReviewTriageExitCode.SUCCESS


@review_triage_app.command(name=ReviewTriageCommand.SET_UP_MARK_VIEWED)
def set_up_mark_viewed(
    *,
    workflow_repository: str | None = None,
    repository: str | None = None,
    branch_or_tag: str = "main",
    on_every_pull_request: bool = False,
) -> ReviewTriageExitCode:
    """
    Set a repository's Actions up to mark files viewed, as far as a command can, and
    print what each step came to and the steps left to you.

    :param workflow_repository: The repository whose Actions mark the files, as
        ``owner/name``; the checkout's ``origin`` by default.
    :param repository: The repository the pull requests are opened on; the workflow
        repository's parent, or itself, by default.
    :param branch_or_tag: The basstler branch or tag the installed workflow runs.
    :param on_every_pull_request: Also run it for every pull request opened or updated
        on the workflow repository, which then defaults to the pull requests'.
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    """
    git = GitCommandRunner(Path.cwd())
    if on_every_pull_request and workflow_repository is None:
        workflow_repository = repository
    setup = MarkViewedSetup(
        named_or_remote(workflow_repository, git),
        Repository.parse(repository) if repository else None,
        branch_or_tag,
        on_every_pull_request,
    )
    logger.info(setup.run(GitHubRestClient()))
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
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    """
    logger.info(TriageDeclaration.from_arguments(rename, rejected_rename).comment())
    return ReviewTriageExitCode.SUCCESS
