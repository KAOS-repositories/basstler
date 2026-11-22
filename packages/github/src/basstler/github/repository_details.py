"""
What GitHub's repository resource says about a repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from basstler.git.branch import Branch
from basstler.github.permission_level import PermissionLevel
from basstler.github.pull_request_state import ForkLineage
from basstler.github.repository import Repository
from basstler.github.repository_resources import RepositoryRead
from basstler.github.wire_form import BranchName, RepositoryDefaultBranch
from basstler.json_model import RawValueReader, ValidatedJSONModel

# %% the repository resource


class ContentsAccess(RawValueReader):
    """
    Reads the requesting account's role in a repository, as its resource gives it, as
    the :class:`PermissionLevel` it has on the repository's contents.
    """

    def read(self, value: dict[str, bool]) -> PermissionLevel | None:
        if value.get("push"):
            return PermissionLevel.WRITE
        if value.get("pull"):
            return PermissionLevel.READ
        return None


class RepositoryDetails(ValidatedJSONModel):
    """
    One repository, as its REST resource describes it.
    """

    default_branch: Annotated[Branch[Repository], BranchName()]
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

    parent_default_branch: Annotated[
        Branch[Repository] | None, Field(alias="parent"), RepositoryDefaultBranch()
    ] = None
    """
    The default branch of the repository it was forked from, ``None`` when it is no
    fork.
    """

    contents_access: Annotated[
        PermissionLevel | None, Field(alias="permissions"), ContentsAccess()
    ] = None
    """
    What the requesting account may do with the repository's files and branches,
    ``None`` when it may do neither or the request was anonymous.
    """

    @property
    def lineage(self) -> ForkLineage | None:
        """
        What the repository was forked from, ``None`` unless it is a fork.
        """
        if self.parent_default_branch is None:
            return None
        return ForkLineage(
            upstream_repository=self.parent_default_branch.repository,
            upstream_default_branch=self.parent_default_branch.name,
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
