"""
Tests for the workflow that runs the whole suite on Windows: that every pull request
runs it, and a push does not.
"""

from __future__ import annotations

from basstler.github.workflows import Trigger, TriggerEvent, Workflow

from .constants.paths import RepositoryLocation

WINDOWS_TESTS = Workflow.at(RepositoryLocation.WINDOWS_TESTS_WORKFLOW.value)
"""
The workflow under test.
"""

# %% the changes it runs for


def only_trigger() -> Trigger:
    """
    :return: The one event the workflow answers to.
    """
    (trigger,) = WINDOWS_TESTS.triggers
    return trigger


def test_the_workflow_runs_only_for_pull_requests():
    """
    A push to main was already tested by its pull request, on a runner that costs twice.
    """
    assert only_trigger().event is TriggerEvent.PULL_REQUEST


def test_the_workflow_runs_for_every_pull_request():
    """
    A change outside any filter can break Windows as well, so none narrows the trigger.
    """
    assert only_trigger().runs_on_every_pull_request_push
