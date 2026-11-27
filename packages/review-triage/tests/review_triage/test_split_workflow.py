"""
Tests for the workflows that split a pull request into its mechanical changes and the
rest when its author asks: the reusable one and the one calling it on a label.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from basstler.github.tooling_labels import GitHubLabel
from basstler.github.workflows import TriggerEvent
from basstler.review_triage.command_names import ReviewTriageCommand
from basstler_testing.constants.paths import RepositoryLocation
from basstler_testing.workflow_definition import Workflow, WorkflowJob

# %% reading the workflows


class SplitJob(StrEnum):
    """
    The jobs of the split workflows.
    """

    SPLIT = "split"


class SplitStep(StrEnum):
    """
    The identifiers of the reusable workflow's steps the tests read.
    """

    AUTHOR = "author"
    SPLIT = "split"
    LABEL = "label"


class SplitSecret(StrEnum):
    """
    The secrets the reusable workflow takes.
    """

    PUSH_TOKEN = "push_token"


CHECKOUT_ACTION = "actions/checkout"
"""
The action that checks the repository out.
"""

START_OPTION = "--from-merge-base"
"""
The option making the split start where the pull request's change starts.
"""


@pytest.fixture
def split_job() -> WorkflowJob:
    """
    The reusable workflow's one job.
    """
    workflow = Workflow.read(RepositoryLocation.REVIEW_TRIAGE_SPLIT_MECHANICAL_WORKFLOW)
    return workflow.jobs[SplitJob.SPLIT]


# %% the reusable workflow


def test_the_split_is_a_reusable_workflow_taking_an_optional_push_token():
    workflow = Workflow.read(RepositoryLocation.REVIEW_TRIAGE_SPLIT_MECHANICAL_WORKFLOW)
    assert workflow.triggers == {TriggerEvent.WORKFLOW_CALL}
    assert workflow.called_secrets == {SplitSecret.PUSH_TOKEN: False}


def test_only_the_pull_request_s_author_is_checked_before_anything_is_checked_out(
    split_job: WorkflowJob,
):
    """
    The split replaces the author's branch, so nobody else may start it.
    """
    author = split_job.steps.index(split_job.step_identified_as(SplitStep.AUTHOR))
    checkout = split_job.steps.index(split_job.step_using(CHECKOUT_ACTION))
    assert author < checkout
    assert "$GITHUB_ACTOR" in (
        split_job.step_identified_as(SplitStep.AUTHOR).command or ""
    )


def test_the_split_runs_the_command_from_where_the_change_starts(
    split_job: WorkflowJob,
):
    """
    Starting from the merge base splits the same pull request into the same commits,
    whichever token runs it.
    """
    command = split_job.step_identified_as(SplitStep.SPLIT).command or ""
    assert f"review-triage {ReviewTriageCommand.SPLIT_MECHANICAL} " in command
    assert START_OPTION in command


def test_the_label_is_removed_however_the_split_ends(split_job: WorkflowJob):
    """
    So the author can add it again to split again.
    """
    removal = split_job.step_identified_as(SplitStep.LABEL)
    assert removal.condition == "always()"
    assert GitHubLabel.SPLIT_MECHANICAL in (removal.command or "")


# %% the calling workflow


def test_the_split_starts_when_the_split_label_is_added():
    workflow = Workflow.read(RepositoryLocation.SPLIT_MECHANICAL_WORKFLOW)
    assert workflow.triggers == {TriggerEvent.PULL_REQUEST_TARGET}
    assert (
        workflow.jobs[SplitJob.SPLIT].condition
        == f"github.event.label.name == '{GitHubLabel.SPLIT_MECHANICAL}'"
    )
