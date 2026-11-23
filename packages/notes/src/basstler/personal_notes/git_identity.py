"""
Print where on the personal-notes branch this session's git identity is recorded.

The notes repository's owner keeps the identity at :attr:`PersonalNotesProjectLocation.GIT_IDENTITY`.
Everyone else who shares the notes branch, a collaborator of a team repository, keeps
one of their own below :attr:`PersonalNotesProjectLocation.CONTRIBUTOR_GIT_IDENTITIES`, named after
their GitHub login, so each authors their commits as themselves.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.personal_notes.git_identity
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from cyclopts import App

from basstler.exit_codes import StackExitCode
from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubAttemptClient, GitHubRestClient
from basstler.github.pull_request_record import AccountField
from basstler.github.repository import Repository
from basstler.github.repository_access import GitHubPath
from basstler.locations import ClaudeCodeVariable
from basstler.personal_notes.locations import PersonalNotesProjectLocation
from basstler.personal_notes.branch import PersonalNotesLocation
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% whose identity applies


@dataclass(frozen=True, kw_only=True)
class GitIdentityRecord:
    """
    Which identity file on the notes branch belongs to the account a session works as.
    """

    notes_repository: Repository | None
    """
    The repository holding the notes branch, ``None`` when its remote names no GitHub
    repository.
    """

    login: str | None
    """
    The GitHub login the session's credential belongs to, ``None`` when it is unknown.
    """

    @classmethod
    def of_session(
        cls,
        *,
        project_root: Path,
        environment: Mapping[str, str],
        client: GitHubAttemptClient,
    ) -> GitIdentityRecord:
        """
        :param project_root: The clone whose notes settings are read.
        :param environment: The environment the notes settings are read from.
        :param client: Asks GitHub whose credential the session holds.
        :return: The record for the account the session works as.
        """
        git = GitCommandRunner(project_root)
        notes_remote = PersonalNotesLocation.resolve(project_root, environment).remote
        notes_url = git.configured_remote_url(notes_remote) or notes_remote
        notes_repository = (
            Repository.from_remote_url(notes_url)
            if Repository.names_a_repository(notes_url)
            else None
        )
        account = client.attempt_get(str(GitHubPath.AUTHENTICATED_USER))
        login = (
            None if account.failure is not None else account.body[AccountField.LOGIN]
        )
        return cls(notes_repository=notes_repository, login=login)

    @property
    def is_owner(self) -> bool:
        """
        Whether the session works as the notes repository's owner.

        Also true when either side is unknown, so a notes branch nothing can attribute
        keeps the one identity it always had.
        """
        if self.notes_repository is None or self.login is None:
            return True
        return self.notes_repository.owner.casefold() == self.login.casefold()

    @property
    def path(self) -> PurePosixPath:
        """
        The identity file's path on the notes branch, ``/``-separated on every platform.
        """
        if self.is_owner:
            return PurePosixPath(PersonalNotesProjectLocation.GIT_IDENTITY)
        return (
            PurePosixPath(PersonalNotesProjectLocation.CONTRIBUTOR_GIT_IDENTITIES)
            / self.login
        )


# %% the command line

app = App(help=__doc__)
"""
The command, which takes no arguments.
"""


@app.default
def print_git_identity_path() -> StackExitCode:
    """
    Print the path of the identity file that belongs to this session's account.

    :return: :attr:`StackExitCode.SUCCESS`, also when GitHub does not say who the
        session is: the owner's path is the answer then.
    """
    project_root = Path(
        os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd())
    )
    record = GitIdentityRecord.of_session(
        project_root=project_root, environment=os.environ, client=GitHubRestClient()
    )
    logger.info(str(record.path))
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()
