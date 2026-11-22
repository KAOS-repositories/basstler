"""
Bringing a fork's branch up to date with its parent's by moving it forward.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from basstler.class_property import classproperty
from basstler.git.branch import Branch
from basstler.github.client import HttpMethod
from basstler.github.file_proposal import ExistingBranch
from basstler.github.git_objects import GitObject
from basstler.github.repository_resources import SettingWrite
from basstler.github.user_steps import SyncFork, UserStep

# %% moving a fork's branch forward


class ForkFastForward(SettingWrite[ExistingBranch], GitObject):
    """
    Moves a fork's branch forward to a commit of its parent's, the object it stands for;
    GitHub refuses it unless the branch's commit is an ancestor of that commit.
    """

    branch: Annotated[Branch, Field(exclude=True)]
    """
    The fork's branch.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.PATCH

    @property
    def path(self) -> str:
        return self.repository.branch_update_path(self.branch)

    @property
    def manual_step(self) -> UserStep:
        return SyncFork(self.repository)
