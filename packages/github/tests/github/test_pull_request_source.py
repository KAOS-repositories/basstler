"""
Tests for :mod:`basstler.github.pull_request_source`: reading the live state of a plan's
pull requests from GitHub.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

import pytest

from basstler.github.comparison import ComparisonStatus
from basstler.github.constants import MergeableState
from basstler.github.exceptions import GitHubRequestFailed
from basstler.github.pull_request_record import (
    PullRequestField,
    PullRequestHeadKey,
)
from basstler.github.pull_request_source import GitHubPullRequestSource
from basstler.github.pull_request_state import (
    ForkLineage,
    PullRequestRecord,
    PullRequestState,
)
from basstler.github.repository import Repository
from basstler.github.repository_access import (
    CommitReport,
    GitHubRepository,
    GitHubRepositoryPath,
)
from basstler.github.states import CombinedCheckState

from basstler_testing.constants.paths import DatasetLocation, RecordedCommitChecks
from basstler_testing.constants.site import SiteSampleText
from basstler_testing.github.pull_request_api import (
    api_pull_request,
    details_of,
    listing_path,
    pull_request_path,
)
from basstler_testing.github.recorded_client import RecordedGitHubClient
from basstler_testing.github.pull_request_samples import (
    ELSEWHERE_PULL_REQUEST,
    OPEN_PULL_REQUEST,
    TRACKING_ISSUE,
    UPSTREAM_REPOSITORY,
)

# %% reading pull requests


def test_github_source_answers_a_listed_pull_request_from_the_listing():
    listed = api_pull_request(OPEN_PULL_REQUEST, {PullRequestField.DRAFT: True})
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses=details_of(OPEN_PULL_REQUEST.repository),
            pages={listing_path(OPEN_PULL_REQUEST.repository): [[listed]]},
        )
    )
    record = source.pull_request(OPEN_PULL_REQUEST)
    assert record == PullRequestRecord.from_api(listed)


def test_github_source_reads_an_unlisted_pull_request_on_its_own():
    unlisted = api_pull_request(OPEN_PULL_REQUEST, {PullRequestField.DRAFT: True})
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses={
                **details_of(OPEN_PULL_REQUEST.repository),
                pull_request_path(OPEN_PULL_REQUEST): unlisted,
            },
            pages={listing_path(OPEN_PULL_REQUEST.repository): [[]]},
        )
    )
    record = source.pull_request(OPEN_PULL_REQUEST)
    assert record == PullRequestRecord.from_api(unlisted)


def test_github_source_answers_none_for_a_pull_request_that_does_not_exist():
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses=details_of(ELSEWHERE_PULL_REQUEST.repository),
            pages={listing_path(ELSEWHERE_PULL_REQUEST.repository): [[]]},
        )
    )
    assert source.pull_request(ELSEWHERE_PULL_REQUEST) is None


def commit_report_path(report: CommitReport) -> str:
    """
    :param report: Which listing reported against :attr:`SiteSampleText.HEAD_COMMIT`
        to read.
    :return: The path it is listed from.
    """
    return (
        f"/{OPEN_PULL_REQUEST.repository.api_path}{GitHubRepositoryPath.COMMITS}/"
        f"{SiteSampleText.HEAD_COMMIT}/{report}?per_page={GitHubRepository.page_size}"
    )


def api_pull_request_at_head(state: PullRequestState) -> dict[str, Any]:
    """
    :param state: Whether the pull request is open or closed.
    :return: The open pull request of the first plan, in that state, with its head at
        :attr:`SiteSampleText.HEAD_COMMIT`.
    """
    return api_pull_request(
        OPEN_PULL_REQUEST,
        {
            PullRequestField.STATE: state.value,
            PullRequestField.HEAD: {
                PullRequestHeadKey.COMMIT: SiteSampleText.HEAD_COMMIT.value
            },
        },
    )


def test_github_source_reads_the_checks_of_an_open_pull_request():
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses=details_of(OPEN_PULL_REQUEST.repository),
            pages={
                listing_path(OPEN_PULL_REQUEST.repository): [
                    [api_pull_request_at_head(PullRequestState.OPEN)]
                ],
                commit_report_path(CommitReport.CHECK_RUNS): [
                    json.loads(
                        RecordedCommitChecks.ONE_CHECK_RUN_FAILING.value.read_text(
                            encoding="utf-8"
                        )
                    )
                ],
                commit_report_path(CommitReport.STATUS): [
                    json.loads(
                        RecordedCommitChecks.NO_STATUSES.value.read_text(
                            encoding="utf-8"
                        )
                    )
                ],
            },
        )
    )
    assert (
        source.pull_request(OPEN_PULL_REQUEST).check_state is CombinedCheckState.FAILURE
    )


def test_github_source_leaves_the_checks_of_a_closed_pull_request_unread():
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses=details_of(OPEN_PULL_REQUEST.repository),
            pages={
                listing_path(OPEN_PULL_REQUEST.repository): [
                    [api_pull_request_at_head(PullRequestState.CLOSED)]
                ]
            },
        )
    )
    assert source.pull_request(OPEN_PULL_REQUEST).check_state is None


def test_github_source_reading_no_check_states_leaves_an_open_pull_requests_unread():
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses=details_of(OPEN_PULL_REQUEST.repository),
            pages={
                listing_path(OPEN_PULL_REQUEST.repository): [
                    [api_pull_request_at_head(PullRequestState.OPEN)]
                ]
            },
        ),
        reads_check_states=False,
    )
    assert source.pull_request(OPEN_PULL_REQUEST).check_state is None


# %% reading mergeable states


def a_source_reading_mergeable_states(
    listed: dict[str, Any],
    own_read: dict[str, Any],
    reads_mergeable_states: bool = True,
) -> GitHubPullRequestSource:
    """
    :param listed: The pull request as the repository's listing gives it.
    :param own_read: The pull request as reading it on its own gives it.
    :param reads_mergeable_states: Whether the source reads mergeable states.
    :return: A source that reads no check states.
    """
    return GitHubPullRequestSource(
        RecordedGitHubClient(
            responses={
                **details_of(OPEN_PULL_REQUEST.repository),
                pull_request_path(OPEN_PULL_REQUEST): own_read,
            },
            pages={listing_path(OPEN_PULL_REQUEST.repository): [[listed]]},
        ),
        reads_check_states=False,
        reads_mergeable_states=reads_mergeable_states,
    )


@pytest.mark.parametrize("mergeable_state", list(MergeableState))
def test_github_source_reads_the_mergeable_state_of_an_open_pull_request_on_its_own(
    mergeable_state: MergeableState,
):
    source = a_source_reading_mergeable_states(
        listed=api_pull_request(OPEN_PULL_REQUEST),
        own_read=api_pull_request(
            OPEN_PULL_REQUEST, {PullRequestField.MERGEABLE_STATE: mergeable_state.value}
        ),
    )
    assert source.pull_request(OPEN_PULL_REQUEST).mergeable_state is mergeable_state


def test_github_source_reading_no_mergeable_states_leaves_them_unread():
    source = a_source_reading_mergeable_states(
        listed=api_pull_request(OPEN_PULL_REQUEST),
        own_read=api_pull_request(
            OPEN_PULL_REQUEST, {PullRequestField.MERGEABLE_STATE: MergeableState.DIRTY}
        ),
        reads_mergeable_states=False,
    )
    assert source.pull_request(OPEN_PULL_REQUEST).mergeable_state is None


@pytest.mark.parametrize(
    "overrides",
    [
        {PullRequestField.STATE: PullRequestState.CLOSED.value},
        {PullRequestField.DRAFT: True},
    ],
)
def test_github_source_leaves_the_mergeable_state_of_a_closed_or_draft_pull_request_unread(
    overrides: dict[PullRequestField, Any],
):
    source = a_source_reading_mergeable_states(
        listed=api_pull_request(OPEN_PULL_REQUEST, overrides),
        own_read=api_pull_request(
            OPEN_PULL_REQUEST, {PullRequestField.MERGEABLE_STATE: MergeableState.DIRTY}
        ),
    )
    assert source.pull_request(OPEN_PULL_REQUEST).mergeable_state is None


# %% reading issue urls


def test_github_source_reads_an_issue_url():
    """
    An issue's web address is read from the issue itself.
    """
    issue_url = UPSTREAM_REPOSITORY.issue_url(TRACKING_ISSUE)
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses={
                **details_of(UPSTREAM_REPOSITORY),
                f"/{UPSTREAM_REPOSITORY.api_path}/issues/{TRACKING_ISSUE}": {
                    PullRequestField.HTML_URL.key: issue_url
                },
            }
        )
    )
    assert source.issue_url(UPSTREAM_REPOSITORY, TRACKING_ISSUE) == issue_url


def test_github_source_reraises_a_refusal_other_than_not_found():
    """
    A refused issue read is raised with the status GitHub refused it with.
    """
    with pytest.raises(GitHubRequestFailed) as refused:
        GitHubPullRequestSource(
            RecordedGitHubClient(
                responses=details_of(UPSTREAM_REPOSITORY), refusal=HTTPStatus.FORBIDDEN
            )
        ).issue_url(UPSTREAM_REPOSITORY, TRACKING_ISSUE)
    assert refused.value.status == HTTPStatus.FORBIDDEN


# %% a repository the source cannot read


def test_github_source_answers_none_for_a_pull_request_on_a_repository_it_cannot_read():
    source = GitHubPullRequestSource(RecordedGitHubClient())
    assert source.pull_request(ELSEWHERE_PULL_REQUEST) is None


@pytest.mark.parametrize(
    "status", [HTTPStatus.UNAUTHORIZED, HTTPStatus.INTERNAL_SERVER_ERROR]
)
def test_github_source_raises_a_failure_that_is_not_a_refused_repository(
    status: HTTPStatus,
):
    """
    A failure other than a refused repository is raised, not kept as unreadable.
    """
    source = GitHubPullRequestSource(RecordedGitHubClient(refusal=status))
    with pytest.raises(GitHubRequestFailed) as failed:
        source.read_failure_of(UPSTREAM_REPOSITORY)
    assert failed.value.status == status


def test_github_source_keeps_why_a_repository_cannot_be_read():
    """
    An unreadable repository keeps the status its read was refused with.
    """
    client = RecordedGitHubClient(refusal=HTTPStatus.FORBIDDEN)
    failure = GitHubPullRequestSource(client).read_failure_of(UPSTREAM_REPOSITORY)
    assert failure.status == client.refusal


def test_github_source_reports_a_repository_it_cannot_read(
    capsys: pytest.CaptureFixture,
):
    """
    An unreadable repository is reported on standard error.
    """
    source = GitHubPullRequestSource(RecordedGitHubClient())
    failure = source.read_failure_of(UPSTREAM_REPOSITORY)
    assert failure.error_message() in capsys.readouterr().err


def test_github_source_answers_no_issue_url_on_a_repository_it_cannot_read():
    """
    No issue address is answered on a repository the source cannot read.
    """
    source = GitHubPullRequestSource(RecordedGitHubClient(refusal=HTTPStatus.FORBIDDEN))
    assert source.issue_url(UPSTREAM_REPOSITORY, TRACKING_ISSUE) is None


# %% whether an open pull request's commits are already in the upstream


def landing_source(
    answers: dict[str, Any], state: PullRequestState = PullRequestState.OPEN
) -> GitHubPullRequestSource:
    """
    :param answers: What GitHub answers each comparison read with, by its path.
    :param state: Whether the pull request is open or closed.
    :return: A source over the first plan's repository as a fork, whose one pull request
        is at :attr:`SiteSampleText.HEAD_COMMIT` and based on ``main``.
    """
    fork = json.loads(DatasetLocation.REPOSITORY_FORK.read_text(encoding="utf-8"))
    return GitHubPullRequestSource(
        RecordedGitHubClient(
            responses={f"/{UPSTREAM_REPOSITORY.api_path}": fork, **answers},
            pages={
                listing_path(OPEN_PULL_REQUEST.repository): [
                    [api_pull_request_at_head(state)]
                ],
            },
        ),
        reads_check_states=False,
    )


def comparison_path(base: str) -> str:
    """
    :param base: What the head is compared with: a branch, or ``owner:branch``.
    :return: The path the comparison of that with the pull request's head is read from.
    """
    return (
        f"/{OPEN_PULL_REQUEST.repository.compare_path(base)}"
        f"...{SiteSampleText.HEAD_COMMIT}"
    )


def upstream_base() -> str:
    """
    :return: The fork's upstream default branch, as a comparison names it.
    """
    parent = json.loads(DatasetLocation.REPOSITORY_FORK.read_text(encoding="utf-8"))[
        "parent"
    ]
    owner = Repository.parse(parent["full_name"]).owner
    return f"{owner}:{parent['default_branch']}"


def a_comparison(status: ComparisonStatus, ahead_by: int, behind_by: int = 0) -> dict:
    """
    :param status: How the head relates to what it is compared with.
    :param ahead_by: How many commits the head has that the base lacks.
    :param behind_by: How many commits the base has that the head lacks.
    :return: The comparison as GitHub answers it.
    """
    return {"status": status.value, "ahead_by": ahead_by, "behind_by": behind_by}


def test_a_pull_request_whose_commits_are_in_the_upstream_is_read_as_landed():
    source = landing_source(
        {
            comparison_path(upstream_base()): a_comparison(
                ComparisonStatus.BEHIND, ahead_by=0, behind_by=5
            ),
            comparison_path("main"): a_comparison(ComparisonStatus.AHEAD, ahead_by=2),
        }
    )

    assert source.pull_request(OPEN_PULL_REQUEST).landed_upstream is True


def test_a_pull_request_with_commits_the_upstream_lacks_is_read_as_not_landed():
    source = landing_source(
        {
            comparison_path(upstream_base()): a_comparison(
                ComparisonStatus.DIVERGED, ahead_by=1, behind_by=5
            )
        }
    )

    assert source.pull_request(OPEN_PULL_REQUEST).landed_upstream is False


def test_a_pull_request_with_no_commits_beyond_its_own_base_is_read_as_not_landed():
    source = landing_source(
        {
            comparison_path(upstream_base()): a_comparison(
                ComparisonStatus.IDENTICAL, ahead_by=0
            ),
            comparison_path("main"): a_comparison(
                ComparisonStatus.IDENTICAL, ahead_by=0
            ),
        }
    )

    assert source.pull_request(OPEN_PULL_REQUEST).landed_upstream is False


def test_a_comparison_that_cannot_be_read_leaves_the_pull_request_unread_and_says_so(
    capsys: pytest.CaptureFixture[str],
):
    source = landing_source({})

    record = source.pull_request(OPEN_PULL_REQUEST)

    assert record.landed_upstream is None
    assert comparison_path(upstream_base()) in capsys.readouterr().err


def test_a_closed_pull_request_is_not_compared():
    source = landing_source({}, PullRequestState.CLOSED)

    assert source.pull_request(OPEN_PULL_REQUEST).landed_upstream is None


def test_a_pull_request_of_a_repository_that_is_not_a_fork_is_not_compared():
    """
    A pull request on a repository that is no fork has no upstream to be compared with.
    """
    source = GitHubPullRequestSource(
        RecordedGitHubClient(
            responses=details_of(OPEN_PULL_REQUEST.repository),
            pages={
                listing_path(OPEN_PULL_REQUEST.repository): [
                    [api_pull_request_at_head(PullRequestState.OPEN)]
                ],
            },
        ),
        reads_check_states=False,
    )

    assert source.pull_request(OPEN_PULL_REQUEST).landed_upstream is None


# %% reading a fork's upstream


def test_github_source_reads_the_upstream_of_a_fork():
    """
    A fork's upstream and both default branches are read from its details.
    """
    fork = json.loads(DatasetLocation.REPOSITORY_FORK.read_text(encoding="utf-8"))
    source = GitHubPullRequestSource(
        RecordedGitHubClient(responses={f"/{UPSTREAM_REPOSITORY.api_path}": fork})
    )
    assert source.fork_lineage_of(UPSTREAM_REPOSITORY) == ForkLineage(
        upstream_repository=Repository.parse(fork["parent"]["full_name"]),
        upstream_default_branch=fork["parent"]["default_branch"],
        fork_default_branch=fork["default_branch"],
    )


def test_github_source_finds_no_upstream_for_a_repository_that_is_not_a_fork():
    """
    A repository that is no fork has no upstream.
    """
    source = GitHubPullRequestSource(
        RecordedGitHubClient(responses=details_of(UPSTREAM_REPOSITORY))
    )
    assert source.fork_lineage_of(UPSTREAM_REPOSITORY) is None
