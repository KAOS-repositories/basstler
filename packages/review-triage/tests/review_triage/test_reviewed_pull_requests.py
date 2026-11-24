"""
Tests for :mod:`basstler.review_triage.reviewed_pull_requests`: finding the open pull
requests a reviewer takes part in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubReader
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.repository import ReviewerInvolvement
from basstler.review_triage.outputs import ViewedMarking
from basstler.review_triage.reviewed_pull_requests import ReviewedPullRequests
from basstler.review_triage.triage import TriageOutcome
from basstler.review_triage.viewed_states import ViewedCheckpoints

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.scratch_repository import ScratchRepository
from .conftest import SAMPLE_REPOSITORY, RefusingWriter, listing_of

# %% a search answering each involvement with its own page

SEARCH_PAGES = {
    ReviewerInvolvement.REVIEW_REQUESTED: DatasetLocation.REVIEW_REQUESTED_PULL_REQUESTS,
    ReviewerInvolvement.REVIEWED: DatasetLocation.REVIEWED_PULL_REQUESTS,
}
"""
The search page each involvement is answered with.
"""


@dataclass(frozen=True)
class SearchByInvolvement(GitHubReader):
    """
    Answers the search for each involvement on the sample repository with its page.
    """

    def get(self, path: str) -> Any:
        raise AssertionError(f"read only as a listing: {path}")

    def get_pages(self, path: str) -> list[Any]:
        (location,) = [
            location
            for involvement, location in SEARCH_PAGES.items()
            if path == SAMPLE_REPOSITORY.reviewer_pull_request_search_path(involvement)
        ]
        return [json.loads(location.read_text())]


# %% the pull requests found


def test_every_pull_request_requested_or_reviewed_is_found_once_lowest_first():
    """
    A pull request both requesting and reviewed by the account is found once.
    """
    expected = sorted(
        {
            item["number"]
            for location in SEARCH_PAGES.values()
            for item in json.loads(location.read_text())["items"]
        }
    )

    found = ReviewedPullRequests(SAMPLE_REPOSITORY).numbers(SearchByInvolvement())

    assert found == tuple(expected)


# %% marking them


def test_every_reviewed_pull_request_s_mechanical_files_are_marked(
    sample_triage: TriageOutcome, scratch_repository: ScratchRepository
):
    """
    Each pull request's mechanical files are marked, once per pull request.
    """
    writer = listing_of(sample_triage)

    ReviewedPullRequests(SAMPLE_REPOSITORY).mark_viewed(
        ViewedMarking(writer),
        GitCommandRunner(scratch_repository.project_root),
        (sample_triage, sample_triage),
    )

    expected = [file.change.path for file in sample_triage.mechanical_files] * 2
    assert writer.marked_paths == expected


def test_each_marked_pull_request_is_recorded_in_its_own_checkpoints(
    sample_triage: TriageOutcome, scratch_repository: ScratchRepository
):
    """
    The files marked are recorded as viewed at the head of the pull request marked.
    """
    git = GitCommandRunner(scratch_repository.project_root)

    ReviewedPullRequests(SAMPLE_REPOSITORY).mark_viewed(
        ViewedMarking(listing_of(sample_triage)), git, (sample_triage,)
    )

    checkpoints = ViewedCheckpoints.for_pull_request(
        git, SAMPLE_REPOSITORY, sample_triage.pull_request.number
    )
    head = sample_triage.pull_request.head.commit
    assert checkpoints.read() == {
        file.change.path: head for file in sample_triage.mechanical_files
    }


def test_a_refused_pull_request_is_raised_once_every_one_was_tried(
    sample_triage: TriageOutcome, scratch_repository: ScratchRepository
):
    """
    A refusal stops neither the other pull requests nor goes unreported.
    """
    tried: list[TriageOutcome] = []

    def outcomes():
        for outcome in (sample_triage, sample_triage):
            tried.append(outcome)
            yield outcome

    with pytest.raises(GraphQLErrorsReturned):
        ReviewedPullRequests(SAMPLE_REPOSITORY).mark_viewed(
            ViewedMarking(RefusingWriter(HTTPStatus.FORBIDDEN)),
            GitCommandRunner(scratch_repository.project_root),
            outcomes(),
        )
    assert tried == [sample_triage, sample_triage]
