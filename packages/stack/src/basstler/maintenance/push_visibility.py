"""
Refusing to push commits into a repository that is more visible than where they came
from.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.github.client import GitHubAttemptReader
from basstler.github.repository import Repository
from basstler.github.repository_visibility import RepositoryVisibility


@dataclass(frozen=True)
class PushVisibilityGuard:
    """
    Decides whether commits of one repository may be pushed into another.
    """

    github: GitHubAttemptReader
    """
    How the repositories' visibility is read.
    """

    source: Repository
    """
    The repository the pushed commits belong to.
    """

    target: Repository
    """
    The repository the commits would be pushed into.
    """

    def refusal(self) -> str | None:
        """
        :return: Why the push would publish the source's commits more widely than the
            source does, ``None`` when it is safe: the two are one repository, the
            source is known to be public, or the target is known to be private.
        """
        if self.source == self.target:
            return None
        visibility_of_source = RepositoryVisibility.read_from(self.github, self.source)
        if visibility_of_source is RepositoryVisibility.PUBLIC:
            return None
        visibility_of_target = RepositoryVisibility.read_from(self.github, self.target)
        if visibility_of_target is RepositoryVisibility.PRIVATE:
            return None
        return (
            f"{self.target.full_name} is not known to be private, while "
            f"{self.source.full_name} is not known to be public, so pushing there could "
            f"publish private commits; push by hand once the target is confirmed"
        )
