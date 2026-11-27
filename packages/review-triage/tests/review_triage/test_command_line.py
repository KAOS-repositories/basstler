"""
Choosing on the command line where a pull request is triaged from.
"""

from __future__ import annotations

import pytest
from cyclopts import CycloptsError

from basstler.git.commands import GitCommandRunner
from basstler.github.pull_request_changes import (
    CommitStart,
    LastCommitsStart,
    LastReviewStart,
    MergeBaseStart,
)
from basstler.review_triage.command_line import (
    ReviewTriageCommand,
    TriagePublication,
    review_triage_app,
)
from basstler.review_triage.declaration import TriageDeclaration
from basstler.review_triage.recorded_plans import PlanRecord, RecordedPlan

# %% the start chosen


@pytest.mark.parametrize(
    ("since", "last", "from_merge_base", "start"),
    [
        ("abc123", None, False, CommitStart("abc123")),
        (None, 3, False, LastCommitsStart(3)),
        (None, None, True, MergeBaseStart()),
        (None, None, False, LastReviewStart()),
    ],
)
def test_the_options_choose_where_the_triage_starts(
    since, last, from_merge_base, start
):
    publication = TriagePublication.from_arguments(
        7, None, TriageDeclaration(), since, last, from_merge_base=from_merge_base
    )
    assert publication.start == start


# %% the options refused


@pytest.mark.parametrize(
    "options",
    [
        ("--since", "abc123", "--last", "2"),
        ("--since", "abc123", "--from-merge-base"),
        ("--last", "0"),
    ],
)
@pytest.mark.parametrize(
    "command", [ReviewTriageCommand.REPORT, ReviewTriageCommand.MARK_VIEWED]
)
def test_conflicting_or_empty_starts_are_refused(command, options):
    with pytest.raises(CycloptsError):
        review_triage_app.parse_args(
            [command, "7", *options], exit_on_error=False, print_error=False
        )


# %% the plans named


def test_a_plan_argument_is_a_record_of_the_commit_that_applied_it():
    argument = f"abc123{PlanRecord.separator}{RecordedPlan.WORKSPACE_PACKAGES}"

    publication = TriagePublication.from_arguments(
        7, None, TriageDeclaration(), None, None, plans=(argument,)
    )

    assert publication.plan_records == (
        PlanRecord("abc123", RecordedPlan.WORKSPACE_PACKAGES),
    )


@pytest.mark.parametrize(
    "command", [ReviewTriageCommand.REPORT, ReviewTriageCommand.MARK_VIEWED]
)
def test_the_plan_option_is_repeatable(command):
    arguments = ("abc123=workspace-packages", "def456=workspace-packages")

    _, bound, _ = review_triage_app.parse_args(
        [command, "7", "--plan", arguments[0], "--plan", arguments[1]],
        exit_on_error=False,
        print_error=False,
    )

    assert bound.kwargs["plan"] == arguments


# %% samples


@pytest.mark.parametrize(
    ("options", "samples"),
    [((), True), (("--no-samples",), False)],
    ids=["by default", "--no-samples"],
)
@pytest.mark.parametrize(
    "command", [ReviewTriageCommand.REPORT, ReviewTriageCommand.MARK_VIEWED]
)
def test_samples_are_left_unless_turned_off(command, options, samples):
    _, bound, _ = review_triage_app.parse_args(
        [command, "7", *options], exit_on_error=False, print_error=False
    )
    assert bound.arguments.get("samples", True) is samples


def test_a_publication_without_samples_leaves_none(tmp_path):
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    publication = TriagePublication.from_arguments(
        7, None, TriageDeclaration(), None, None, samples=False
    )
    assert publication.triager(git).sampling is None


@pytest.mark.parametrize(
    "options",
    [
        ("--since", "abc123", "--last", "2"),
        ("--since", "abc123", "--from-merge-base"),
    ],
)
def test_the_split_refuses_conflicting_starts(options):
    with pytest.raises(CycloptsError):
        review_triage_app.parse_args(
            [ReviewTriageCommand.SPLIT_MECHANICAL, "7", *options],
            exit_on_error=False,
            print_error=False,
        )
