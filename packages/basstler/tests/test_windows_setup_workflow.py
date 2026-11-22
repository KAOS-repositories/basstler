"""
Tests for the workflow that runs the personal-notes setup on Windows: that it runs only
for pull requests.
"""

from __future__ import annotations

from basstler.github.workflows import Trigger, TriggerEvent, Workflow

from basstler_testing.constants.paths import RepositoryLocation

WINDOWS_SETUP = Workflow.at(RepositoryLocation.WINDOWS_SETUP_WORKFLOW.value)
"""
The workflow under test.
"""

# %% the changes it runs for


def only_trigger() -> Trigger:
    """
    :return: The one event the workflow answers to.
    """
    (trigger,) = WINDOWS_SETUP.triggers
    return trigger


def test_the_workflow_runs_only_for_pull_requests():
    """
    A push runs nothing on a Windows runner, so no change is paid for twice.
    """
    assert only_trigger().event is TriggerEvent.PULL_REQUEST
