"""
The ``basstler review-triage`` commands: reporting which files of a pull request need
review, marking the others viewed, and writing a rename declaration.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from cyclopts import App, Group, Parameter, validators

from basstler.exit_codes import ExitCode
from basstler.github.client import GitHubRestClient
from basstler.git.commands import GitCommandRunner
from basstler.github.pull_request_changes import (
    CommitStart,
    ComparisonStart,
    LastCommitsStart,
    MergeBaseStart,
    PullRequestChangesReader,
)
from basstler.github.repository import Repository
from basstler.locations import PackageLocation
from basstler.review_triage.declaration import ArgumentDeclaration, TriageDeclaration
from basstler.review_triage.outputs import MarkdownReport, TriageOutput, ViewedMarking
from basstler.review_triage.rules import (
    ReviewTriageSettings,
    RuleSelection,
    TriageRule,
)
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

    start: ComparisonStart = MergeBaseStart()
    """
    Where the changes are triaged from.
    """

    remote: str = "origin"
    """
    The remote whose repository the pull request is looked up in when
    :attr:`repository` is ``None``.
    """

    rule_options: RuleSelection = RuleSelection()
    """
    The rules turned on and off on the command line, outranking the project's settings.
    """

    @classmethod
    def from_arguments(
        cls,
        pull_request: int,
        repository: str | None,
        declaration: TriageDeclaration,
        since: str | None,
        last: int | None,
        select_rules: tuple[TriageRule, ...] = (),
        ignore_rules: tuple[TriageRule, ...] = (),
    ) -> TriagePublication:
        """
        :param pull_request: The pull request's number.
        :param repository: Its repository as ``owner/name``, or ``None``.
        :param declaration: Renames given and rejected on the command line.
        :param since: The commit to triage from, or ``None``.
        :param last: How many of the last commits to triage, or ``None``.
        :param select_rules: The rules to turn on.
        :param ignore_rules: The rules to turn off.
        :return: The publication triaging from *since*, else from before the *last*
            commits, else from the merge base.
        """
        if since is not None:
            start: ComparisonStart = CommitStart(since)
        elif last is not None:
            start = LastCommitsStart(last)
        else:
            start = MergeBaseStart()
        return cls(
            pull_request,
            repository,
            declaration,
            start,
            rule_options=RuleSelection(
                frozenset(select_rules), frozenset(ignore_rules)
            ),
        )

    def publish(self, outputs: tuple[TriageOutput, ...]) -> None:
        """
        :param outputs: Where the outcome goes, in order.
        """
        git = GitCommandRunner(Path.cwd())
        checkout = Path(git.run("rev-parse", "--show-toplevel"))
        repository = (
            Repository.parse(self.repository)
            if self.repository
            else Repository.from_remote_url(git.run("remote", "get-url", self.remote))
        )
        changes = PullRequestChangesReader(git, GitHubRestClient()).read(
            repository, self.pull_request, self.start
        )
        default = PullRequestTriager()
        triager = replace(
            default,
            rename_sources=(
                *default.rename_sources,
                ArgumentDeclaration(self.declaration),
            ),
            rules=self.rule_options.applied_to(
                ReviewTriageSettings.from_checkout(checkout).selection
            ),
        )
        outcome = triager.triage(changes)
        for output in outputs:
            output.publish(outcome)


# %% the commands

COMPARISON_START_GROUP = Group(
    "Where to triage from", validator=validators.MutuallyExclusive()
)
"""
The options choosing the commit a triage starts from, at most one of them given.
"""

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
    since: Annotated[str | None, Parameter(group=COMPARISON_START_GROUP)] = None,
    last: Annotated[
        int | None,
        Parameter(group=COMPARISON_START_GROUP, validator=validators.Number(gte=1)),
    ] = None,
    select_rule: tuple[TriageRule, ...] = (),
    ignore_rule: tuple[TriageRule, ...] = (),
) -> ReviewTriageExitCode:
    """
    Print which files of a pull request need review, as Markdown.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    :param since: The commit to triage from, such as the head commit you last
        reviewed; a file only merges of the base branch changed since is mechanical.
    :param last: How many of the pull request's last commits to triage, a merge
        counting as one, as GitHub's view of its last commits shows them.
    :param select_rule: An opt-in rule to turn on, adding to the checkout's
        ``[tool.basstler.review-triage]`` settings in ``pyproject.toml``; repeatable.
    :param ignore_rule: A rule to turn off, outranking those settings; repeatable.
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    """
    TriagePublication.from_arguments(
        pull_request,
        repository,
        TriageDeclaration.from_arguments(rename, rejected_rename),
        since,
        last,
        select_rule,
        ignore_rule,
    ).publish((MarkdownReport(),))
    return ReviewTriageExitCode.SUCCESS


@review_triage_app.command(name=ReviewTriageCommand.MARK_VIEWED)
def mark_viewed(
    pull_request: int,
    *,
    repository: str | None = None,
    rename: tuple[str, ...] = (),
    rejected_rename: tuple[str, ...] = (),
    since: Annotated[str | None, Parameter(group=COMPARISON_START_GROUP)] = None,
    last: Annotated[
        int | None,
        Parameter(group=COMPARISON_START_GROUP, validator=validators.Number(gte=1)),
    ] = None,
    select_rule: tuple[TriageRule, ...] = (),
    ignore_rule: tuple[TriageRule, ...] = (),
) -> ReviewTriageExitCode:
    """
    Mark a pull request's mechanical files viewed for the account whose GitHub
    credential is configured, and print the triage.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    :param since: The commit to triage from, such as the head commit you last
        reviewed; a file only merges of the base branch changed since is mechanical.
    :param last: How many of the pull request's last commits to triage, a merge
        counting as one, as GitHub's view of its last commits shows them.
    :param select_rule: An opt-in rule to turn on, adding to the checkout's
        ``[tool.basstler.review-triage]`` settings in ``pyproject.toml``; repeatable.
    :param ignore_rule: A rule to turn off, outranking those settings; repeatable.
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    """
    TriagePublication.from_arguments(
        pull_request,
        repository,
        TriageDeclaration.from_arguments(rename, rejected_rename),
        since,
        last,
        select_rule,
        ignore_rule,
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
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    """
    logger.info(TriageDeclaration.from_arguments(rename, rejected_rename).comment())
    return ReviewTriageExitCode.SUCCESS
