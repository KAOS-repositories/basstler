"""
The boards and configurations the maintenance suites execute a pass against, on a
:class:`~basstler_testing.fork_checkout.ForkCheckout`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from enum import StrEnum

import basstler.maintenance.__main__
import basstler.maintenance.restack_procedure
from basstler.stack.commit_move import BranchAncestry
from basstler.github.pull_request_record import (
    CommitChecks,
    PullRequestRecord,
)
from basstler.github.states import CombinedCheckState
from basstler.maintenance.board import BoardExport
from basstler.upstream_reviews.action.open_pull_requests import UpstreamPullRequests
from basstler.stack.model import (
    PullRequest,
    Stack,
)
from basstler.stack.settings import Configuration

from ..constants.stack import RemoteName, StackBranch, StackLabel
from ..fork_checkout import UPSTREAM_BASE, ForkCheckout
from ..github.listed_repository import ChecksReportedOn
from ..github.pull_request_samples import (
    PullRequestHeadRepository,
    StackPullRequestNumber,
    UPSTREAM_REPOSITORY,
)

# %% shared maintenance inputs


MAINTENANCE_MODULE = basstler.maintenance.__main__.__name__
"""
The executor under test, invoked as a subprocess wherever an exit status is the
assertion.

Named off the module rather than spelled out, and run with ``-m`` rather than by path: a
module run by path puts its own directory on ``sys.path`` in place of the project root,
so its absolute imports of its siblings would not resolve.
"""


class FixtureFile(StrEnum):
    """
    The files a test writes into the checkout to put the branches in the state it is
    about, named once because several tests write the same one from both sides.
    """

    CONTESTED = "a-contested-file"
    """
    Written on a branch and on its parent, with different content, so integrating them
    conflicts.
    """

    ON_THE_BASE = "a-base-file"
    """
    Written on the base branch, so every branch below it has a moved parent to take.
    """

    PUSHED_BY_SOMEBODY_ELSE = "a-file-somebody-else-pushed"
    """
    Written by a commit the pass did not make, standing for a branch that moved under
    it.
    """


def make_configuration() -> Configuration:
    """
    :return: The configuration a scratch fork checkout resolves to.
    """
    return Configuration(
        in_review_label=StackLabel.IN_REVIEW,
        rebase_label=StackLabel.REBASE,
        needs_resolution_label=StackLabel.NEEDS_RESOLUTION,
        fork_repository=PullRequestHeadRepository.FORK.value,
        fork_remote=RemoteName.ORIGIN,
        upstream_repository=UPSTREAM_REPOSITORY,
        upstream_remote=RemoteName.UPSTREAM,
        upstream_base=UPSTREAM_BASE,
        upstream_location=RemoteName.UPSTREAM,
    )


def make_own_remote_configuration() -> Configuration:
    """
    :return: The configuration a scratch checkout naming no upstream resolves to, its own
        remote standing where the upstream would.
    """
    return dataclasses.replace(
        make_configuration(),
        upstream_repository=None,
        upstream_remote=RemoteName.ORIGIN,
        upstream_location=RemoteName.ORIGIN,
    )


def a_stack(
    checkout: ForkCheckout,
    pull_requests: list[PullRequest],
    configuration: Configuration | None = None,
):
    """
    Build the derived stack the executor consumes, with landedness read from real git.

    :param checkout: The checkout to answer ancestry questions from.
    :param pull_requests: The board entries.
    :param configuration: The configuration the stack runs on, by default
        :func:`make_configuration`'s.
    :return: The derived stack.
    """
    configuration = configuration or make_configuration()
    upstream = f"{configuration.upstream_remote}/{configuration.upstream_base}"
    ancestry = BranchAncestry(configuration, checkout.git)

    def is_merged(name: str) -> bool:
        return ancestry.is_ancestor(name, upstream)

    def is_contained_by(candidate: str, container: str) -> bool:
        return ancestry.is_ancestor(
            candidate, configuration.reference_on_fork(container)
        )

    return Stack.build(configuration, pull_requests, is_merged, is_contained_by)


# %% the board export


def an_export(
    records: Iterable[PullRequestRecord],
    upstream_records: Iterable[PullRequestRecord] = (),
    checks: CommitChecks | None = None,
) -> BoardExport:
    """
    :param records: The fork's open pull requests, as the REST API returns them.
    :param upstream_records: The upstream's open pull requests.
    :param checks: The verdict over each head commit's checks, ``None`` for no checks
        on any commit.
    :return: The board the export builds from them.
    """
    return BoardExport.from_api_records(
        records,
        UpstreamPullRequests.from_api_records(
            upstream_records, PullRequestHeadRepository.FORK.value
        ),
        checks or ChecksReportedOn(),
    )


# %% restack


def a_parent_and_child(fork_checkout: ForkCheckout) -> None:
    """
    Publish a two-branch stack: the parent on the base, the child on the parent.

    :param fork_checkout: The checkout to build the branches in.
    """
    fork_checkout.branch_from(StackBranch.PARENT, UPSTREAM_BASE)
    fork_checkout.branch_from(StackBranch.CHILD, StackBranch.PARENT)


def a_board_entry(
    number: int,
    head: str,
    base: str,
    labels: list[str] | None = None,
    title: str | None = None,
    session: str | None = None,
    description: str | None = None,
    upstream_pull_request: int | None = None,
    check_state: CombinedCheckState = CombinedCheckState.NOT_REPORTED,
) -> PullRequest:
    """
    :param number: The pull request number.
    :param head: The head branch, on the fork.
    :param base: The base branch.
    :param labels: The labels it carries.
    :param title: Its title.
    :param session: The session its description names.
    :param description: Its description, without the sections a pass writes.
    :param upstream_pull_request: The open upstream pull request opened from it.
    :param check_state: The verdict over its head's checks.
    :return: One ready board entry whose head is on the fork.
    """
    return PullRequest(
        number=number,
        head=head,
        base=base,
        draft=False,
        head_repository=PullRequestHeadRepository.FORK.value.full_name,
        labels=labels or [],
        session=session,
        title=title,
        description=description,
        upstream_pull_request=upstream_pull_request,
        check_state=check_state,
    )


def the_board(labels: list[str] | None = None) -> list[PullRequest]:
    """
    :param labels: The labels the child's pull request carries.
    :return: The two-branch board matching :func:`a_parent_and_child`.
    """
    return [
        PullRequest(
            number=StackPullRequestNumber.PARENT,
            head=StackBranch.PARENT,
            base=UPSTREAM_BASE,
            draft=False,
            head_repository=PullRequestHeadRepository.FORK.value.full_name,
        ),
        PullRequest(
            number=StackPullRequestNumber.CHILD,
            head=StackBranch.CHILD,
            base=StackBranch.PARENT,
            draft=False,
            labels=labels or [],
            head_repository=PullRequestHeadRepository.FORK.value.full_name,
        ),
    ]
