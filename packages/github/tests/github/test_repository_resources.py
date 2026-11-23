"""
Tests for github/repository_resources.py: reads bound to the model they parse, and
writes bound to the resource they change.
"""

from __future__ import annotations

from http import HTTPStatus


from basstler.github.actions_settings import (
    ActionsEnabling,
    ActionsPermissions,
    ActionsPermissionsRead,
    WorkflowDetails,
    WorkflowEnabling,
)
from basstler.github.repository import Repository
from basstler.github.user_steps import AllowActions, EnableWorkflow
from basstler.review_triage.locations import ReviewTriageWorkflowLocation

from basstler_testing.github.path_answering_client import PathAnsweringClient

# %% reading

REPOSITORY = Repository("an-owner", "a-project")
"""
The repository every read and write here is for.
"""


def test_a_read_parses_the_served_resource_into_its_bound_model():
    client = PathAnsweringClient(
        {REPOSITORY.actions_permissions_path: {"enabled": True}}
    )
    reading = ActionsPermissionsRead(REPOSITORY).attempt(client)
    assert reading.resource == ActionsPermissions(enabled=True)


def test_a_refused_read_parses_nothing_and_keeps_github_s_refusal():
    client = PathAnsweringClient(forbidden={REPOSITORY.actions_permissions_path})
    reading = ActionsPermissionsRead(REPOSITORY).attempt(client)
    assert (reading.resource, reading.response.failure.status) == (
        None,
        HTTPStatus.FORBIDDEN,
    )


# %% writing a resource


def test_each_setting_write_names_the_setting_it_changes():
    assert (ActionsEnabling.resource_type, WorkflowEnabling.resource_type) == (
        ActionsPermissions,
        WorkflowDetails,
    )


def test_each_setting_write_is_taken_by_hand_as_its_own_user_step():
    assert (
        ActionsEnabling(REPOSITORY).manual_step,
        WorkflowEnabling(
            REPOSITORY, ReviewTriageWorkflowLocation.MARK_VIEWED
        ).manual_step,
    ) == (
        AllowActions(REPOSITORY, known_off=True),
        EnableWorkflow(REPOSITORY, ReviewTriageWorkflowLocation.MARK_VIEWED),
    )
