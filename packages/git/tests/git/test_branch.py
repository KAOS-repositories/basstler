"""
Tests for a git branch, the base of every branch the package handles.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.git.branch import Branch
from basstler.git.remote_branch import RemoteBranch
from basstler.git.repository import GitRepository

# %% a repository the branch belongs to


@dataclass(frozen=True)
class FixedAddressRepository(GitRepository):
    """
    A repository fetched from one address given up front.
    """

    address: str
    """
    The URL the repository is fetched from.
    """

    @property
    def url(self) -> str:
        return self.address


REPOSITORY = FixedAddressRepository("https://example.com/project.git")
"""
The repository every branch in these tests belongs to.
"""


# %% the reference a branch is kept under


def test_reference_is_the_branch_under_the_heads_namespace() -> None:
    assert Branch(REPOSITORY, "feature/x").reference == "refs/heads/feature/x"


# %% the repository a branch belongs to


def test_a_branch_holds_the_repository_it_belongs_to() -> None:
    assert Branch(REPOSITORY, "main").repository == REPOSITORY


def test_branches_of_the_same_name_in_two_repositories_differ() -> None:
    other = FixedAddressRepository("https://example.com/fork.git")

    assert Branch(REPOSITORY, "main") != Branch(other, "main")


# %% the branches that are one


def test_a_remote_branch_is_a_branch() -> None:
    assert issubclass(RemoteBranch, Branch)
