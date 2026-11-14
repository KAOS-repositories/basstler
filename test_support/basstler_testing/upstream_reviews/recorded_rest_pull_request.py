"""
The recorded upstream pull request the REST reader tests read, and a reader over it.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.github.repository import Repository
from basstler.github.rest_models import RestPullRequestSummary
from basstler.upstream_reviews.readers import RestPullRequestReader, UpstreamRestRoute

from .replay import RecordedRestResponse, ReplayingRestClient

# %% the recorded pull request


class Example(StrEnum):
    """
    The identities the recorded responses were built around.
    """

    UPSTREAM_OWNER = "example-upstream"
    UPSTREAM_NAME = "example-repo"
    FORK_OWNER = "example-fork-owner"
    BRANCH = "some-branch"


UPSTREAM = Repository(Example.UPSTREAM_OWNER, Example.UPSTREAM_NAME)
ROUTE = UpstreamRestRoute(UPSTREAM)
NUMBER = 513
HEAD_SHA = RestPullRequestSummary.from_json(
    RecordedRestResponse.PULL_REQUEST.load()
).head.sha


def pull_request_responses(
    check_runs: RecordedRestResponse = RecordedRestResponse.CHECK_RUNS,
    status: RecordedRestResponse = RecordedRestResponse.STATUS,
) -> dict[str, object]:
    """
    Every response reading the recorded pull request takes, keyed by the path it
    answers.

    :param check_runs: The check runs the head commit carries.
    :param status: The commit statuses it carries.
    :return: The responses.
    """
    return {
        ROUTE.pull_request(NUMBER): RecordedRestResponse.PULL_REQUEST.load(),
        ROUTE.reviews(NUMBER): RecordedRestResponse.REVIEWS.load(),
        ROUTE.review_comments(NUMBER): RecordedRestResponse.REVIEW_COMMENTS.load(),
        ROUTE.review_threads(NUMBER): RecordedRestResponse.REVIEW_THREADS.load(),
        ROUTE.check_runs(HEAD_SHA): check_runs.load(),
        ROUTE.commit_status(HEAD_SHA): status.load(),
    }


def make_reader(responses: dict[str, object]) -> RestPullRequestReader:
    """
    :param responses: What each path answers with.
    :return: A REST reader over them, for the recorded upstream and fork.
    """
    return RestPullRequestReader(
        ReplayingRestClient(responses), UPSTREAM, Example.FORK_OWNER
    )
