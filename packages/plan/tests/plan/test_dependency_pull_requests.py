"""
Tests for reading the live pull requests a plan's dependencies name, through
:class:`basstler.github.pull_request_source.GitHubPullRequestSource`.
"""

from __future__ import annotations

import json
from typing import Any

from basstler.github.pull_request_record import PullRequestField, PullRequestHeadKey
from basstler.github.pull_request_source import GitHubPullRequestSource
from basstler.github.repository import PullRequestReference, Repository
from basstler.github.repository_access import PullRequestListState
from basstler.plan.dependencies import DependencyResolver

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.constants.site import SiteSampleText
from basstler_testing.github.pull_request_api import (
    api_pull_request,
    details_of,
    listing_path,
)
from basstler_testing.github.recorded_client import RecordedGitHubClient
from basstler_testing.plan.first_plan import (
    ELSEWHERE_PULL_REQUEST,
    FIRST_PLAN,
    PLAN_REPOSITORY,
)
from basstler.text_file import TextFile

# %% the plan's pull requests, read live


def test_github_source_finds_a_repository_whose_details_are_refused_unreadable():
    """
    A repository whose details are refused is a read failure, not a pull request.
    """
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses=details_of(PLAN_REPOSITORY),
            pages={listing_path(PLAN_REPOSITORY): [[]]},
        )
    )
    live_pull_requests = source.live_pull_requests_of(
        DependencyResolver(FIRST_PLAN).pull_request_references
    )
    assert list(live_pull_requests.read_failures) == [ELSEWHERE_PULL_REQUEST.repository]


def test_github_source_records_the_upstream_of_each_fork_it_read_pull_requests_of():
    """
    Reading a plan's pull requests records the upstream of each fork they are on.
    """
    fork = json.loads(TextFile(DatasetLocation.REPOSITORY_FORK).read())
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses={f"/{PLAN_REPOSITORY.api_path}": fork},
            pages={
                listing_path(PLAN_REPOSITORY): [[]],
                listing_path(
                    Repository.parse(fork["parent"]["full_name"]),
                    PullRequestListState.OPEN,
                ): [[]],
            },
        )
    )
    live_pull_requests = source.live_pull_requests_of(
        DependencyResolver(FIRST_PLAN).pull_request_references
    )
    assert live_pull_requests.fork_lineages == {
        str(PLAN_REPOSITORY): source.fork_lineage_of(PLAN_REPOSITORY)
    }


# %% reading the upstream pull requests opened from a fork


def an_upstream_pull_request(
    upstream: Repository, number: int, head_repository: Repository, branch: str
) -> dict[str, Any]:
    """
    :param upstream: The repository the pull request is opened on.
    :param number: Its number.
    :param head_repository: The repository its head branch lives in.
    :param branch: Its head branch.
    :return: The open pull request, as the pulls API lists it.
    """
    return api_pull_request(
        PullRequestReference(upstream, number),
        {
            PullRequestField.HEAD: {
                PullRequestHeadKey.REFERENCE: branch,
                PullRequestHeadKey.HEAD_REPOSITORY: {
                    PullRequestHeadKey.FULL_NAME: head_repository.full_name
                },
                PullRequestHeadKey.COMMIT: SiteSampleText.HEAD_COMMIT.value,
            }
        },
    )


def test_github_source_records_the_upstream_pull_request_of_each_fork_branch():
    """
    Reading a plan's pull requests records the upstream pull request opened from each
    fork branch.
    """
    fork = json.loads(TextFile(DatasetLocation.REPOSITORY_FORK).read())
    upstream = Repository.parse(fork["parent"]["full_name"])
    elsewhere = Repository("another-owner", "another-fork")
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses={f"/{PLAN_REPOSITORY.api_path}": fork},
            pages={
                listing_path(PLAN_REPOSITORY): [[]],
                listing_path(upstream, PullRequestListState.OPEN): [
                    [
                        an_upstream_pull_request(
                            upstream, 7, PLAN_REPOSITORY, "a-branch"
                        ),
                        an_upstream_pull_request(
                            upstream, 8, elsewhere, "a-branch-of-another-fork"
                        ),
                    ]
                ],
            },
        )
    )
    live_pull_requests = source.live_pull_requests_of(
        DependencyResolver(FIRST_PLAN).pull_request_references
    )
    assert live_pull_requests.upstream_pull_requests == {
        str(PLAN_REPOSITORY): {"a-branch": 7}
    }


def test_github_source_reading_no_upstream_pull_requests_leaves_the_upstream_unread():
    """
    A source told not to read upstream pull requests reads nothing of the upstream.
    """
    fork = json.loads(TextFile(DatasetLocation.REPOSITORY_FORK).read())
    upstream = Repository.parse(fork["parent"]["full_name"])
    client = RecordedGitHubClient(
        responses={f"/{PLAN_REPOSITORY.api_path}": fork},
        pages={
            listing_path(PLAN_REPOSITORY): [[]],
            listing_path(upstream, PullRequestListState.OPEN): [[]],
        },
    )
    source = GitHubPullRequestSource(client, reads_upstream_pull_requests=False)
    source.live_pull_requests_of(DependencyResolver(FIRST_PLAN).pull_request_references)
    assert [
        path for path in client.reads if path.startswith(f"/{upstream.api_path}/")
    ] == []
