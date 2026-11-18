"""
Tests for :mod:`basstler.review_triage.reviewed_pull_requests`: finding the open pull
requests a reviewer takes part in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from basstler.github.client import GitHubReader
from basstler.github.repository import ReviewerInvolvement
from basstler.review_triage.reviewed_pull_requests import ReviewedPullRequests

from basstler_testing.constants.paths import DatasetLocation
from .conftest import SAMPLE_REPOSITORY

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
