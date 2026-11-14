"""
Choosing on the command line where a pull request is triaged from.
"""

from __future__ import annotations

import pytest
from cyclopts import CycloptsError

from basstler.github.pull_request_changes import (
    CommitStart,
    LastCommitsStart,
    MergeBaseStart,
)
from basstler.review_triage.command_line import (
    ReviewTriageCommand,
    TriagePublication,
    review_triage_app,
)
from basstler.review_triage.declaration import TriageDeclaration

# %% the start chosen


@pytest.mark.parametrize(
    ("since", "last", "start"),
    [
        ("abc123", None, CommitStart("abc123")),
        (None, 3, LastCommitsStart(3)),
        (None, None, MergeBaseStart()),
    ],
)
def test_the_options_choose_where_the_triage_starts(since, last, start):
    publication = TriagePublication.from_arguments(
        7, None, TriageDeclaration(), since, last
    )
    assert publication.start == start


# %% the options refused


@pytest.mark.parametrize(
    "options",
    [
        ("--since", "abc123", "--last", "2"),
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
