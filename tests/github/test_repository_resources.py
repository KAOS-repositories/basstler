"""
Tests for github/repository_resources.py: reads bound to the model they parse, and
writes bound to the resource they change.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from pydantic import ValidationError

from basstler.github.actions_settings import (
    ActionsEnabling,
    ActionsSecretRead,
    ActionsPermissions,
    ActionsPermissionsRead,
    WorkflowDetails,
    WorkflowEnabling,
)
from basstler.github.repository import Repository
from basstler.github.user_steps import AllowActions, EnableWorkflow
from basstler.locations import WorkflowLocation
from basstler.review_triage.viewed_request import ReviewTriageSecret

from .path_answering_client import PathAnsweringClient

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


def test_a_secret_read_gives_the_secret_it_asked_for():
    secret = ReviewTriageSecret.VIEWER_TOKEN
    client = PathAnsweringClient({secret.path_on(REPOSITORY): {"name": secret.value}})
    reading = ActionsSecretRead(REPOSITORY, secret).attempt(client)
    assert reading.resource.name is secret


def test_a_secret_read_refuses_a_name_of_another_kind():
    secret = ReviewTriageSecret.VIEWER_TOKEN
    client = PathAnsweringClient(
        {secret.path_on(REPOSITORY): {"name": f"NOT_{secret.value}"}}
    )
    with pytest.raises(ValidationError):
        ActionsSecretRead(REPOSITORY, secret).attempt(client)


# %% writing a resource


def test_each_setting_write_names_the_setting_it_changes():
    assert (ActionsEnabling.resource_type, WorkflowEnabling.resource_type) == (
        ActionsPermissions,
        WorkflowDetails,
    )


def test_each_setting_write_is_taken_by_hand_as_its_own_user_step():
    assert (
        ActionsEnabling(REPOSITORY).manual_step,
        WorkflowEnabling(REPOSITORY, WorkflowLocation.MARK_VIEWED).manual_step,
    ) == (
        AllowActions(REPOSITORY, known_off=True),
        EnableWorkflow(REPOSITORY, WorkflowLocation.MARK_VIEWED),
    )
