"""
A repository's Actions settings: whether Actions run, whether one workflow runs, and
whether one secret is stored - each read, and where GitHub allows it, written.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


from basstler.class_property import classproperty
from basstler.github.workflows import RepositoryWorkflow
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
class WorkflowRead(RepositoryWorkflow, RepositoryRead[WorkflowDetails]):
    """
    Reads one workflow of a repository.
    """

    @property
    def path(self) -> str:
        return self.repository.workflow_resource_path(self.workflow_path)


class WorkflowEnabling(RepositoryWorkflow, SettingWrite[WorkflowDetails]):
    """
    Enables one workflow of a repository.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.PUT

    @property
    def path(self) -> str:
        return f"{self.repository.workflow_resource_path(self.workflow_path)}/enable"

    @property
    def manual_step(self) -> UserStep:
        return EnableWorkflow(self.repository, self.workflow_path)


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
