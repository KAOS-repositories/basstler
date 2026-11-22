"""
Tests for the form a recorded GraphQL pull request page writes its pull request in.
"""

from __future__ import annotations

from basstler.github.pull_request_models import UpstreamPullRequestSnapshot
from basstler.github.repository import PullRequestReference

from basstler_testing.upstream_reviews.recorded_rest_pull_request import UPSTREAM
from basstler_testing.upstream_reviews.replay import RecordedResponse

# %% a pull request named by its number


def test_a_pull_request_read_by_number_belongs_to_the_repository_read():
    """
    A pull request the page names by its number is one of the repository it was read
    from.
    """
    pull_request = RecordedResponse.PULL_REQUEST_PAGE_ONE.recorded(
        UPSTREAM
    ).pull_request

    assert pull_request.reference.repository == UPSTREAM


def test_a_snapshot_keeps_the_pull_request_it_was_assembled_from():
    """
    A snapshot assembled from a pull request references that pull request.
    """
    pull_request = RecordedResponse.PULL_REQUEST_PAGE_ONE.recorded(
        UPSTREAM
    ).pull_request

    snapshot = UpstreamPullRequestSnapshot.assemble(pull_request, [])

    assert snapshot.reference == PullRequestReference(
        UPSTREAM, pull_request.reference.number
    )
