"""
Tests for reading who can read a repository from its GitHub resource.
"""

from __future__ import annotations

import pytest

from basstler.github.repository import Repository
from basstler.github.repository_visibility import (
    ReaderWithoutCredential,
    RepositoryVisibility,
)

from basstler_testing.github.visibility_client import visibility_client

# %% reading visibility

PUBLIC_REPOSITORY = Repository("owner", "public")
"""
A repository GitHub describes as public.
"""

PRIVATE_REPOSITORY = Repository("owner", "private")
"""
A repository GitHub describes as private.
"""

UNDESCRIBED_REPOSITORY = Repository("owner", "undescribed")
"""
A repository GitHub refuses to describe.
"""


@pytest.mark.parametrize(
    ("repository", "visibility"),
    [
        (PUBLIC_REPOSITORY, RepositoryVisibility.PUBLIC),
        (PRIVATE_REPOSITORY, RepositoryVisibility.PRIVATE),
        (UNDESCRIBED_REPOSITORY, RepositoryVisibility.UNREADABLE),
    ],
)
def test_reads_each_repository_s_visibility(
    repository: Repository, visibility: RepositoryVisibility
):
    github = visibility_client(public=[PUBLIC_REPOSITORY], private=[PRIVATE_REPOSITORY])
    assert RepositoryVisibility.read_from(github, repository) is visibility


def test_reads_visibility_as_unknown_without_a_credential():
    visibility = RepositoryVisibility.read_from(
        ReaderWithoutCredential(), PUBLIC_REPOSITORY
    )
    assert visibility is RepositoryVisibility.UNREADABLE
