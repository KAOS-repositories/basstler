"""
Tests for :mod:`basstler.personal_notes.git_identity`: which identity file on the notes
branch belongs to the account a session works as.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import PurePosixPath

from basstler.github.client import (
    GitHubAttemptClient,
    GitHubResponse,
    GitHubWrite,
    HttpMethod,
)
from basstler.github.credential import CredentialProvider
from basstler.github.exceptions import GitHubRequestFailed
from basstler.github.pull_request_record import AccountField
from basstler.github.repository import Repository
from basstler.github.repository_access import GitHubPath
from basstler.locations import ProjectLocation
from basstler.personal_notes.git_identity import GitIdentityRecord

from ..scratch_repository import ScratchRepository

SHARED_NOTES = Repository.parse("an-owner/a-team-project")
"""
A notes repository its owner shares with colleagues.
"""

COLLEAGUE = "a-colleague"
"""
The login of someone who shares :data:`SHARED_NOTES` without owning it.
"""

# %% a GitHub answering from memory


@dataclass
class AccountReadingClient(GitHubAttemptClient):
    """
    Answers the authenticated account's read with :attr:`login`, or refuses it when that
    is ``None``, recording what was read.
    """

    login: str | None
    """
    The login GitHub answers with, ``None`` to refuse the read.
    """

    reads: list[str] = field(default_factory=list)
    """
    Every path read, oldest first.
    """

    def attempt_get(self, path: str) -> GitHubResponse:
        self.reads.append(path)
        if self.login is not None:
            return GitHubResponse({AccountField.LOGIN.value: self.login})
        return GitHubResponse(
            None,
            failure=GitHubRequestFailed(
                status=HTTPStatus.UNAUTHORIZED,
                detail="",
                method=HttpMethod.GET,
                path=path,
                credential_origin=CredentialProvider.CALLER,
            ),
        )

    def attempt_send(self, write: GitHubWrite) -> GitHubResponse:
        raise AssertionError(f"the identity lookup sent a write: {write}")


# %% whose file applies


def test_the_owner_keeps_the_identity_file_it_always_had():
    record = GitIdentityRecord(notes_repository=SHARED_NOTES, login=SHARED_NOTES.owner)

    assert record.path == PurePosixPath(ProjectLocation.GIT_IDENTITY)


def test_the_owner_is_recognized_whatever_the_case_of_the_login():
    record = GitIdentityRecord(
        notes_repository=SHARED_NOTES, login=SHARED_NOTES.owner.upper()
    )

    assert record.is_owner


def test_a_colleague_gets_a_file_named_after_their_login():
    record = GitIdentityRecord(notes_repository=SHARED_NOTES, login=COLLEAGUE)

    assert record.path == (
        PurePosixPath(ProjectLocation.CONTRIBUTOR_GIT_IDENTITIES) / COLLEAGUE
    )


def test_an_unknown_login_falls_back_to_the_owner_s_file():
    record = GitIdentityRecord(notes_repository=SHARED_NOTES, login=None)

    assert record.path == PurePosixPath(ProjectLocation.GIT_IDENTITY)


def test_a_notes_remote_naming_no_repository_falls_back_to_the_owner_s_file():
    record = GitIdentityRecord(notes_repository=None, login=COLLEAGUE)

    assert record.path == PurePosixPath(ProjectLocation.GIT_IDENTITY)


# %% reading the session


def test_the_session_s_login_and_notes_repository_are_read(
    scratch_repository: ScratchRepository,
):
    scratch_repository.serve_notes_remote_as(SHARED_NOTES)
    client = AccountReadingClient(login=COLLEAGUE)

    record = GitIdentityRecord.of_session(
        project_root=scratch_repository.project_root, environment={}, client=client
    )

    assert record == GitIdentityRecord(notes_repository=SHARED_NOTES, login=COLLEAGUE)
    assert client.reads == [str(GitHubPath.AUTHENTICATED_USER)]


def test_a_refused_account_read_leaves_the_login_unknown(
    scratch_repository: ScratchRepository,
):
    scratch_repository.serve_notes_remote_as(SHARED_NOTES)

    record = GitIdentityRecord.of_session(
        project_root=scratch_repository.project_root,
        environment={},
        client=AccountReadingClient(login=None),
    )

    assert record.login is None
