"""
A workflow file that publishes a release's distributions to a package index through
trusted publishing, parsed into the parts that decide how it publishes.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import yaml
from basstler.github.workflows import TriggerEvent
from basstler.json_model import RawValueReader, ValidatedJSONModel
from basstler.text_file import TextFile
from pydantic import Field

# %% vocabulary


class PublishAction(StrEnum):
    """
    The actions a publishing workflow uses to hand files over and publish them.
    """

    PUBLISH = "pypa/gh-action-pypi-publish"
    UPLOAD = "actions/upload-artifact"
    DOWNLOAD = "actions/download-artifact"


class IdentityTokenPermission(StrEnum):
    """
    The permission that lets a job request an identity token, and the level it needs.
    """

    SCOPE = "id-token"
    LEVEL = "write"


class PublishActionInput(StrEnum):
    """
    The inputs of the publish action a release depends on.
    """

    REPOSITORY_URL = "repository-url"
    PACKAGES_DIRECTORY = "packages-dir"
    SKIP_EXISTING = "skip-existing"
    PASSWORD = "password"


class ArtifactActionInput(StrEnum):
    """
    The inputs of the actions that hand files between jobs a release depends on.
    """

    PATH = "path"


# %% the parts of the file


class ListOfOne(RawValueReader):
    """
    Reads a single value as the list holding it, as a workflow file may write either.
    """

    def read(self, value: Any) -> Any:
        """
        :param value: A value or a list of them.
        :return: A list.
        """
        return value if isinstance(value, list) else [value]


class PublishStep(ValidatedJSONModel):
    """
    One step of a job.
    """

    step_id: str | None = Field(default=None, alias="id")
    """
    The name other steps and jobs refer to it by; unset when none does.
    """

    uses: str | None = None
    """
    The action it uses, with the version it pins; unset for a shell step.
    """

    run: str | None = None
    """
    The shell it runs; unset for an action step.
    """

    action_inputs_by_name: dict[str, Any] = Field(default_factory=dict, alias="with")
    """
    The inputs it passes to its action.
    """

    environment_variables: dict[str, str] = Field(default_factory=dict, alias="env")
    """
    The environment variables it sets, by name.
    """

    @property
    def action(self) -> str | None:
        """
        The action it uses, without its version.
        """
        return self.uses.partition("@")[0] if self.uses else None


class PublishStrategy(ValidatedJSONModel):
    """
    How a job is run once for each combination of its matrix.
    """

    matrix: dict[str, Any]
    """
    The values each run takes, by the variable that holds them.
    """

    fail_fast: bool = Field(default=True, alias="fail-fast")
    """
    Whether one run failing cancels the others.
    """


class PublishJob(ValidatedJSONModel):
    """
    One job of the workflow.
    """

    steps: list[PublishStep]
    """
    Its steps, in order.
    """

    condition: str | None = Field(default=None, alias="if")
    """
    The condition it runs under; unset when it always runs.
    """

    needs: Annotated[list[str], ListOfOne()] = Field(default_factory=list)
    """
    The jobs that must succeed before it starts.
    """

    environment: str | None = None
    """
    The GitHub environment it runs in.
    """

    permissions: dict[str, str] = Field(default_factory=dict)
    """
    The permissions it asks for, by scope.
    """

    strategy: PublishStrategy | None = None
    """
    The matrix it runs over; unset when it runs once.
    """

    outputs: dict[str, str] = Field(default_factory=dict)
    """
    The values it hands to the jobs that need it, by name.
    """

    @property
    def requests_identity_token(self) -> bool:
        """
        Whether it may ask for the identity token an index's trusted publisher accepts.
        """
        return (
            self.permissions.get(IdentityTokenPermission.SCOPE)
            == IdentityTokenPermission.LEVEL
        )

    def step_using(self, action: PublishAction) -> PublishStep:
        """
        :param action: An action, without its version.
        :return: The one step that uses it.
        """
        (step,) = (step for step in self.steps if step.action == action)
        return step

    def identified_step(self, step_id: str) -> PublishStep:
        """
        :param step_id: The name a step is referred to by.
        :return: The step of that name.
        """
        (step,) = (step for step in self.steps if step.step_id == step_id)
        return step


class FollowedRunTrigger(ValidatedJSONModel):
    """
    The trigger that starts the workflow when other workflows' runs reach a stage.
    """

    workflow_names: list[str] = Field(alias="workflows")
    """
    The workflows it follows.
    """

    trigger_types: list[str] = Field(alias="types")
    """
    The stages of their runs it starts on.
    """


class ManualTrigger(ValidatedJSONModel):
    """
    The trigger that starts the workflow by hand.
    """

    inputs_by_name: dict[str, Any] = Field(default_factory=dict, alias="inputs")
    """
    What the person starting it may give.
    """


class PublishTriggers(ValidatedJSONModel):
    """
    The events the workflow runs on.
    """

    followed_run: FollowedRunTrigger = Field(alias=TriggerEvent.WORKFLOW_RUN)
    """
    The stage of another workflow's run that starts it.
    """

    manual: ManualTrigger = Field(alias=TriggerEvent.WORKFLOW_DISPATCH)
    """
    A run started by hand.
    """


class TriggersKey(StrEnum):
    """
    The key that holds a workflow's events, which YAML reads as ``True``.
    """

    ON = "on"


class PublishWorkflow(ValidatedJSONModel):
    """
    A workflow file that publishes a release.
    """

    jobs: dict[str, PublishJob]
    """
    Its jobs, by name.
    """

    triggers: PublishTriggers = Field(alias=TriggersKey.ON)
    """
    The events it runs on.
    """

    permissions: dict[str, str] = Field(default_factory=dict)
    """
    The permissions every job starts from.
    """

    @classmethod
    def read(cls, path: Path) -> PublishWorkflow:
        """
        :param path: A workflow file.
        :return: The parsed workflow.
        """
        data = yaml.safe_load(TextFile(path).read())
        return cls.from_json(
            {
                TriggersKey.ON if key is True else key: value
                for key, value in data.items()
            }
        )
