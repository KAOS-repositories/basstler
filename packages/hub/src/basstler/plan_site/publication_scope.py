"""
Which of the repositories a hub file lists a site build may publish.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from basstler.github.client import GitHubAttemptReader
from basstler.github.repository import Repository
from basstler.github.repository_visibility import (
    ReaderWithoutCredential,
    RepositoryVisibility,
)


class PublicationScope(ABC):
    """
    Decides, before a repository's notes are fetched, whether a build publishes it.
    """

    @abstractmethod
    def exclusion_of(self, repository: Repository) -> str | None:
        """
        :param repository: A repository the hub file lists.
        :return: Why the build leaves it out, ``None`` when it publishes it.
        """


@dataclass(frozen=True)
class PublicRepositoriesOnly(PublicationScope):
    """
    Publishes only repositories GitHub says are public, whatever the build's token can
    read.
    """

    github: GitHubAttemptReader = field(
        default_factory=ReaderWithoutCredential.client_from_environment_or_this
    )
    """
    What answers each repository's resource, which says who can read it.
    """

    def exclusion_of(self, repository: Repository) -> str | None:
        visibility = RepositoryVisibility.read_from(self.github, repository)
        if visibility is RepositoryVisibility.PUBLIC:
            return None
        return f"its visibility is {visibility}, and the site publishes only public repositories"


@dataclass(frozen=True)
class EveryRepository(PublicationScope):
    """
    Publishes every listed repository, private ones in full, for a site only this
    computer serves.
    """

    def exclusion_of(self, repository: Repository) -> str | None:
        return None
