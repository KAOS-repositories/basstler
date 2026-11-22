"""
Tests for reading the review-triage secret through
:class:`basstler.github.actions_settings.ActionsSecretRead`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from basstler.github.actions_settings import ActionsSecretRead
from basstler.github.repository import Repository
from basstler.review_triage.viewed_request import ReviewTriageSecret

from basstler_testing.github.path_answering_client import PathAnsweringClient

# %% reading the secret

REPOSITORY = Repository("an-owner", "a-project")
"""
The repository whose secret is read.
"""


def test_a_secret_read_gives_the_secret_it_asked_for():
    """
    Reading the review-triage secret gives back that secret.
    """
    secret = ReviewTriageSecret.VIEWER_TOKEN
    client = PathAnsweringClient({secret.path_on(REPOSITORY): {"name": secret.value}})
    reading = ActionsSecretRead(REPOSITORY, secret).attempt(client)
    assert reading.resource.secret is secret


def test_a_secret_read_refuses_a_name_of_another_kind():
    """
    A read answering another secret's name is refused.
    """
    secret = ReviewTriageSecret.VIEWER_TOKEN
    client = PathAnsweringClient(
        {secret.path_on(REPOSITORY): {"name": f"NOT_{secret.value}"}}
    )
    with pytest.raises(ValidationError):
        ActionsSecretRead(REPOSITORY, secret).attempt(client)
