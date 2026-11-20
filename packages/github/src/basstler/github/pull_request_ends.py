"""
The two branches a pull request joins: the one it merges into and the one it proposes.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.github.repository import RepositoryBranch

# %% the ends


@dataclass(frozen=True)
class PullRequestEnds:
    """
    The branch a pull request merges into and the branch it proposes.
    """

    base: RepositoryBranch
    """
    The branch it merges into, on the repository the pull request is opened on.
    """

    head: RepositoryBranch
    """
    The branch it proposes, on that repository or on a fork of it.
    """

    @property
    def compare_url(self) -> str:
        """
        The page comparing :attr:`head` with :attr:`base`, from which the pull request
        is opened.
        """
        return self.base.repository.compare_url(self.base, self.head)


# %% what a pull request is opened with


@dataclass(frozen=True)
class PullRequestOpening(PullRequestEnds):
    """
    What a pull request is opened with: the branches it joins, its title and its
    description.
    """

    title: str
    """
    The pull request's title.
    """

    body: str = ""
    """
    The pull request's description, in Markdown.
    """
