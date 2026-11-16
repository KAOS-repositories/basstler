"""
A repository's Actions settings: whether Actions run, whether one workflow runs, and
whether one secret is stored - each read, and where GitHub allows it, written.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import Field

from basstler.class_property import classproperty
from basstler.github.actions_secret import ActionsSecret
from basstler.github.client import HttpMethod
from basstler.github.repository_resources import RepositoryRead, SettingWrite
from basstler.github.user_steps import AllowActions, EnableWorkflow, UserStep
from basstler.json_model import ValidatedJSONModel

# %% whether Actions run


class ActionsPermissions(ValidatedJSONModel):
    """
    Whether a repository runs Actions at all.
    """

    enabled: bool
    """
    Whether Actions may run in the repository.
    """


@dataclass(frozen=True)
class ActionsPermissionsRead(RepositoryRead[ActionsPermissions]):
    """
    Reads whether a repository runs Actions.
    """

    @property
    def path(self) -> str:
        return self.repository.actions_permissions_path


class ActionsEnabling(SettingWrite[ActionsPermissions]):
    """
    Lets a repository run Actions.
    """

    enabled: bool = True
    """
    Whether Actions may run; always on.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.PUT

    @property
    def path(self) -> str:
        return self.repository.actions_permissions_path

    @property
    def manual_step(self) -> UserStep:
        return AllowActions(self.repository, known_off=True)


# %% whether one workflow runs


class WorkflowState(StrEnum):
    """
    The states GitHub reports a workflow in.
    """

    ACTIVE = "active"
    """
    It runs when started.
    """


class WorkflowDetails(ValidatedJSONModel):
    """
    One workflow of a repository, as its REST resource describes it.
    """

    state: str
    """
    Whether it runs, :attr:`WorkflowState.ACTIVE`, or why not; a fork's workflows
    start out disabled.
    """


@dataclass(frozen=True)
class WorkflowRead(RepositoryRead[WorkflowDetails]):
    """
    Reads one workflow of a repository.
    """

    workflow: Path
    """
    The workflow's file in the repository.
    """

    @property
    def path(self) -> str:
        return self.repository.workflow_path(self.workflow)


class WorkflowEnabling(SettingWrite[WorkflowDetails]):
    """
    Enables one workflow of a repository.
    """

    workflow: Annotated[Path, Field(exclude=True)]
    """
    The workflow's file in the repository.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.PUT

    @property
    def path(self) -> str:
        return f"{self.repository.workflow_path(self.workflow)}/enable"

    @property
    def manual_step(self) -> UserStep:
        return EnableWorkflow(self.repository, self.workflow)


# %% whether one secret is stored


class StoredSecretMetadata(ValidatedJSONModel):
    """
    One Actions secret a repository stores, as GitHub describes it without its value.
    """

    name: str
    """
    The secret's name.
    """


@dataclass(frozen=True)
class ActionsSecretRead(RepositoryRead[StoredSecretMetadata]):
    """
    Reads whether a repository stores one Actions secret; GitHub never serves its value.
    """

    secret: ActionsSecret
    """
    The secret.
    """

    @property
    def path(self) -> str:
        return self.secret.path_on(self.repository)
