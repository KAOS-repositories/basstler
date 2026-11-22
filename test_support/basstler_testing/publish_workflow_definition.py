"""
The workflow that publishes a release's distributions, parsed into the parts its suite
checks.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

import yaml
from basstler.json_model import RawValueReader, ValidatedJSONModel
from pydantic import Field

from basstler_testing.constants.paths import RepositoryLocation

# %% vocabulary


class PublishJobName(StrEnum):
    """
    The jobs of the publish workflow.
    """

    BUILD = "build"
    PUBLISH_TESTPYPI = "publish-testpypi"
    PUBLISH_PYPI = "publish-pypi"


class PackageIndex(StrEnum):
    """
    The package indexes a release is published to, in the order they are reached; each
    value is the GitHub environment that index's trusted publisher names.
    """

    TESTPYPI = "testpypi"
    PYPI = "pypi"

    @property
    def upload_url(self) -> str | None:
        """
        Where the index takes uploads, unset where the publish action's default, PyPI
        itself, is the address.
        """
        return {
            PackageIndex.TESTPYPI: "https://test.pypi.org/legacy/",
            PackageIndex.PYPI: None,
        }[self]

    @property
    def job(self) -> PublishJobName:
        """
        The job that publishes to this index.
        """
        return {
            PackageIndex.TESTPYPI: PublishJobName.PUBLISH_TESTPYPI,
            PackageIndex.PYPI: PublishJobName.PUBLISH_PYPI,
        }[self]


class PublishAction(StrEnum):
    """
    The actions the workflow uses to hand files over and publish them.
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

    uses: str | None = None
    """
    The action it uses, with the version it pins; unset for a shell step.
    """

    run: str | None = None
    """
    The shell it runs; unset for an action step.
    """

    inputs: dict[str, Any] = Field(default_factory=dict, alias="with")
    """
    The inputs it passes to its action.
    """

    @property
    def action(self) -> str | None:
        """
        The action it uses, without its version.
        """
        return self.uses.partition("@")[0] if self.uses else None


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


class ReleaseRunTrigger(ValidatedJSONModel):
    """
    The trigger that starts the workflow when another one finishes.
    """

    workflows: list[str]
    """
    The workflows it follows, by name.
    """

    types: list[str]
    """
    The stages of their runs it starts on.
    """


class ManualTrigger(ValidatedJSONModel):
    """
    The trigger that starts the workflow by hand.
    """

    inputs: dict[str, Any] = Field(default_factory=dict)
    """
    What the person starting it may give, by input name.
    """


class PublishTriggers(ValidatedJSONModel):
    """
    The events the workflow runs on.
    """

    release_run: ReleaseRunTrigger = Field(alias="workflow_run")
    """
    The finish of a release run.
    """

    manual: ManualTrigger = Field(alias="workflow_dispatch")
    """
    A run started by hand.
    """


class PublishWorkflow(ValidatedJSONModel):
    """
    The publish workflow file.
    """

    jobs: dict[PublishJobName, PublishJob]
    """
    Its jobs, by name.
    """

    triggers: PublishTriggers = Field(alias="on")
    """
    The events it runs on.
    """

    permissions: dict[str, str] = Field(default_factory=dict)
    """
    The permissions every job starts from.
    """

    @classmethod
    def read(cls) -> PublishWorkflow:
        """
        :return: The workflow file of the repository, parsed.
        """
        data = yaml.safe_load(
            RepositoryLocation.PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        )
        # YAML reads the key ``on`` as ``True``.
        return cls.from_json(
            {"on" if key is True else key: v for key, v in data.items()}
        )

    def publishing_to(self, index: PackageIndex) -> PublishJob:
        """
        :param index: A package index.
        :return: The job that publishes to it.
        """
        return self.jobs[index.job]

    @property
    def source(self) -> str:
        """
        The file's text.
        """
        return RepositoryLocation.PUBLISH_WORKFLOW.read_text(encoding="utf-8")
