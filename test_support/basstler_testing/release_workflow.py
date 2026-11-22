"""
The release workflow as YAML loads it, and the branches it moves each release to.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import yaml

from basstler.text_file import TextFile

from .constants.paths import RepositoryLocation

# %% the release workflow file


class WorkflowFileKey(StrEnum):
    """
    The keys of a workflow file read here, beyond those :mod:`basstler.github.workflows` reads.
    """

    NAME = "name"
    """
    The workflow's name, which another workflow's ``workflow_run`` trigger follows it by.
    """

    WORKFLOWS = "workflows"
    """
    The workflows a ``workflow_run`` trigger follows.
    """

    STEPS = "steps"
    """
    A job's steps.
    """

    WITH = "with"
    """
    The inputs a step hands its action.
    """

    REF = "ref"
    """
    The commit the checkout action checks out.
    """

    ENVIRONMENT = "env"
    """
    The variables a workflow sets for every job.
    """


class ReleaseWorkflowVariable(StrEnum):
    """
    The variables the release workflow sets for its steps.
    """

    RELEASE_BRANCH = "RELEASE_BRANCH"
    """
    The branch the release moves to its tag.
    """

    PLUGIN_RELEASE_BRANCH = "PLUGIN_RELEASE_BRANCH"
    """
    The branch holding only the plugin at the latest release, at the branch's root.
    """


def release_workflow_file() -> dict[Any, Any]:
    """
    :return: The release workflow as YAML loads it, which reads the ``on`` key as ``True``.
    """
    return yaml.safe_load(TextFile(RepositoryLocation.RELEASE_WORKFLOW).read())


# %% the branches a release moves


def release_branch() -> str:
    """
    :return: The branch the release workflow moves to each release.
    """
    return release_workflow_file()[WorkflowFileKey.ENVIRONMENT][
        ReleaseWorkflowVariable.RELEASE_BRANCH
    ]


def plugin_release_branch() -> str:
    """
    :return: The branch the release workflow moves to each release's plugin.
    """
    return release_workflow_file()[WorkflowFileKey.ENVIRONMENT][
        ReleaseWorkflowVariable.PLUGIN_RELEASE_BRANCH
    ]
