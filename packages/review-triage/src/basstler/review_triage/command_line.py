"""
The ``basstler review-triage`` commands: reporting which files of a pull request need
review, marking the others viewed, and writing a rename declaration.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Annotated

from cyclopts import App, Group, Parameter, validators

from basstler.exit_codes import ExitCode
from basstler.git.commands import GitCommandRunner
from basstler.github.basstler_project import BasstlerProject
from basstler.github.client import GitHubRestClient
from basstler.github.pull_request_changes import (
    CommitStart,
    ComparisonStart,
    LastCommitsStart,
    LastReviewStart,
    MergeBaseStart,
    PullRequestChangesReader,
)
from basstler.github.repository import PullRequestReference, Repository
from basstler.locations import ClaudeCodeVariable
from basstler.review_triage.command_names import ReviewTriageCommand
from basstler.review_triage.declaration import ArgumentDeclaration, TriageDeclaration
from basstler.review_triage.outputs import MarkdownReport, TriageOutput, ViewedMarking
from basstler.review_triage.rules import (
    ReviewTriageSettings,
    RuleSelection,
    TriageRule,
)
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

    start: ComparisonStart = LastReviewStart()
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
        from_merge_base: bool = False,
    ) -> TriagePublication:
        """
        :param pull_request: The pull request's number.
        :param repository: Its repository as ``owner/name``, or ``None``.
        :param declaration: Renames given and rejected on the command line.
        :param since: The commit to triage from, or ``None``.
        :param last: How many of the last commits to triage, or ``None``.
        :param select_rules: The rules to turn on.
        :param ignore_rules: The rules to turn off.
        :param from_merge_base: Whether to triage the whole change.
        :return: The publication triaging from *since*, else from before the *last*
            commits, else from the merge base if *from_merge_base*, else from the
            viewer's last review.
        """
        if since is not None:
            start: ComparisonStart = CommitStart(since)
        elif last is not None:
            start = LastCommitsStart(last)
        elif from_merge_base:
            start = MergeBaseStart()
        else:
            start = LastReviewStart()
        return cls(
            pull_request,
            repository,
            declaration,
            start,
            rule_options=RuleSelection(
                frozenset(select_rules), frozenset(ignore_rules)
            ),
        )

    def outcome(self) -> TriageOutcome:
        """
        :return: The triage of the pull request.
        """
        git = GitCommandRunner(Path.cwd())
        checkout = Path(git.run("rev-parse", "--show-toplevel"))
        changes = PullRequestChangesReader(git, GitHubRestClient()).read(
            Repository.from_name_or_remote(self.repository, git, self.remote),
            self.pull_request,
            self.start,
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
        return triager.triage(changes)

    def publish(self, outputs: tuple[TriageOutput, ...]) -> None:
        """
        :param outputs: Where the outcome goes, in order.
        """
        outcome = self.outcome()
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
    from_merge_base: Annotated[
        bool, Parameter(group=COMPARISON_START_GROUP, negative=())
    ] = False,
    select_rule: tuple[TriageRule, ...] = (),
    ignore_rule: tuple[TriageRule, ...] = (),
) -> ReviewTriageExitCode:
    """
    Print which files of a pull request need review, as Markdown; by default only the
    changes since your last review, the whole change if you have not reviewed it.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    :param since: The commit to triage from, such as the head commit you last
        reviewed; a file only merges of the base branch changed since is mechanical.
    :param last: How many of the pull request's last commits to triage, a merge
        counting as one, as GitHub's view of its last commits shows them.
    :param from_merge_base: Triage the whole change, not only what changed since your
        last review.
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
        from_merge_base,
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
    since: Annotated[str | None, Parameter(group=COMPARISON_START_GROUP)] = None,
    last: Annotated[
        int | None,
        Parameter(group=COMPARISON_START_GROUP, validator=validators.Number(gte=1)),
    ] = None,
    from_merge_base: Annotated[
        bool, Parameter(group=COMPARISON_START_GROUP, negative=())
    ] = False,
    select_rule: tuple[TriageRule, ...] = (),
    ignore_rule: tuple[TriageRule, ...] = (),
) -> ReviewTriageExitCode:
    """
    Mark a pull request's mechanical files viewed for the logged-in account, or, where
    that fails, ask a repository's Actions to; then print the triage. By default only
    the changes since that account's last review, the whole change without one.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param workflow_repository: The repository whose Actions are asked when marking
        directly fails, as ``owner/name``; the checkout's ``origin`` by default.
    :param directly: Only mark them directly, never through Actions, as the workflow
        that marks them does.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    :param since: The commit to triage from, such as the head commit you last
        reviewed; a file only merges of the base branch changed since is mechanical.
    :param last: How many of the pull request's last commits to triage, a merge
        counting as one, as GitHub's view of its last commits shows them.
    :param from_merge_base: Triage the whole change, not only what changed since your
        last review.
    :param select_rule: An opt-in rule to turn on, adding to the checkout's
        ``[tool.basstler.review-triage]`` settings in ``pyproject.toml``; repeatable.
    :param ignore_rule: A rule to turn off, outranking those settings; repeatable.
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    :raises GraphQLErrorsReturned: If marking them directly, alone, fails.
    :raises FilesNotMarkedViewed: If neither way marks them.
    """
    git = GitCommandRunner(Path.cwd())
    outcome = TriagePublication.from_arguments(
        pull_request,
        repository,
        TriageDeclaration.from_arguments(rename, rejected_rename),
        since,
        last,
        select_rule,
        ignore_rule,
        from_merge_base,
    ).outcome()
    MarkdownReport().publish(outcome)
    routes = ViewedMarkingRoutes(
        ViewedMarking(GitHubRestClient()),
        MarkViewedRequest(
            Repository.from_name_or_remote(workflow_repository, git),
            PullRequestReference(
                Repository.from_name_or_remote(repository, git), pull_request
            ),
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
    reference = PullRequestReference(
        Repository.from_name_or_remote(repository, git), pull_request
    )
    request = MarkViewedRequest(
        Repository.from_name_or_remote(workflow_repository, git), reference
    )
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
    branch_or_tag: str = BasstlerProject.default_branch.name,
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
        Repository.from_name_or_remote(workflow_repository, git),
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
