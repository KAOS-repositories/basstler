"""
The pull requests, repositories and description text the tests write into a pull
request and read back.
"""

from __future__ import annotations

from enum import Enum, IntEnum, StrEnum

from basstler.github.repository import PullRequestReference, Repository

# %% the pull requests and their repositories


class StackPullRequestNumber(IntEnum):
    """
    The numbers of the fork pull requests the two-branch stack under test is made of.

    A number is written into a board entry, keyed into a recorded write and read back in
    an assertion, so it is named once rather than spelled at each of those places.
    """

    PARENT = 40
    """
    The pull request of :attr:`StackBranch.PARENT`.
    """

    CHILD = 41
    """
    The pull request of :attr:`StackBranch.CHILD`, based on the parent's.
    """

    ON_ANOTHER_FORK = 42
    """
    The pull request of :attr:`StackBranch.ON_ANOTHER_FORK`, whose head is not on the
    fork.
    """

    OFF_THE_CHAIN = 43
    """
    The pull request of :attr:`StackBranch.OFF_THE_CHAIN`, cut from the base beside the
    two-branch stack.
    """

    UPSTREAM = 140
    """
    The upstream pull request opened from :attr:`StackBranch.PARENT`.
    """


class PullRequestHeadRepository(Enum):
    """
    The repositories a board entry's head branch can live in.
    """

    FORK = Repository("a-fork-owner", "a-fork")
    """
    The fork the pass maintains, which a scratch checkout's fork remote points at.
    """

    ANOTHER_CONTRIBUTORS_FORK = Repository("another-contributor", "a-fork")
    """
    Another contributor's fork, which the pass cannot push to.
    """


class PromotionSampleText(StrEnum):
    """
    The text a promotion test puts into a fork pull request and finds again in what the
    pass writes back.
    """

    TITLE = "A parent branch"
    """
    The parent pull request's title.
    """

    SUMMARY = "What this branch does."
    """
    The first paragraph of the parent pull request's description.
    """

    DETAIL = "More detail."
    """
    The paragraph after it.
    """

    PROSE = "Prose."
    """
    A description's text before its Promote section.
    """

    FIRST_LINK = "https://example.invalid/first"
    """
    The create-link a first promotion writes.
    """

    SECOND_LINK = "https://example.invalid/second"
    """
    The create-link a second promotion writes in its place.
    """

    COMMENT_LINK_PREFIX = "https://example.invalid/comment/"
    """
    What a recorded comment's stand-in URL starts with, before the comment's position.
    """


UPSTREAM_REPOSITORY = Repository("an-upstream-owner", "a-project")
"""
The upstream a scratch fork checkout's fork was made from.
"""


OPEN_PULL_REQUEST = PullRequestReference(
    UPSTREAM_REPOSITORY, StackPullRequestNumber.CHILD
)
"""
A pull request the tests read back as open.
"""

MERGED_PULL_REQUEST = PullRequestReference(
    UPSTREAM_REPOSITORY, StackPullRequestNumber.PARENT
)
"""
A pull request the tests read back as merged.
"""

ELSEWHERE_PULL_REQUEST = PullRequestReference(
    PullRequestHeadRepository.ANOTHER_CONTRIBUTORS_FORK.value,
    StackPullRequestNumber.ON_ANOTHER_FORK,
)
"""
A pull request on a repository other than :data:`UPSTREAM_REPOSITORY`.
"""

TRACKING_ISSUE = 7
"""
The number of an issue on :data:`UPSTREAM_REPOSITORY`.
"""


# %% what a description links


A_SESSION_LINK = "https://claude.ai/code/session_01ABCdef"
"""
The session a pull request's description names, written into one and read back out of
another wherever a test follows that link through the pass.
"""
