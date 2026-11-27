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


def test_only_the_pull_request_s_author_may_add_the_label(split_job: WorkflowJob):
    """
    Splitting is the author's choice; a push to a branch carrying the label is split
    for whoever pushed.
    """
    author = split_job.step_identified_as(SplitStep.AUTHOR)
    assert author.condition == "inputs.requested_by_label"
    assert "$GITHUB_ACTOR" in (author.command or "")


def test_the_author_is_checked_before_anything_is_checked_out(split_job: WorkflowJob):
    author = split_job.steps.index(split_job.step_identified_as(SplitStep.AUTHOR))
    checkout = split_job.steps.index(split_job.step_using(CHECKOUT_ACTION))
    assert author < checkout


def test_the_split_runs_the_command_reading_the_whole_change(split_job: WorkflowJob):
    """
    The command finds where the previous split ended itself, so no start is given.
    """
    command = split_job.step_identified_as(SplitStep.SPLIT).command or ""
    assert f"review-triage {ReviewTriageCommand.SPLIT_MECHANICAL} " in command
    assert "--since" not in command
    assert "--from-merge-base" not in command


def test_a_label_someone_else_added_is_removed(split_job: WorkflowJob):
    """
    Left on, it would split every later push.
    """
    removal = split_job.step_identified_as(SplitStep.LABEL)
    assert removal.condition == "failure() && steps.author.outcome == 'failure'"
    assert GitHubLabel.SPLIT_MECHANICAL in (removal.command or "")


# %% the calling workflow


def test_the_split_runs_when_the_label_is_added_and_on_every_push_it_stays_on():
    workflow = Workflow.read(RepositoryLocation.SPLIT_MECHANICAL_WORKFLOW)
    assert workflow.triggers == {TriggerEvent.PULL_REQUEST_TARGET}
    assert workflow.jobs[SplitJob.SPLIT].condition == (
        f"(github.event.action == 'labeled' && github.event.label.name == "
        f"'{GitHubLabel.SPLIT_MECHANICAL}') || (github.event.action == 'synchronize' && "
        f"contains(github.event.pull_request.labels.*.name, "
        f"'{GitHubLabel.SPLIT_MECHANICAL}'))"
    )
