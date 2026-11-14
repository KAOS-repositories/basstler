"""
Tests for the workflow that runs the whole suite on Windows: that every pull request
ready for review runs it, and a draft or a push does not.
"""

from __future__ import annotations

from basstler.github.workflows import ActivityType, Trigger, TriggerEvent, Workflow

from basstler_testing.constants.paths import RepositoryLocation

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


# %% drafts


DRAFT_SKIP = "!github.event.pull_request.draft"
"""
The condition that runs a job only for a pull request out of draft.
"""


def test_a_pull_request_marked_ready_runs_the_workflow():
    """
    Marking a draft ready is a run of its own, so its last draft push is tested too.
    """
    assert only_trigger().activity_types == {
        *ActivityType.pull_request_defaults,
        ActivityType.READY_FOR_REVIEW,
    }


def test_the_suite_skips_a_draft_pull_request():
    """
    A draft keeps changing, so only a pull request ready for review pays for Windows.
    """
    (job,) = WINDOWS_TESTS.jobs

    assert job.condition == DRAFT_SKIP
