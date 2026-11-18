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

from basstler.github.client import GitHubReader
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.repository import ReviewerInvolvement
from basstler.review_triage.outputs import ViewedMarking
from basstler.review_triage.reviewed_pull_requests import ReviewedPullRequests
from basstler.review_triage.triage import TriageOutcome

from ..constants.paths import DatasetLocation
from .conftest import SAMPLE_REPOSITORY, RecordingWriter, RefusingWriter

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
    sample_triage: TriageOutcome,
):
    """
    Each pull request's mechanical files are marked, one mutation per file.
    """
    writer = RecordingWriter({"data": {}})

    ReviewedPullRequests(SAMPLE_REPOSITORY).mark_viewed(
        ViewedMarking(writer), (sample_triage, sample_triage)
    )

    assert len(writer.sent) == 2 * len(sample_triage.mechanical_files)


def test_a_refused_pull_request_is_raised_once_every_one_was_tried(
    sample_triage: TriageOutcome,
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
            ViewedMarking(RefusingWriter(HTTPStatus.FORBIDDEN)), outcomes()
        )
    assert tried == [sample_triage, sample_triage]
