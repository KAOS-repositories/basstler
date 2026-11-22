"""
A remote of a clone, named by the GitHub repository it points at.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.git.remote import Remote
from basstler.github.repository import Repository

# %% the remote


@dataclass(frozen=True)
class GitHubRemote(Remote):
    """
    A :class:`Remote` that knows the GitHub repository it points at.
    """

    @property
    def github_repository(self) -> Repository | None:
        """
        :return: The repository the remote points at, ``None`` when it names none - a
            remote given as a local path.
        """
        url = self.url
        if not Repository.names_a_repository(url):
            return None
        return Repository.from_remote_url(url)

    @property
    def description(self) -> str:
        """:return: The repository's name, or the remote's where it names none."""
        repository = self.github_repository
        return repository.full_name if repository else self.location
