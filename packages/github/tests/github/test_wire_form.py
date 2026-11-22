"""
Tests for the forms GitHub's payloads write a branch or a pull request in.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from basstler.git.branch import Branch
from basstler.github.exceptions import RepositoryUnknown
from basstler.github.pull_request_models import UpstreamPullRequestSnapshot
from basstler.github.repository import HasRepository, PullRequestReference, Repository
from basstler.github.repository_details import RepositoryDetails, RepositoryDetailsRead
from basstler.github.rest_models import PullRequestEnd, PullRequestEndForm

from basstler_testing.upstream_reviews.recorded_rest_pull_request import UPSTREAM
from basstler_testing.upstream_reviews.replay import RecordedResponse

REPOSITORY = Repository("an-owner", "a-project")
"""
The repository every payload in these tests is read from.
"""

FORK = Repository("a-forker", "a-project")
"""
A fork of :data:`REPOSITORY`.
"""

DETAILS = {"default_branch": "trunk", "fork": False, "private": False}
"""
A repository resource of a repository that is no fork.
"""

# %% a branch named by text


def test_a_branch_named_by_text_belongs_to_the_repository_read():
    details = RepositoryDetailsRead(REPOSITORY).parse(DETAILS)

    assert details.default_branch == Branch(REPOSITORY, DETAILS["default_branch"])


def test_a_branch_named_by_text_outside_a_read_has_no_repository():
    with pytest.raises(ValidationError) as raised:
        RepositoryDetails.from_json(DETAILS)

    assert isinstance(raised.value.errors()[0]["ctx"]["error"], RepositoryUnknown)


def test_a_branch_named_by_text_is_written_as_its_name():
    details = RepositoryDetailsRead(REPOSITORY).parse(DETAILS)

    assert details.to_json()["default_branch"] == details.default_branch.name


# %% a branch of a repository the payload names


def test_a_fork_s_parent_default_branch_belongs_to_the_parent():
    details = RepositoryDetailsRead(FORK).parse(
        {
            **DETAILS,
            "fork": True,
            "parent": {"full_name": REPOSITORY.full_name, "default_branch": "main"},
        }
    )

    assert details.parent_default_branch == Branch(REPOSITORY, "main")


def test_a_pull_request_end_belongs_to_the_repository_its_payload_names():
    end = PullRequestEndForm().read(
        {"ref": "topic", "sha": "a-commit", "repo": {"full_name": FORK.full_name}},
        HasRepository(REPOSITORY),
    )

    assert end == PullRequestEnd(FORK, "topic", "a-commit")


def test_a_pull_request_end_whose_repository_was_deleted_cannot_be_read():
    with pytest.raises(RepositoryUnknown):
        PullRequestEndForm().read(
            {"ref": "topic", "sha": "a-commit", "repo": None}, None
        )


def test_a_pull_request_end_is_written_back_as_it_was_read():
    end = PullRequestEnd(FORK, "topic", "a-commit")
    form = PullRequestEndForm()

    assert form.read(form.write(end), None) == end


# %% a pull request named by its number


def test_a_pull_request_read_by_number_belongs_to_the_repository_read():
    pull_request = RecordedResponse.PULL_REQUEST_PAGE_ONE.recorded(
        UPSTREAM
    ).pull_request

    assert pull_request.reference.repository == UPSTREAM


def test_a_snapshot_keeps_the_pull_request_it_was_assembled_from():
    pull_request = RecordedResponse.PULL_REQUEST_PAGE_ONE.recorded(
        UPSTREAM
    ).pull_request

    snapshot = UpstreamPullRequestSnapshot.assemble(pull_request, [])

    assert snapshot.reference == PullRequestReference(
        UPSTREAM, pull_request.reference.number
    )
