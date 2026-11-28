"""
Who can read a repository, as GitHub's repository resource says.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from basstler.github.client import (
    GitHubAttemptReader,
    GitHubResponse,
    GitHubRestClient,
    HttpMethod,
)
from basstler.github.exceptions import GitHubUnreachableError
from basstler.github.repository import Repository
from basstler.github.repository_details import RepositoryDetailsRead


class RepositoryVisibility(StrEnum):
    """
    Who can read a repository, as far as this run could tell.
    """

    PUBLIC = "public"
    """
    Anybody can read it.
    """

    PRIVATE = "private"
    """
    Only the people and tokens granted access can read it.
    """

    UNREADABLE = "unreadable"
    """
    GitHub refused to say, or could not be reached.
    """

    @classmethod
    def read_from(
        cls, github: GitHubAttemptReader, repository: Repository
    ) -> RepositoryVisibility:
        """
        :param github: What answers the repository's resource.
        :param repository: The repository to look up.
        :return: Who can read it.
        """
        details = RepositoryDetailsRead(repository).attempt(github).resource
        if details is None:
            return cls.UNREADABLE
        return cls.PRIVATE if details.is_private else cls.PUBLIC


@dataclass(frozen=True)
class ReaderWithoutCredential(GitHubAttemptReader):
    """
    Stands in for GitHub when no token is available, answering every read as unreachable
    so visibility reads as unknown.
    """

    def attempt_get(self, path: str) -> GitHubResponse:
        return GitHubResponse(
            None,
            failure=GitHubUnreachableError(
                HttpMethod.GET, path, "no GitHub token is available"
            ),
        )

    @classmethod
    def client_from_environment_or_this(cls) -> GitHubAttemptReader:
        """
        :return: A client with the environment's credential, or this stand-in when the
            environment has none.
        """
        client = GitHubRestClient()
        return client if client.found_credential is not None else cls()
