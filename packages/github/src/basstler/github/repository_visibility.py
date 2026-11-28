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
    def or_client_from_environment(cls) -> GitHubAttemptReader:
        """
        :return: A client with the environment's credential, or this stand-in when the
            environment has none.
        """
        client = GitHubRestClient()
        return client if client.found_credential is not None else cls()


@dataclass(frozen=True)
class RepositoryVisibilityReader:
    """
    Reads each repository's :class:`RepositoryVisibility` from GitHub.
    """

    github: GitHubAttemptReader
    """
    What answers the repositories' resources.
    """

    def visibility_of(self, repository: Repository) -> RepositoryVisibility:
        """
        :param repository: The repository to look up.
        :return: Who can read it.
        """
        answer = self.github.attempt_get(repository.api_path)
        if answer.failure is not None:
            return RepositoryVisibility.UNREADABLE
        if RepositoryDetailsRead(repository).parse(answer.body).is_private:
            return RepositoryVisibility.PRIVATE
        return RepositoryVisibility.PUBLIC
