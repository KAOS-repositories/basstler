"""
Tests for the workflow that runs the whole suite on Windows: that every push to main
runs it within the tests the release waits for, and a pull request only when it changes
what Windows is known to treat differently.
"""

from __future__ import annotations

from basstler.github.workflows import (
    ActivityType,
    Job,
    Trigger,
    TriggerEvent,
    Workflow,
)

from basstler_testing.constants.paths import RepositoryLocation

WINDOWS_TESTS = Workflow.at(RepositoryLocation.WINDOWS_TESTS_WORKFLOW.value)
"""
The workflow under test.
"""

TESTS = Workflow.at(RepositoryLocation.TESTS_WORKFLOW.value)
"""
The workflow whose run on main the release waits for.
"""

PUSH_ONLY = "github.event_name == 'push'"
"""
The condition that runs a job of the tests only for a push, never for a pull request.
"""

DRAFT_SKIP = "!github.event.pull_request.draft"
"""
The condition that runs a job only for a pull request out of draft.
"""

# %% a push to main


def calling_job() -> Job:
    """
    :return: The job of the tests that runs this workflow.
    """
    (job,) = (
        job
        for job in TESTS.jobs
        if job.reusable_workflow
        == f"{TESTS.local_reference_prefix}{WINDOWS_TESTS.file_name}"
    )
    return job


def test_the_workflow_can_run_as_a_job_of_another():
    """
    The tests of a push run it as one of their jobs.
    """
    assert TriggerEvent.WORKFLOW_CALL in WINDOWS_TESTS.events


def test_the_tests_of_a_push_run_the_workflow():
    """
    The release waits for the tests of the push, so it never tags a commit Windows
    fails.
    """
    assert PUSH_ONLY in calling_job().condition


def test_a_push_does_not_run_the_workflow_on_its_own():
    """
    The tests of the push already run it, and a second run would cost twice again.
    """
    assert TriggerEvent.PUSH not in WINDOWS_TESTS.events


def test_the_workflow_can_be_started_by_hand():
    """
    A pull request the path filter leaves out can still be tested on Windows.
    """
    assert TriggerEvent.WORKFLOW_DISPATCH in WINDOWS_TESTS.events


# %% a pull request


def pull_request_trigger() -> Trigger:
    """
    :return: The workflow's pull-request trigger.
    """
    return WINDOWS_TESTS.trigger(TriggerEvent.PULL_REQUEST)


def test_a_pull_request_runs_the_workflow_only_for_the_files_it_names():
    """
    The portability rules catch the rest on Linux; main's run catches what they miss.
    """
    assert pull_request_trigger().paths


def test_a_pull_request_marked_ready_runs_the_workflow():
    """
    Marking a draft ready is a run of its own, so its last draft push is tested too.
    """
    assert pull_request_trigger().activity_types == {
        *ActivityType.pull_request_defaults,
        ActivityType.READY_FOR_REVIEW,
    }


def test_the_suite_skips_a_draft_pull_request():
    """
    A draft keeps changing, so only a pull request ready for review pays for Windows.
    """
    (job,) = WINDOWS_TESTS.jobs

    assert job.condition == DRAFT_SKIP


# %% speed


def test_the_suite_runs_in_several_shards_at_once():
    """
    One Windows runner takes over half an hour for the suite, so it is split.
    """
    (job,) = WINDOWS_TESTS.jobs

    assert (job.instances or 0) > 1
