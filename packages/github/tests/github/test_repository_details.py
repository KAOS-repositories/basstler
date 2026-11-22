"""
Tests for :mod:`basstler.github.repository_details`: what the repository resource says
the requesting account may do with the repository's contents.
"""

from __future__ import annotations

import pytest

from basstler.github.permission_level import PermissionLevel
from basstler.github.repository import Repository
from basstler.github.repository_details import RepositoryDetailsRead

REPOSITORY = Repository("an-owner", "a-project")
"""
The repository the resources in these tests are read from.
"""

REPOSITORY_RESOURCE = {"default_branch": "main", "fork": False, "private": False}
"""
The fields of a repository's resource every answer carries.
"""

# %% the account's access to the contents


@pytest.mark.parametrize(
    ("role", "access"),
    [
        ({"admin": False, "push": True, "pull": True}, PermissionLevel.WRITE),
        ({"admin": False, "push": False, "pull": True}, PermissionLevel.READ),
        ({"admin": False, "push": False, "pull": False}, None),
    ],
    ids=["may push", "may only read", "may do neither"],
)
def test_the_account_s_role_is_read_as_its_access_to_the_contents(
    role: dict[str, bool], access: PermissionLevel | None
):
    details = RepositoryDetailsRead(REPOSITORY).parse(
        {**REPOSITORY_RESOURCE, "permissions": role}
    )

    assert details.contents_access is access


def test_an_anonymous_answer_grants_no_access():
    assert (
        RepositoryDetailsRead(REPOSITORY).parse(REPOSITORY_RESOURCE).contents_access
        is None
    )
