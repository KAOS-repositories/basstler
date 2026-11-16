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
from basstler.github.pull_request import PullRequestDescription
from basstler.git.commands import GitCommandRunner
from basstler.github.pull_request_changes import (
    CommitStart,
    ComparisonStart,
    LastCommitsStart,
    LastReviewStart,
    MergeBaseStart,
    PullRequestChanges,
    PullRequestChangesReader,
)
from basstler.github.repository import Repository
from basstler.locations import PackageLocation
from basstler.review_triage.declaration import ArgumentDeclaration, TriageDeclaration
from basstler.review_triage.exceptions import MissingHeadRepositoryError
from basstler.review_triage.mechanical_split import MechanicalSplitter
from basstler.review_triage.outputs import MarkdownReport, TriageOutput, ViewedMarking
from basstler.review_triage.review_samples import ReviewSampling
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

    SPLIT_MECHANICAL = "split-mechanical"
    """
    Replace a pull request's commits with one making its mechanical changes and one
    making every other change.
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

    leaves_samples: bool = True
    """
    Whether one mechanical file showing each rename is left for review.
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
        samples: bool = True,
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
        :param samples: Whether to leave one mechanical file showing each rename for
            review.
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
            leaves_samples=samples,
        )

    def publish(self, outputs: tuple[TriageOutput, ...]) -> None:
        """
        :param outputs: Where the outcome goes, in order.
        """
        git = GitCommandRunner(Path.cwd())
        outcome = self.triager(git).triage(self.changes(git))
        for output in outputs:
            output.publish(outcome)

    def changes(self, git: GitCommandRunner) -> PullRequestChanges:
        """
        :param git: The checkout the pull request is read in.
        :return: The pull request and its changes since :attr:`start`.
        """
        return PullRequestChangesReader(git, GitHubRestClient()).read(
            self.repository_in(git), self.pull_request, self.start
        )

    def repository_in(self, git: GitCommandRunner) -> Repository:
        """
        :param git: The checkout whose :attr:`remote` names the repository by default.
        :return: The repository the pull request is opened on.
        """
        if self.repository:
            return Repository.parse(self.repository)
        return Repository.from_remote_url(git.run("remote", "get-url", self.remote))

    def triager(self, git: GitCommandRunner) -> PullRequestTriager:
        """
        :param git: The checkout whose settings choose the rules.
        :return: The triager judging with the declared renames and the chosen rules.
        """
        checkout = Path(git.run("rev-parse", "--show-toplevel"))
        default = PullRequestTriager()
        return replace(
            default,
            rename_sources=(
                *default.rename_sources,
                ArgumentDeclaration(self.declaration),
            ),
            rules=self.rule_options.applied_to(
                ReviewTriageSettings.from_checkout(checkout).selection
            ),
            sampling=ReviewSampling() if self.leaves_samples else None,
        )


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
    samples: bool = True,
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
    :param samples: Leave one mechanical file showing each rename for review, the file
        defining the new name where it can; ``--no-samples`` leaves none.
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
        samples,
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
    from_merge_base: Annotated[
        bool, Parameter(group=COMPARISON_START_GROUP, negative=())
    ] = False,
    select_rule: tuple[TriageRule, ...] = (),
    ignore_rule: tuple[TriageRule, ...] = (),
    samples: bool = True,
) -> ReviewTriageExitCode:
    """
    Mark a pull request's mechanical files viewed for the account whose GitHub
    credential is configured, and print the triage; by default only the changes since
    that account's last review, the whole change if it has not reviewed it.

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
    :param samples: Leave one mechanical file showing each rename for review, the file
        defining the new name where it can; ``--no-samples`` leaves none.
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
        samples,
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


@review_triage_app.command(name=ReviewTriageCommand.SPLIT_MECHANICAL)
def split_mechanical(
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
) -> ReviewTriageExitCode:
    """
    Replace a pull request's commits since your last review with one making the changes
    the triage proves mechanical and one making every other change, whose tree is the
    former head's, and summarise the first in the description. Nothing is pushed unless
    the proof holds.

    :param pull_request: The pull request's number.
    :param repository: Its repository as ``owner/name``; the checkout's ``origin`` by
        default.
    :param rename: A rename as ``old=new``, outranking the description's; repeatable.
    :param rejected_rename: An old identifier whose rename is rejected; repeatable.
    :param since: The commit to split from, keeping the commits up to it.
    :param last: How many of the pull request's last commits to split.
    :param from_merge_base: Split the whole change, not only what changed since your
        last review.
    :return: :attr:`ReviewTriageExitCode.SUCCESS`; a failure raises instead.
    """
    publication = TriagePublication.from_arguments(
        pull_request,
        repository,
        TriageDeclaration.from_arguments(rename, rejected_rename),
        since,
        last,
        from_merge_base=from_merge_base,
        samples=False,
    )
    git = GitCommandRunner(Path.cwd())
    changes = publication.changes(git)
    split = MechanicalSplitter(git, publication.triager(git)).split(changes)
    if split is None:
        logger.info(
            f"#{pull_request} changes wholly mechanically, or nothing mechanically, "
            f"since {changes.start.reason}; its branch is unchanged."
        )
        return ReviewTriageExitCode.SUCCESS
    head_repository = changes.pull_request.head.repository
    if head_repository is None:
        raise MissingHeadRepositoryError(pull_request)
    split.publish(git, head_repository.repository.clone_url)
    base_repository = publication.repository_in(git)
    pull_request_url = base_repository.pull_request_url(pull_request)
    GitHubRestClient().send(
        PullRequestDescription(
            repository=base_repository,
            number=pull_request,
            body=split.description(pull_request_url),
        )
    )
    logger.info(
        f"#{pull_request} now makes its mechanical changes in {split.mechanical_commit}"
        f" and every other change in {split.remaining_commit}; review the second: "
        f"{pull_request_url}/commits/{split.remaining_commit}"
    )
    return ReviewTriageExitCode.SUCCESS
