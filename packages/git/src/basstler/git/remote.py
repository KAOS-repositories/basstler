"""
A remote of a clone: the repository a remote name or URL points at.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.git.commands import GitCommandRunner
from basstler.git.repository import GitRepository

# %% the remote


@dataclass(frozen=True)
class Remote(GitRepository):
    """
    The repository one remote of a clone points at.
    """

    git: GitCommandRunner
    """
    The clone the remote is reached from.
    """

    location: str
    """
    The remote, as a remote name in the clone or a URL.
    """

    @property
    def url(self) -> str:
        return self.git.attempt("remote", "get-url", self.location).output or (
            self.location
        )
