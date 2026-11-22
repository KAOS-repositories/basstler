"""
Tests for every workflow that narrows its pull requests to the files it names: that each
name still matches a file, and that a change to the workflow itself runs it.
"""

from __future__ import annotations

import pytest

from basstler.github.workflows import TriggerEvent, Workflow

from .constants.paths import RepositoryLocation

PATH_FILTERED_WORKFLOWS = tuple(
    workflow
    for workflow in Workflow.every_workflow_in_the_repository()
    if TriggerEvent.PULL_REQUEST in workflow.events
    and workflow.trigger(TriggerEvent.PULL_REQUEST).paths
)
"""
The workflows whose pull-request trigger names the files it runs for.
"""

# %% the files each workflow names


@pytest.mark.parametrize(
    ("workflow", "pattern"),
    [
        pytest.param(workflow, pattern, id=f"{workflow.file_name}:{pattern}")
        for workflow in PATH_FILTERED_WORKFLOWS
        for pattern in sorted(workflow.trigger(TriggerEvent.PULL_REQUEST).paths)
    ],
)
def test_every_path_filter_matches_a_file_in_the_repository(
    workflow: Workflow, pattern: str
):
    """
    A filter left naming a moved file would stop the workflow running for it, silently.
    """
    matched = list(RepositoryLocation.ROOT.value.glob(pattern))
    # Before Python 3.13, a pattern ending in ``**`` matches only directories.
    candidates = [path for match in matched for path in [match, *match.rglob("*")]]

    assert any(path.is_file() for path in candidates)


@pytest.mark.parametrize(
    "workflow", PATH_FILTERED_WORKFLOWS, ids=lambda workflow: workflow.file_name
)
def test_the_workflow_runs_when_it_changes(workflow: Workflow):
    """
    A change to the workflow itself is checked by running it.
    """
    own_file = workflow.path.relative_to(RepositoryLocation.ROOT.value)

    assert own_file.as_posix() in workflow.trigger(TriggerEvent.PULL_REQUEST).paths


def test_the_windows_workflows_are_path_filtered():
    """
    The parametrizations above check nothing if discovery finds neither.
    """
    assert {workflow.path for workflow in PATH_FILTERED_WORKFLOWS} == {
        RepositoryLocation.WINDOWS_SETUP_WORKFLOW.value,
        RepositoryLocation.WINDOWS_TESTS_WORKFLOW.value,
    }
