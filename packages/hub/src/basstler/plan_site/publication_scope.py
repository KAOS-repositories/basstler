"""
Which of the repositories a hub file lists a site build may publish.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from basstler.github.repository import Repository
from basstler.github.repository_visibility import (
    RepositoryVisibility,
    RepositoryVisibilityReader,
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

    visibility: RepositoryVisibilityReader
    """
    How each repository's visibility is read.
    """

    def exclusion_of(self, repository: Repository) -> str | None:
        visibility = self.visibility.visibility_of(repository)
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
