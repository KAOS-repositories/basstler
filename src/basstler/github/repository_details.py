"""
What GitHub's repository resource says about a repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from basstler.git.branch import Branch
from basstler.github.pull_request_state import ForkLineage
from basstler.github.repository import Repository
from basstler.github.repository_resources import RepositoryRead
from basstler.json_model import RawValueReader, ValidatedJSONModel

# %% the repository resource


class BranchName(RawValueReader):
    """
    Reads a branch's name, as a repository's resource gives it, as the :class:`Branch`.
    """

    def read(self, value: str) -> Branch:
        return Branch(value)


class ParentRepository(ValidatedJSONModel):
    """
    The repository a fork was made from, as the fork's resource names it.
    """

    full_name: str
    """
    The parent's ``owner/name``.
    """

    default_branch: Annotated[Branch, BranchName()]
    """
    The parent's default branch.
    """

    @property
    def repository(self) -> Repository:
        """
        The parent itself.
        """
        return Repository.parse(self.full_name)


class RepositoryDetails(ValidatedJSONModel):
    """
    One repository, as its REST resource describes it.
    """

    default_branch: Annotated[Branch, BranchName()]
    """
    The branch pull requests target unless told otherwise.
    """

    is_fork: Annotated[bool, Field(alias="fork")]
    """
    Whether it is a fork, whose default branch follows its upstream's.
    """

    is_private: Annotated[bool, Field(alias="private")]
    """
    Whether only the people and tokens granted access can read it.
    """

    parent: ParentRepository | None = None
    """
    The repository it was forked from, ``None`` when it is no fork.
    """

    @property
    def lineage(self) -> ForkLineage | None:
        """
        What the repository was forked from, ``None`` unless it is a fork.
        """
        if self.parent is None:
            return None
        return ForkLineage(
            upstream_repository=self.parent.repository,
            upstream_default_branch=self.parent.default_branch.name,
            fork_default_branch=self.default_branch.name,
        )


# %% reading it


@dataclass(frozen=True)
class RepositoryDetailsRead(RepositoryRead[RepositoryDetails]):
    """
    Reads a repository's own resource.
    """

    @property
    def path(self) -> str:
        return self.repository.api_path
