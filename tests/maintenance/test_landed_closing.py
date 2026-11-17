"""
Tests for closing the open fork pull requests whose work has already landed upstream,
against a real scratch fork.
"""

from __future__ import annotations

import pytest

from basstler.maintenance.commands import RunReportCommand
from basstler.maintenance.finish_summary import FinishSummary, FinishSummaryHeading
from basstler.maintenance.promotion import PromotionSummaries
from basstler.maintenance.landed_closing import (
    ClosedAsLanded,
    LandedPullRequestClosing,
)

from ..constants.stack import RemoteName, StackBranch
from .fork import (
    UPSTREAM_BASE,
    ForkCheckout,
    StackPullRequestNumber,
    a_parent_and_child,
    a_stack,
    the_board,
)
from .test_finish_summary import section_of
from .recorded_fork import (
    AlreadyResolvedPass,
    PlanSiteBuildNote,
    RecordingPullRequests,
)

# %% which pull requests are closed


def land_upstream(checkout: ForkCheckout, branch: str) -> None:
    """
    Publish a fork branch's commit as the upstream base, as a merged pull request does.

    :param checkout: The scratch fork.
    :param branch: The fork branch to land.
    """
    checkout.run_git(
        "push", "--quiet", RemoteName.UPSTREAM, f"{branch}:{UPSTREAM_BASE}"
    )
    checkout.run_git("fetch", "--quiet", RemoteName.UPSTREAM)


@pytest.fixture(autouse=True)
def inside_the_fork(
    fork_checkout: ForkCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Run each test in the scratch fork, where the commit counts are asked.

    :param fork_checkout: The scratch fork.
    :param monkeypatch: Moves the working directory into the fork.
    """
    monkeypatch.chdir(fork_checkout.project_root)


@pytest.fixture
def parent_landed(fork_checkout: ForkCheckout) -> ForkCheckout:
    """
    The two-branch stack with the parent's commits in the upstream base.

    :param fork_checkout: The scratch fork.
    :return: The same fork.
    """
    a_parent_and_child(fork_checkout)
    land_upstream(fork_checkout, StackBranch.PARENT)
    return fork_checkout


def test_a_landed_pull_request_is_closed(parent_landed: ForkCheckout):
    fork = RecordingPullRequests()
    stack = a_stack(parent_landed, the_board())

    closed = LandedPullRequestClosing(stack, fork).apply()

    assert closed == (
        ClosedAsLanded(StackBranch.PARENT, StackPullRequestNumber.PARENT),
    )
    assert fork.closed == [StackPullRequestNumber.PARENT]


def test_a_landed_pull_request_is_not_labelled(parent_landed: ForkCheckout):
    fork = RecordingPullRequests()
    stack = a_stack(parent_landed, the_board())

    LandedPullRequestClosing(stack, fork).apply()

    assert fork.label_writes == []


def test_a_landed_pull_request_is_commented_on_with_its_branch_and_the_base(
    parent_landed: ForkCheckout,
):
    fork = RecordingPullRequests()
    stack = a_stack(parent_landed, the_board())

    LandedPullRequestClosing(stack, fork).apply()

    (comment,) = fork.comments
    assert comment.pull_request_number == StackPullRequestNumber.PARENT
    assert StackBranch.PARENT in comment.body
    assert f"{RemoteName.UPSTREAM}/{UPSTREAM_BASE}" in comment.body


def test_a_pull_request_that_has_not_landed_is_left_open(fork_checkout: ForkCheckout):
    a_parent_and_child(fork_checkout)
    fork = RecordingPullRequests()
    stack = a_stack(fork_checkout, the_board())

    closed = LandedPullRequestClosing(stack, fork).apply()

    assert closed == ()
    assert fork.closed == []
    assert fork.label_writes == []
    assert fork.comments == []


def test_a_branch_with_no_commits_of_its_own_is_left_open(
    fork_checkout: ForkCheckout,
):
    """
    Such a branch is an ancestor of the upstream base, as a landed one is, but nothing
    of it landed.
    """
    fork_checkout.run_git("branch", StackBranch.PARENT, UPSTREAM_BASE)
    fork_checkout.run_git("push", "--quiet", RemoteName.ORIGIN, StackBranch.PARENT)
    fork_checkout.run_git("fetch", "--quiet", RemoteName.ORIGIN)
    fork = RecordingPullRequests()
    stack = a_stack(fork_checkout, the_board()[:1])

    closed = LandedPullRequestClosing(stack, fork).apply()

    assert closed == ()
    assert fork.closed == []


def test_a_pull_request_whose_base_the_fork_no_longer_has_is_left_open_and_warned_about(
    parent_landed: ForkCheckout, capsys: pytest.CaptureFixture[str]
):
    parent_landed.run_git(
        "update-ref", "-d", f"refs/remotes/{RemoteName.ORIGIN}/{StackBranch.PARENT}"
    )
    land_upstream(parent_landed, StackBranch.CHILD)
    fork = RecordingPullRequests()
    stack = a_stack(parent_landed, the_board()[1:])

    closed = LandedPullRequestClosing(stack, fork).apply()

    assert closed == ()
    assert fork.closed == []
    assert StackBranch.CHILD in capsys.readouterr().err


# %% what the pass does with them


@pytest.fixture
def child_landed(fork_checkout: ForkCheckout) -> ForkCheckout:
    """
    The two-branch stack with the child's commits in the upstream base, as when the work
    landed through a pull request of its own and left the child stacked on its parent.

    :param fork_checkout: The scratch fork.
    :return: The same fork.
    """
    a_parent_and_child(fork_checkout)
    land_upstream(fork_checkout, StackBranch.CHILD)
    return fork_checkout


def test_a_whole_pass_closes_the_landed_pull_request_and_starts_the_plan_site_build(
    child_landed: ForkCheckout,
):
    maintenance = AlreadyResolvedPass.over(child_landed, the_board()[1:])

    report = RunReportCommand().perform(
        maintenance, as_json=True, summaries=PromotionSummaries()
    )

    assert report.closed_as_landed == (
        ClosedAsLanded(StackBranch.CHILD, StackPullRequestNumber.CHILD),
    )
    assert report.landed == ()
    assert report.plan_site_build == PlanSiteBuildNote.STARTED
    assert maintenance.plan_site_builds_started == [PlanSiteBuildNote.STARTED]


def test_a_whole_pass_that_closes_nothing_does_not_start_the_plan_site_build(
    fork_checkout: ForkCheckout,
):
    a_parent_and_child(fork_checkout)
    maintenance = AlreadyResolvedPass.over(fork_checkout, the_board())

    report = RunReportCommand().perform(
        maintenance, as_json=True, summaries=PromotionSummaries()
    )

    assert report.closed_as_landed == ()
    assert report.plan_site_build is None
    assert maintenance.plan_site_builds_started == []


def test_the_summary_lists_what_was_closed_and_what_became_of_the_build(
    child_landed: ForkCheckout,
):
    maintenance = AlreadyResolvedPass.over(child_landed, the_board()[1:])
    report = RunReportCommand().perform(
        maintenance, as_json=True, summaries=PromotionSummaries()
    )

    summary = FinishSummary(report, maintenance.resolved_stack).as_markdown()

    (entry,) = section_of(summary, FinishSummaryHeading.CLOSED_AS_LANDED)
    assert f"`{StackBranch.CHILD}`" in entry
    assert section_of(summary, FinishSummaryHeading.PLAN_SITE_BUILD) == [
        PlanSiteBuildNote.STARTED
    ]
