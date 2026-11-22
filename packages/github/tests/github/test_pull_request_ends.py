"""
The two branches a pull request joins, and the listing of the pull requests between
them.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from basstler.github.pull_request_ends import PullRequestEnds
from basstler.github.repository import Repository, RepositoryBranch
from basstler.github.repository_access import ListingParameter, PullRequestListState

# %% the ends

REPOSITORY = Repository("an-owner", "a-project")
"""
The repository the pull requests are opened on.
"""

ENDS = PullRequestEnds(
    RepositoryBranch("main", REPOSITORY),
    RepositoryBranch("topic", Repository("a-forker", REPOSITORY.name)),
)
"""
A branch of a fork, proposed to the repository's ``main``.
"""


def test_the_ends_compare_their_head_with_their_base():
    assert ENDS.compare_url == REPOSITORY.compare_url(ENDS.base, ENDS.head)


# %% listing the pull requests between them


def test_the_listing_between_the_ends_filters_on_both():
    address = urlsplit(PullRequestListState.OPEN.path_between(ENDS))
    query = parse_qs(address.query)
    assert (
        address.path,
        query[ListingParameter.HEAD],
        query[ListingParameter.BASE],
    ) == (
        REPOSITORY.pull_requests_path,
        [ENDS.head.qualified_name],
        [ENDS.base.name],
    )


def test_a_listing_on_a_repository_filters_only_on_the_state():
    query = parse_qs(urlsplit(PullRequestListState.OPEN.path_on(REPOSITORY)).query)
    assert (ListingParameter.HEAD in query, query[ListingParameter.STATE]) == (
        False,
        [PullRequestListState.OPEN.query],
    )
